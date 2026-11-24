#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests of tools/leak-check.py on throwaway repositories: each rule fires
on what it is for and stays quiet on clean input. The strings the rules
look for are put together here from pieces, so that this file passes the
check itself. Python 3, standard library only; needs git.

    test_leak_check.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(TOP, 'tools', 'leak-check.py')

NAME = 'bagofwaffles'
MAIL = NAME + '@' + 'fastmail.com'
OTHER = 'someone' + '@' + 'example.org'
HOMEDIR = '/' + 'Users' + '/' + 'someone'
SECRET = 'Zebedee'
UTC = '2026-01-02T03:04:05+0000'
ZEROS = '0' * 40


def jpeg(marker=b'', body=b''):
    """A JPEG's opening: JFIF, then one more segment if asked, then the scan."""
    def segment(m, b):
        return b'\xff' + m + (len(b) + 2).to_bytes(2, 'big') + b
    extra = segment(marker, body) if marker else b''
    return b'\xff\xd8' + segment(b'\xe0', b'JFIF\0\1\1\0\0\1\0\1\0\0') + extra + \
        b'\xff\xda\0\2' + b'Exif\0\0 in the picture data is not a block\xff\xd9'


def chunk(kind, body):
    return len(body).to_bytes(4, 'big') + kind + body + b'\0' * 4


