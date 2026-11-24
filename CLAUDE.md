# Waffle Iron

Tools for the OP-XY and OP-1 Field. The install page in `docs/` is served by GitHub Pages from `main`, so
what lands on `main` is live.

## Working here

- The page is plain HTML, CSS and JavaScript modules: no build step, no dependencies, nothing to install.
- Serve it with `python3 -I -B -m http.server 8769 --bind 127.0.0.1 --directory docs`; on localhost
  `?demo=present` (and the others in `page.js`'s `DEMOS`) stands in for a unit.
- `npm run check` runs the unit tests and the leak check. Run it before a commit.
- waffle-boot is a read-only reference here: read it, never change it.

## What goes in a change

- This is a small project: commit directly on `main`. No `dev/` branches or worktrees are needed. Where
  the shared git rules ask for them, this file wins.
- One finished piece of work per commit, with `npm run check` passing first.
- Commit subjects are `area: what changed`, lower case, about the behavior and not the process
  (`page:`, `release:`, `readme:`, `tools:`). No trailers or attribution lines.
- US English. Short comments that explain the code; no dates, names or history in them.
- Every commit is by the project identity, made with `TZ=UTC`.
- No personal names, email addresses, home paths or host names in files or commit messages.
  `tools/leak-check.py` checks every commit and push. Never skip the hooks.
- Everything pushed is public, and `main` is the live page. Ask before each push, push once when the
  whole job is done, and never rewrite or force-push what is pushed.
- GitHub Actions is off: the checks run locally.
- The unit's serial number is never shown or logged by the page.
