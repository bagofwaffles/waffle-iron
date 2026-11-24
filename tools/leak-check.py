#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Checks that nothing personal or foreign leaves with a commit, a push or
a post to GitHub. Python 3, standard library only; run it with -I -B.

    leak-check.py tree                    the tracked files, as checked out
    leak-check.py history [--all | REV…]  commits and everything they hold
    leak-check.py files PATH…             files about to be released
    leak-check.py doctor                  is this machine set up?

    leak-check.py pre-commit              \\
    leak-check.py commit-msg FILE          | the git hooks
    leak-check.py pre-push REMOTE URL     /
    leak-check.py claude-hook             a Claude Code PreToolUse hook

What it looks for:

  identity   every commit is by the project identity, in UTC
  messages   no "…-by:" trailers, no addresses
  content    no home directory paths, no email addresses, and binary
             files only where photos, test data, screenshots and the
             page's copy of the installer live
  images     no Exif, XMP or IPTC block in a JPEG or PNG: that is where
             a camera puts the place, the time and its serial number
  private    the patterns in ~/.config/bagofwaffles/leak-patterns, one
             regular expression a line, matched without regard to case
  banned     nothing descended from a commit in
             ~/.config/bagofwaffles/banned-commits is pushed

A finding names the rule and the place, never the text that matched, so
that a report can be pasted anywhere. Exit status: 0 clean, 1 findings,
2 a blocked Claude Code command, 3 a usage or set-up error.

