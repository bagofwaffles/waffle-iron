# Contributing to Waffle Iron

Waffle Iron is not taking outside code contributions yet. Bug reports are welcome as issues. This page says
what applies to an issue today, and to a change once contributions open.

## A clean-room project

Like [waffle-boot](https://github.com/bagofwaffles/waffle-boot), Waffle Iron is written from scratch, from
public documentation and the projects' own specifications. It holds no code or data from the device's
firmware. Never paste, attach or link vendor firmware, or anything disassembled or decompiled from it, in
an issue, a pull request, a commit message, a comment or a test.

## An issue

Never attach firmware, update files, flash or memory dumps, keys, or a unit's serial number. The page's
console log never holds the serial number, so it is safe to paste.

## A change, once contributions open

- It is released under GPL-2.0-or-later ([`LICENSE`](LICENSE)); sending it means you agree. Every source
  file starts with an `SPDX-License-Identifier: GPL-2.0-or-later` line.
- Plain HTML, CSS and JavaScript modules, with no build step and no dependencies. US English.
- One focused commit per change. The message starts with the area it changes and says what and why, as in
  `page: the choices are two keys, and Dev Mode is Manage Dev Mode`.
- Short comments that explain the code; no dates, names or history in them.
- `npm run check` passes.

## Nothing personal leaves with a commit

No personal names, email addresses, home paths or host names in files or commit messages. Every commit is
by the project identity and stamped in UTC. `tools/leak-check.py` checks each commit, message and push; it
is the same check waffle-boot uses. The maintainer installs it once per machine with
`tools/leak-check-install.sh`, and `python3 -I -B tools/leak-check.py doctor` says whether this clone is set
up. Do not skip the hooks.
