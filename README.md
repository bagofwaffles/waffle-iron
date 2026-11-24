# Waffle Iron

Tools for the Teenage Engineering OP-XY and OP-1 Field for the
[bag of waffles](https://github.com/bagofwaffles?tab=repositories) projects.

**Use it here: https://bagofwaffles.github.io/waffle-iron/**

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

## License

GPL-2.0-or-later. See [`LICENSE`](LICENSE).
