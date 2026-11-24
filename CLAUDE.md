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

- One pull request per finished piece of work.
- US English. Short comments that explain the code; no dates, names or history in them.
- Commit messages start with the area (`page:`, `release:`, `tools:`, `docs:`) and say what and why.
- No personal names, email addresses, home paths or host names in files or commit messages.
  `tools/leak-check.py` checks every commit (`tools/leak-check-install.sh` sets it up). Do not skip the
  hooks.
- The unit's serial number is never shown or logged by the page.