It cannot recognize copied text or constants: that is what the clean-room
rule in CONTRIBUTING.md is for. tools/leak-check-install.sh installs it.
"""
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import threading

PROJECT = 'bagofwaffles'
EMAIL = 'bagofwaffles@fastmail.com'
AUTHORS = {('bagofwaffles', EMAIL), ('Bag of Waffles', EMAIL)}
WEB_FLOW = ('GitHub', 'noreply@github.com')
EMAILS_ALLOWED = {EMAIL, 'noreply@github.com', 'git@github.com'}

HOME_RE = re.compile(
    rb'/Users/[A-Za-z0-9._-]+'
    rb'|/home/(?!runner\b)[A-Za-z0-9._-]+'
    rb'|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+'
    rb'|-Users-[A-Za-z0-9._]+')
EMAIL_RE = re.compile(
    rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
TRAILER_RE = re.compile(rb'^[A-Za-z-]+-by:', re.I | re.M)

# Binary files belong here and nowhere else.
BINARY_OK = re.compile(r'^(photos/|docs/ui/|docs/web/release/|tests/oracle/S-[^/]+/vectors/|'
                       r'tests/fuzz/regressions/)')
# The specification is a private repository of its own: nothing under spec/ is tracked here.
PRIVATE_TREE = re.compile(r'^spec(/|$)')
# Upstream code keeps its authors' addresses and paths.
UPSTREAM = re.compile(r'^src/third_party/')

PER_FILE = 3        # findings reported for one rule in one file
ZEROS = '0' * 40


class Report:
    def __init__(self):
        self.lines = []

    def add(self, rule, where):
        line = 'leak-check: %s: %s' % (rule, where)
        if line not in self.lines:
            self.lines.append(line)

    def finish(self, status=1):
        for line in self.lines:
            print(line, file=sys.stderr)
        return status if self.lines else 0


def fail(text):
    print('leak-check: ' + text, file=sys.stderr)
    sys.exit(3)


def git(args, cwd=None, data=None, ok=(0,)):
    done = subprocess.run(['git'] + args, cwd=cwd, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode not in ok:
        fail('git %s: %s' % (args[0], done.stderr.decode('utf-8', 'replace').strip()))
    return done.stdout


def git_ok(args, cwd=None):
    return subprocess.run(['git'] + args, cwd=cwd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


# ---- private configuration --------------------------------------------

def config_dir():
    return os.environ.get('WB_LEAK_CONFIG') or \
        os.path.join(os.path.expanduser('~'), '.config', PROJECT)


def config_lines(name):
    try:
        with open(os.path.join(config_dir(), name), 'rb') as f:
            rows = f.read().split(b'\n')
    except OSError:
        return []
    return [(n, row.strip()) for n, row in enumerate(rows, 1)
            if row.strip() and not row.lstrip().startswith(b'#')]


_patterns = None


def patterns():
    global _patterns
    if _patterns is None:
        _patterns = []
        for n, row in config_lines('leak-patterns'):
            try:
                _patterns.append((n, re.compile(row, re.I)))
            except re.error:
                fail('leak-patterns line %d is not a regular expression' % n)
    return _patterns


def banned():
    return [row.split()[0].decode('ascii', 'replace')
            for _, row in config_lines('banned-commits')]


# ---- the rules ----------------------------------------------------------

def line_of(data, at):
    return data.count(b'\n', 0, at) + 1


def scan_text(data, where, report, shapes=True, emails=True):
    """The text rules on some bytes. `where` is a path, or a label."""
    if shapes:
        hits = 0
        for m in HOME_RE.finditer(data):
            report.add('home directory path', '%s:%d' % (where, line_of(data, m.start())))
            hits += 1
            if hits == PER_FILE:
                break
        hits = 0
        for m in EMAIL_RE.finditer(data) if emails else ():
            if m.group().decode('ascii', 'replace').lower() in EMAILS_ALLOWED:
                continue
            report.add('email address', '%s:%d' % (where, line_of(data, m.start())))
            hits += 1
            if hits == PER_FILE:
                break
    for n, pattern in patterns():
        m = pattern.search(data)
        if m:
            report.add('private pattern %d' % n, '%s:%d' % (where, line_of(data, m.start())))


def scan_name(name, what, report):
    """A path or a ref name."""
    raw = name.encode('utf-8', 'surrogateescape')
    if HOME_RE.search(raw):
        report.add('home directory path in a %s' % what, name)
    for n, pattern in patterns():
        if pattern.search(raw):
            report.add('private pattern %d in a %s' % (n, what), '(not shown)')


def image_metadata(data):
    """The kind of metadata block a JPEG or PNG carries, or ''."""
    if data[:2] == b'\xff\xd8':
        at = 2
        while at + 4 <= len(data) and data[at] == 0xff:
            marker = data[at + 1]
            if marker == 0xda:                # the picture starts here
                break
            if marker == 0xff:                # a fill byte
                at += 1
                continue
            if 0xd0 <= marker <= 0xd9 or marker == 0x01:
                at += 2                       # a marker with no length
                continue
            size = int.from_bytes(data[at + 2:at + 4], 'big')
            body = data[at + 4:at + 2 + size]
            if marker == 0xe1 and body.startswith(b'Exif\0'):
                return 'Exif'
            if marker == 0xe1 and body.startswith(b'http://ns.adobe.com/'):
                return 'XMP'
            if marker == 0xed:
                return 'IPTC'
            at += 2 + size
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        at = 8
        while at + 8 <= len(data):
            size = int.from_bytes(data[at:at + 4], 'big')
            kind = data[at + 4:at + 8]
            if kind == b'eXIf':
                return 'Exif'
            if kind in (b'iTXt', b'tEXt', b'zTXt') and \
                    data[at + 8:at + 8 + size].startswith(b'XML:com.adobe.xmp'):
                return 'XMP'
            if kind == b'IDAT':               # the picture starts here
                break
            at += 12 + size
    return ''


def scan_blob(path, data, report):
    """A tracked file's content, under its path."""
    binary = b'\0' in data[:8000]
    upstream = bool(UPSTREAM.match(path))
    base = path.rsplit('/', 1)[-1]
    scan_name(path, 'path', report)
    if PRIVATE_TREE.match(path):
        report.add('a file under spec/, which is not tracked here', path)
    if binary and not BINARY_OK.match(path):
        report.add('binary file outside the test data and screenshots', path)
    found = image_metadata(data)
    if found:
        report.add('%s block in an image (strip it: exiftool -all=)' % found, path)
    if base == '.gitmodules':
        report.add('submodule', path)
    if base == '.gitattributes' and b'filter=lfs' in data:
        report.add('LFS filter', path)
    scan_text(data, path, report, shapes=not upstream, emails=not binary)


def parse_ident(text):
    """'Name <email> epoch +hhmm' -> (name, email, offset)."""
    m = re.match(r'(.*) <([^>]*)> \d+ ([+-]\d{4})$', text.strip())
    return (m.group(1), m.group(2), m.group(3)) if m else ('', '', '')


def check_ident(author, committer, where, report):
    an, ae, aoff = author
    cn, ce, coff = committer
    if (an, ae) not in AUTHORS:
        report.add('author is not the project identity', where)
    if (cn, ce) not in AUTHORS and (cn, ce) != WEB_FLOW:
        report.add('committer is not the project identity', where)
    if aoff != '+0000' or coff != '+0000':
        report.add('time zone is not UTC (commit with TZ=UTC)', where)


def check_message(data, where, report):
    if TRAILER_RE.search(data):
        report.add('trailer in the message', where)
    scan_text(data, where, report)