JPEG = jpeg()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, 'repo')
        self.cfg = os.path.join(self.tmp.name, 'cfg')
        os.makedirs(self.repo)
        os.makedirs(self.cfg)
        self.env = dict(os.environ, HOME=self.tmp.name, TZ='UTC',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        WB_LEAK_CONFIG=self.cfg,
                        GIT_AUTHOR_NAME=NAME, GIT_AUTHOR_EMAIL=MAIL,
                        GIT_COMMITTER_NAME=NAME, GIT_COMMITTER_EMAIL=MAIL,
                        GIT_AUTHOR_DATE=UTC, GIT_COMMITTER_DATE=UTC)
        self.git('init', '-q', '-b', 'main')

    def git(self, *args, **env):
        done = subprocess.run(('git',) + args, cwd=self.repo, env=dict(self.env, **env),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 0, done.stderr.decode())
        return done.stdout.decode().strip()

    def write(self, path, data):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode())

    def commit(self, files=None, message='a change', **env):
        for path, data in (files or {'a.txt': 'plain\n'}).items():
            self.write(path, data)
        self.git('add', '-A')
        self.git('commit', '-q', '--allow-empty', '-m', message, **env)
        return self.git('rev-parse', 'HEAD')

    def tool(self, *args, stdin='', cwd=None, **env):
        done = subprocess.run((sys.executable, '-I', '-B', TOOL) + args,
                              cwd=cwd or self.repo, env=dict(self.env, **env),
                              input=stdin.encode(), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        return done.returncode, done.stderr.decode()

    def push(self, sha, ref='refs/heads/main', theirs=ZEROS, remote='elsewhere'):
        return self.tool('pre-push', remote, 'url',
                         stdin='%s %s %s %s\n' % (ref, sha, ref, theirs))

    def caught(self, result, rule, status=1):
        code, text = result
        self.assertEqual(code, status, text)
        self.assertIn(rule, text)

    def clean(self, result):
        code, text = result
        self.assertEqual((code, text), (0, ''))


class PrePush(Case):
    def test_clean_commit(self):
        self.clean(self.push(self.commit()))

    def test_author(self):
        sha = self.commit(GIT_AUTHOR_NAME='Somebody Else')
        self.caught(self.push(sha), 'author is not the project identity')

    def test_author_email(self):
        sha = self.commit(GIT_AUTHOR_EMAIL=OTHER)
        self.caught(self.push(sha), 'author is not the project identity')

    def test_committer(self):
        sha = self.commit(GIT_COMMITTER_NAME='Somebody Else')
        self.caught(self.push(sha), 'committer is not the project identity')

    def test_web_merge_committer(self):
        sha = self.commit(GIT_COMMITTER_NAME='GitHub',
                          GIT_COMMITTER_EMAIL='noreply' + '@' + 'github.com')
        self.clean(self.push(sha))

    def test_trailer(self):
        sha = self.commit(message='a change\n\nCo-Authored' + '-By: A Tool')
        self.caught(self.push(sha), 'trailer in the message')

    def test_time_zone(self):
        sha = self.commit(GIT_AUTHOR_DATE='2026-01-02T03:04:05-0600')
        self.caught(self.push(sha), 'time zone is not UTC')

    def test_compiled_python(self):
        sha = self.commit({'tools/__pycache__/x.pyc': b'\x00\x01code'})
        self.caught(self.push(sha), 'binary file outside')

    def test_screenshot(self):
        self.clean(self.push(self.commit({'docs/ui/main.png': b'\x89PNG\x00\x00'})))

    def test_vector(self):
        self.clean(self.push(self.commit({'tests/oracle/S-05-os-handoff/vectors/a.ldr': b'\x00' * 9})))

    def test_photo(self):
        self.clean(self.push(self.commit({'photos/board.jpg': JPEG})))

    def test_photo_elsewhere(self):
        sha = self.commit({'board.jpg': JPEG})
        self.caught(self.push(sha), 'binary file outside')

    def test_photo_exif(self):
        sha = self.commit({'photos/board.jpg': jpeg(b'\xe1', b'Exif\0\0MM\0*')})
        self.caught(self.push(sha), 'Exif block in an image')

    def test_photo_xmp(self):
        sha = self.commit({'photos/board.jpg': jpeg(b'\xe1', b'http://ns.adobe.com/xap/1.0/\0<x/>')})
        self.caught(self.push(sha), 'XMP block in an image')

    def test_photo_iptc(self):
        sha = self.commit({'photos/board.jpg': jpeg(b'\xed', b'Photoshop 3.0\0')})
        self.caught(self.push(sha), 'IPTC block in an image')

    def test_png_exif(self):
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', b'\0' * 13) + chunk(b'eXIf', b'MM\0*')
        self.caught(self.push(self.commit({'docs/ui/a.png': png})), 'Exif block in an image')

    def test_png_plain(self):
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', b'\0' * 13) + chunk(b'IDAT', b'eXIf')
        self.clean(self.push(self.commit({'docs/ui/a.png': png})))

    def test_spec_tree(self):
        sha = self.commit({'spec/S-05-os-handoff.md': 'text\n'})
        self.caught(self.push(sha), 'a file under spec/')

    def test_home_path_in_file(self):
        sha = self.commit({'docs/notes.md': 'see ' + HOMEDIR + '/x\n'})
        self.caught(self.push(sha), 'home directory path: docs/notes.md:1')

    def test_home_path_in_binary(self):
        sha = self.commit({'docs/ui/a.png': b'\x00' + HOMEDIR.encode()})
        self.caught(self.push(sha), 'home directory path')

    def test_session_path(self):
        sha = self.commit({'a.md': 'projects/-' + 'Users-' + 'someone-Projects\n'})
        self.caught(self.push(sha), 'home directory path')

    def test_home_path_in_message(self):
        sha = self.commit(message='built in ' + HOMEDIR)
        self.caught(self.push(sha), 'home directory path')

    def test_email_in_file(self):
        sha = self.commit({'README.md': 'one\ntwo\nwrite to ' + OTHER + '\n'})
        self.caught(self.push(sha), 'email address: README.md:3')

    def test_upstream_keeps_its_addresses(self):
        self.clean(self.push(self.commit({'src/third_party/lib/AUTHORS': OTHER + ' ' + HOMEDIR})))

    def test_project_address(self):
        self.clean(self.push(self.commit({'README.md': 'write to ' + MAIL + '\n'})))

    def test_ci_home(self):
        self.clean(self.push(self.commit({'Dockerfile': 'WORKDIR /home' + '/runner\n'})))

    def test_submodule(self):
        sha = self.commit({'.gitmodules': '[submodule "x"]\n'})
        self.caught(self.push(sha), 'submodule')

    def test_tagger(self):
        self.commit()
        self.git('tag', '-a', 'v1', '-m', 'one', GIT_COMMITTER_NAME='Somebody Else')
        sha = self.git('rev-parse', 'v1')
        self.caught(self.push(sha, 'refs/tags/v1'), 'tagger is not the project identity')

    def test_tag(self):
        self.commit()
        self.git('tag', '-a', 'v1', '-m', 'one')
        self.clean(self.push(self.git('rev-parse', 'v1'), 'refs/tags/v1'))

    def test_notes(self):
        self.caught(self.push(self.commit(), 'refs/notes/commits'),
                    'only branches and tags are pushed')

    def test_delete(self):
        self.commit(GIT_AUTHOR_NAME='Somebody Else')
        self.clean(self.push(ZEROS))

    def test_only_new_commits(self):
        old = self.commit(GIT_AUTHOR_NAME='Somebody Else')
        new = self.commit({'b.txt': 'more\n'})
        self.clean(self.push(new, theirs=old))

    def test_forced_over_unknown(self):
        self.clean(self.push(self.commit(), theirs='1' * 40))

    def test_banned_ancestor(self):
        old = self.commit()
        new = self.commit({'b.txt': 'more\n'})
        self.write('../cfg/banned-commits', old + '\n')
        # Even when the remote is thought to hold the old commit already.
        self.caught(self.push(new, theirs=old), 'descends from a banned commit')

    def test_private_pattern(self):
        self.write('../cfg/leak-patterns', '# a comment\n\n' + SECRET.lower() + r'\b' + '\n')
        sha = self.commit({'src/third_party/x.c': 'one\nby ' + SECRET + '\n'})
        code, text = self.push(sha)
        self.assertEqual(code, 1)
        self.assertIn('private pattern 3: src/third_party/x.c:2', text)
        self.assertNotIn(SECRET.lower(), text.lower())

    def test_private_pattern_in_ref(self):
        self.write('../cfg/leak-patterns', SECRET + '\n')
        code, text = self.push(self.commit(), 'refs/heads/' + SECRET)
        self.assertEqual(code, 1)
        self.assertIn('private pattern 1 in a ref name', text)
        self.assertNotIn(SECRET, text)


class Others(Case):
    def test_tree(self):
        self.commit()
        self.clean(self.tool('tree'))
        self.commit({'docs/x.md': HOMEDIR + '\n', 'x.o': b'\x00\x00'})
        code, text = self.tool('tree')
        self.assertEqual(code, 1)
        self.assertIn('home directory path: docs/x.md:1', text)
        self.assertIn('binary file outside the test data and screenshots: x.o', text)

    def test_history(self):
        self.commit({'x.md': OTHER + '\n'})
        sha = self.commit({'x.md': 'gone\n'})
        self.caught(self.tool('history', '--all'), 'email address: x.md:1')
        self.write('../cfg/banned-commits', sha + ' the old tip\n')
        self.caught(self.tool('history'), 'holds a banned commit')

    def test_history_clean(self):
        self.commit()
        self.clean(self.tool('history', '--all'))

    def test_commit_msg(self):
        self.write('../msg', 'subject\n\n# a comment with ' + OTHER + '\n')
        self.clean(self.tool('commit-msg', os.path.join(self.tmp.name, 'msg')))
        self.write('../msg', 'subject\n\nSigned-off' + '-by: Me\n')
        self.caught(self.tool('commit-msg', os.path.join(self.tmp.name, 'msg')), 'trailer')

    def test_pre_commit(self):
        self.write('a.txt', 'plain\n')
        self.git('add', '-A')
        self.clean(self.tool('pre-commit'))
        self.caught(self.tool('pre-commit', GIT_AUTHOR_EMAIL=OTHER), 'author is not')
        self.caught(self.tool('pre-commit', TZ='America/Chicago', GIT_AUTHOR_DATE='',
                              GIT_COMMITTER_DATE=''), 'time zone is not UTC')
        self.write('x.pyc', b'\x00')
        self.git('add', '-A')
        self.caught(self.tool('pre-commit'), 'binary file outside')

    def test_files(self):
        self.write('../out.ldr', b'\x00\x01 plain \xff')
        out = os.path.join(self.tmp.name, 'out.ldr')
        self.clean(self.tool('files', out))
        self.write('../out.ldr', b'\x00' + HOMEDIR.encode() + b'/build\x00')
        self.caught(self.tool('files', out), 'home directory path: out.ldr')

    def test_usage(self):
        self.assertEqual(self.tool('nonsense')[0], 3)


class ClaudeHook(Case):
    def setUp(self):
        super().setUp()
        self.git('remote', 'add', 'origin', 'git' + '@' + 'github.com:' + NAME + '/x.git')
        self.commit()

    def hook(self, command, tool='Bash', cwd=None):
        event = {'tool_name': tool, 'tool_input': {'command': command},
                 'cwd': cwd or self.repo}
        return self.tool('claude-hook', stdin=json.dumps(event), cwd=self.tmp.name)

    def test_unrelated(self):
        self.clean(self.hook('ls -la'))
        self.clean(self.hook('gh pr view 5 > ' + HOMEDIR + '/out.txt'))
        self.clean(self.hook('git status && git log --oneline -n 3'))

    def test_another_project(self):
        other = os.path.join(self.tmp.name, 'other')
        os.makedirs(other)
        self.clean(self.hook('gh issue create --title x --body ' + HOMEDIR, cwd=other))

    def test_here_document(self):
        command = ('cd ' + HOMEDIR + ' && gh pr create --title "a fix" --body "$(cat <<\'EOF\'\n'
                   'Ran with WB=' + HOMEDIR + '/emu\nEOF\n)"')
        self.caught(self.hook(command), 'home directory path: gh command text', 2)

    def test_clean_post(self):
        self.clean(self.hook('cd ' + HOMEDIR + ' && gh pr create --title "a fix" --body "$(cat <<\'EOF\'\n'
                             'Two lines.\nNothing else.\nEOF\n)"'))

    def test_unparsed_command(self):
        command = "gh issue comment 5 --body-file - <<EOF\nIt doesn't fit: " + OTHER + '\nEOF'
        self.caught(self.hook(command), 'email address', 2)

    def test_body_file(self):
        body = os.path.join(self.tmp.name, 'body.md')
        self.write('../body.md', 'All good.\n')
        self.clean(self.hook('gh pr create --title t --body-file ' + body))
        self.clean(self.hook('gh pr comment 5 -F ' + body))
        self.write('../body.md', 'From ' + OTHER + '\n')
        self.caught(self.hook('gh pr create --title t --body-file ' + body), 'email address', 2)
        self.caught(self.hook('gh pr comment 5 -F ' + body), 'email address', 2)
        self.caught(self.hook('gh pr create --body-file=' + body + '.missing'),
                    'cannot read a file given to gh', 2)

    def test_api_field(self):
        self.caught(self.hook('gh api repos/o/r/issues/1/comments -f body="at ' + HOMEDIR + '"'),
                    'home directory path', 2)

    def test_release_asset(self):
        self.write('out.ldr', b'\x00' + HOMEDIR.encode() + b'\x00')
        self.caught(self.hook('gh release create v1 out.ldr --notes "first"'),
                    'home directory path: file given to gh', 2)

    def test_private_pattern(self):
        self.write('../cfg/leak-patterns', SECRET + '\n')
        code, text = self.hook('gh issue create --title "from ' + SECRET + '" --body x')
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, text)

    def test_skipping_hooks(self):
        for command in ('git push --no-verify origin main', 'git commit -n -m x',
                        'git commit -anm x', 'git -c core.hooksPath=/dev/null commit -m x'):
            self.caught(self.hook(command), 'the git hooks may not be skipped', 2)
        self.clean(self.hook('git commit -m "no -n here" --amend --no-edit'))

    def test_push_needs_the_hook(self):
        self.caught(self.hook('git push origin main'), 'no pre-push hook here', 2)
        hook = os.path.join(self.repo, '.git', 'hooks', 'pre-push')
        self.write('.git/hooks/pre-push', '#!/bin/sh\n')
        os.chmod(hook, 0o755)
        self.clean(self.hook('git push origin main'))
        beside = os.path.join(self.tmp.name, NAME)
        os.makedirs(beside)
        self.clean(self.hook('git -C ' + self.repo + ' push', cwd=beside))
        self.caught(self.hook('git -C ' + beside + ' push', cwd=beside), 'no pre-push hook', 2)

    def test_broken_input(self):
        self.assertEqual(self.tool('claude-hook', stdin='not json')[0], 2)


if __name__ == '__main__':
    unittest.main()
