# Waffle Iron

Tools for the Teenage Engineering OP-XY and OP-1 Field from the
[bag of waffles](https://github.com/bagofwaffles?tab=repositories) projects. The first is a page that installs
[waffle-boot](https://github.com/bagofwaffles/waffle-boot) or turns a unit's developer mode on or off,
from the browser.

**Use it here: https://bagofwaffles.github.io/waffle-iron/**

It needs Chrome or Edge on a computer, for Web MIDI and WebUSB. Plug the unit in over USB, turn it on and
allow MIDI when the browser asks.

> [!WARNING]
> waffle-boot is under development. Read its
> [README](https://github.com/bagofwaffles/waffle-boot#readme) and
> [How to Recover](https://github.com/bagofwaffles/waffle-boot/wiki/How-to-Recover) before you install it.

Waffle Iron is an independent project, not affiliated with or endorsed by Teenage Engineering.

## What the page does

- **Install waffle-boot.** The page restarts the unit into its upload screen as a USB disk and makes the
  `firmware.zip` to copy onto it, with the latest waffle-boot installer inside. You can give it your own
  `.ldr` instead, for a development build.
- **Manage Dev Mode.** The page restarts the unit into its boot menu and turns developer mode on or off.

The page keeps no copy of the installer. It reads the latest release from
[waffle-boot's own site](https://bagofwaffles.github.io/waffle-boot/), because a browser cannot download a
GitHub release file directly, and uses it only when its SHA-256 is the one the GitHub release lists. The
unit's serial number is never shown or logged. What the page sends and hears is logged in the browser's
console.

## Working on it

The page is plain HTML, CSS and JavaScript modules in [`docs/`](docs), with nothing to build. GitHub Pages
serves that folder from `main`.

Serve it locally:

```bash
python3 -I -B -m http.server 8769 --bind 127.0.0.1 --directory docs
```

Then open http://localhost:8769/. On localhost, `?demo=` stands in for a unit without touching MIDI:
`none`, `present` (an OP-XY), `field`, `boot`, `field-boot` or `nomidi`.

To try it from another computer, `tools/serve.py` serves the folder over HTTPS on every interface, with a
certificate and key you make in `.dev/` (never tracked).

Run the checks:

```bash
npm run check
```

That runs the page's unit tests (`node --test`) and the leak check's own tests, then the leak check over
the tracked files.

| Path | What it holds |
| --- | --- |
| `docs/` | The page. `page.js` drives it; `devmode.js`, `mtp.js`, `fwzip.js` and `release.js` are its parts. |
| `docs/devices/` | The drawings of the two units, made by `tools/web_devices.py`. |
| `test/` | Unit tests for the page's parts, and for the leak check. |
| `tools/leak-check.py` | Checks that nothing personal leaves with a commit or a push. See [`CONTRIBUTING.md`](CONTRIBUTING.md). |

## License

GPL-2.0-or-later. See [`LICENSE`](LICENSE).