# ---- reading git --------------------------------------------------------

def objects(names, cwd=None):
    """Yields (name, type, bytes) for object names, through one git."""
    names = list(names)
    if not names:
        return
    child = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=cwd,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def feed():
        for name in names:
            child.stdin.write(name.encode('utf-8', 'surrogateescape') + b'\n')
        child.stdin.close()
    threading.Thread(target=feed, daemon=True).start()
    for name in names:
        head = child.stdout.readline()
        if head.endswith(b' missing\n') or not head:
            yield name, None, b''
            continue
        _, kind, size = head.rsplit(None, 2)
        data = child.stdout.read(int(size))
        child.stdout.read(1)
        yield name, kind.decode(), data
    child.wait()


def check_commits(revs, report, cwd=None):
    """Identity and message of each commit rev-list gives for `revs`."""
    shas = git(['rev-list'] + revs, cwd).decode().split()
    for sha, kind, data in objects(shas, cwd):
        if kind != 'commit':
            continue
        head, _, message = data.partition(b'\n\n')
        fields = dict(row.split(' ', 1) for row in
                      head.decode('utf-8', 'replace').split('\n') if ' ' in row)
        where = 'commit ' + sha[:10]
        check_ident(parse_ident(fields.get('author', '')),
                    parse_ident(fields.get('committer', '')), where, report)
        check_message(message, where + ' message', report)
    return shas


def check_blobs(revs, report, cwd=None):
    """Every file reachable from `revs`, once each."""
    seen = {}
    for row in git(['rev-list', '--objects'] + revs, cwd).decode(
            'utf-8', 'surrogateescape').split('\n'):
        sha, _, path = row.partition(' ')
        if path and sha not in seen:
            seen[sha] = path
    for sha, kind, data in objects(seen, cwd):
        if kind == 'blob':
            scan_blob(seen[sha], data, report)


def check_tag(sha, report, cwd=None):
    """An annotated tag's tagger and message."""
    head, _, message = git(['cat-file', 'tag', sha], cwd).partition(b'\n\n')
    for row in head.decode('utf-8', 'replace').split('\n'):
        if row.startswith('tagger '):
            name, email, offset = parse_ident(row[7:])
            if (name, email) not in AUTHORS:
                report.add('tagger is not the project identity', 'tag ' + sha[:10])
            if offset != '+0000':
                report.add('time zone is not UTC (tag with TZ=UTC)', 'tag ' + sha[:10])
    check_message(message, 'tag %s message' % sha[:10], report)


def check_banned(tip, report, cwd=None):
    for sha in banned():
        if git_ok(['cat-file', '-e', sha + '^{commit}'], cwd) and \
                git_ok(['merge-base', '--is-ancestor', sha, tip], cwd):
            report.add('descends from a banned commit', tip[:10])
            return


# ---- modes --------------------------------------------------------------

def mode_tree(args):
    report = Report()
    top = git(['rev-parse', '--show-toplevel']).decode().strip()
    for path in git(['ls-files', '-z'], top).decode('utf-8', 'surrogateescape').split('\0'):
        full = os.path.join(top, path)
        if not path or not os.path.lexists(full):
            continue
        if os.path.islink(full):
            data = os.readlink(full).encode('utf-8', 'surrogateescape')
        else:
            with open(full, 'rb') as f:
                data = f.read()
        scan_blob(path, data, report)
    return report.finish()


def mode_history(args):
    report = Report()
    revs = args or ['HEAD']
    shas = set(check_commits(revs, report))
    for sha in banned():
        if sha in shas:
            report.add('holds a banned commit', sha[:10])
    check_blobs(revs, report)
    tags = [r for r in revs if not r.startswith('-')]
    if '--all' in revs:
        tags = git(['for-each-ref', '--format=%(objectname)', 'refs/tags']).decode().split()
    for name in tags:
        if git(['cat-file', '-t', name], ok=(0, 128)).strip() == b'tag':
            check_tag(name, report)
    return report.finish()


def mode_files(args):
    if not args:
        fail('files: name at least one file')
    report = Report()
    for path in args:
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            fail('cannot read ' + path)
        scan_text(data, os.path.basename(path), report, emails=False)
    return report.finish()


def mode_pre_commit(args):
    report = Report()
    idents = []
    for which in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
        done = subprocess.run(['git', 'var', which], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        idents.append(parse_ident(done.stdout.decode('utf-8', 'replace')))
    check_ident(idents[0], idents[1], 'this commit', report)
    staged = [p for p in git(['diff', '--cached', '--name-only', '-z',
                              '--diff-filter=ACMR']).decode(
                                  'utf-8', 'surrogateescape').split('\0') if p]
    for name, kind, data in objects([':' + p for p in staged]):
        if kind == 'blob':
            scan_blob(name[1:], data, report)
    return report.finish()


def mode_commit_msg(args):
    if len(args) != 1:
        fail('commit-msg: one file')
    report = Report()
    with open(args[0], 'rb') as f:
        rows = [row for row in f.read().split(b'\n') if not row.startswith(b'#')]
    check_message(b'\n'.join(rows), 'the message', report)
    return report.finish()


def mode_pre_push(args):
    report = Report()
    remote = args[0] if args else ''
    known = bool(remote) and git_ok(['config', '--get', 'remote.%s.url' % remote])
    for row in sys.stdin.read().split('\n'):
        parts = row.split()
        if len(parts) != 4:
            continue
        _, local, ref, theirs = parts
        if local == ZEROS:
            continue                      # a delete sends nothing
        if not ref.startswith(('refs/heads/', 'refs/tags/')):
            report.add('only branches and tags are pushed', ref)
            continue
        scan_name(ref, 'ref name', report)
        revs = [local, '--not']
        if known:
            revs.append('--remotes=' + remote)
        if theirs != ZEROS and git_ok(['cat-file', '-e', theirs]):
            revs.append(theirs)
        if git(['cat-file', '-t', local]).strip() == b'tag':
            check_tag(local, report)
        check_banned(local, report)
        check_commits(revs, report)
        check_blobs(revs, report)
    return report.finish()


# ---- the Claude Code hook -----------------------------------------------

BREAKS = {';', '&&', '||', '|', '&', '(', ')', ';;', '|&'}
REDIRECT = re.compile(r'^\d*(>>?|<|>&|&>)$')
FILE_FLAGS = ('--body-file', '--notes-file', '--input')
GH_WRITES = {'create', 'edit', 'comment', 'review', 'close', 'merge', 'reopen',
             'upload', 'ready', 'rename', 'transfer', 'set', 'lock', 'pin'}


def segments(tokens, program):
    """The argument lists of each `program …` in a tokenized command line."""
    out, at = [], 0
    while at < len(tokens):
        if tokens[at] == program or tokens[at].endswith('/' + program):
            end = at + 1
            while end < len(tokens) and tokens[end] not in BREAKS:
                end += 1
            out.append(tokens[at + 1:end])
            at = end
        else:
            at += 1
    return out


def git_verb(argv):
    """(the git subcommand, the directory -C names) of one argument list."""
    where, at = '', 0
    while at < len(argv):
        if argv[at] in ('-C', '-c', '--git-dir', '--work-tree') and at + 1 < len(argv):
            if argv[at] == '-C':
                where = argv[at + 1]
            at += 2
        elif argv[at].startswith('-'):
            at += 1
        else:
            return argv[at], where, argv[at + 1:]
    return '', where, []


def gh_outgoing(argv, cwd):
    """What a gh command sends: (text, files to read, files it must read)."""
    words = [a for a in argv if not a.startswith('-')]
    if not words or (words[0] != 'api' and not GH_WRITES & set(words[1:3])
                     and words[0] != 'gist'):
        return '', [], []
    text, files, must = [], [], []
    at = 0
    while at < len(argv):
        arg, nxt = argv[at], argv[at + 1] if at + 1 < len(argv) else ''
        flag, eq, value = arg.partition('=')
        if REDIRECT.match(arg):
            at += 2
            continue
        if flag in FILE_FLAGS or (arg == '-F' and '=' not in nxt):
            name = value if eq else nxt
            if name and name != '-':
                must.append(name)
            at += 1 if eq else 2
            continue
        if not arg.startswith('-') and os.path.isfile(os.path.join(cwd, arg)):
            files.append(arg)             # a release asset
        elif '=@' in arg and os.path.isfile(os.path.join(cwd, arg.split('=@', 1)[1])):
            files.append(arg.split('=@', 1)[1])
        else:
            text.append(arg)
        at += 1
    return ' '.join(text), files, must


def hook_findings(command, cwd):
    report = Report()
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = None

    if re.search(r'\bgit\b', command):
        if '--no-verify' in command or re.search(r'hookspath', command, re.I):
            report.add('the git hooks may not be skipped', 'command')
        for argv in segments(tokens or command.split(), 'git'):
            verb, where, rest = git_verb(argv)
            where = os.path.join(cwd, where)
            if verb == 'commit' and any(re.match(r'^-[A-Za-z]*n[A-Za-z]*$', a) for a in rest):
                report.add('the git hooks may not be skipped', 'command')
            if verb == 'push':
                done = subprocess.run(['git', 'rev-parse', '--git-path', 'hooks'], cwd=where,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                hook = os.path.join(where, done.stdout.decode().strip(), 'pre-push')
                if done.returncode or not os.access(hook, os.X_OK):
                    report.add('no pre-push hook here (run tools/leak-check-install.sh)', 'command')

    if re.search(r'\bgh\b', command):
        if tokens is None:
            # Not parsed (an unpaired quote, as in a here-document): take
            # everything from gh on, less the files it names.
            rest = command[re.search(r'\bgh\b', command).start():]
            must = re.findall(r'(?:--body-file|--notes-file|--input|-F)[ =]+([^\s=]+)(?=\s|$)', rest)
            for name in must:
                rest = rest.replace(name, ' ')
            sends = [(rest, [], [m for m in must if m != '-'])]
        else:
            sends = [gh_outgoing(argv, cwd) for argv in segments(tokens, 'gh')]
        for text, files, must in sends:
            if text:
                scan_text(text.encode('utf-8', 'surrogateescape'), 'gh command text', report)
            for name in files + must:
                try:
                    with open(os.path.join(cwd, name), 'rb') as f:
                        scan_text(f.read(), 'file given to gh', report,
                                  emails=name in must)
                except OSError:
                    if name in must:
                        report.add('cannot read a file given to gh', 'command')
    return report


def mode_claude_hook(args):
    try:
        event = json.load(sys.stdin)
        command = event.get('tool_input', {}).get('command', '')
        cwd = event.get('cwd') or os.getcwd()
        if event.get('tool_name') != 'Bash' or not re.search(r'\b(gh|git)\b', command):
            return 0
        here = subprocess.run(['git', 'remote', '-v'], cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout.decode('utf-8', 'replace')
        if PROJECT not in (command + cwd + here).lower():
            return 0
        report = hook_findings(command, cwd)
    except SystemExit:
        return 2
    except Exception as error:            # a broken hook must not wave things through
        print('leak-check: hook error: %s' % type(error).__name__, file=sys.stderr)
        return 2
    return report.finish(2)


def mode_doctor(args):
    good = True

    def row(ok, text):
        nonlocal good
        good = good and ok
        print('%s %s' % ('ok  ' if ok else 'FAIL', text))

    home = config_dir()
    row(os.path.isdir(home), 'private directory ' + home.replace(os.path.expanduser('~'), '~'))
    name = os.path.join(home, 'leak-patterns')
    if os.path.isfile(name):
        row(stat.S_IMODE(os.stat(name).st_mode) & 0o077 == 0, 'leak-patterns is private (mode 600)')
        row(bool(patterns()), 'leak-patterns holds %d patterns' % len(patterns()))
    else:
        row(False, 'leak-patterns exists')
    print('     banned-commits holds %d commits' % len(banned()))
    installed = os.path.join(home, 'leak-check.py')
    mine = os.path.abspath(__file__)
    if os.path.isfile(installed) and os.path.abspath(installed) != mine:
        with open(installed, 'rb') as a, open(mine, 'rb') as b:
            row(a.read() == b.read(), 'the installed copy matches this one')
    else:
        row(os.path.isfile(installed), 'an installed copy exists')
    if git_ok(['rev-parse', '--git-dir']):
        hooks = git(['rev-parse', '--git-path', 'hooks']).decode().strip()
        for hook in ('pre-commit', 'commit-msg', 'pre-push'):
            row(os.access(os.path.join(hooks, hook), os.X_OK), 'hook %s is in place here' % hook)
        done = subprocess.run(['git', 'var', 'GIT_AUTHOR_IDENT'], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        ident = parse_ident(done.stdout.decode('utf-8', 'replace'))
        row(ident[:2] in AUTHORS, 'commits here use the project identity')
        row(ident[2] == '+0000', 'commits here are stamped in UTC (TZ=UTC)')
    return 0 if good else 1


MODES = {
    'tree': mode_tree, 'history': mode_history, 'files': mode_files,
    'doctor': mode_doctor, 'pre-commit': mode_pre_commit,
    'commit-msg': mode_commit_msg, 'pre-push': mode_pre_push,
    'claude-hook': mode_claude_hook,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(3)
    sys.exit(MODES[sys.argv[1]](sys.argv[2:]))
