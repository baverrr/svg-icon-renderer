# Privacy policy

Last updated: 2026-11-12

svg-icon-renderer runs only on your computers. It collects no personal data and sends nothing
anywhere except, for the Windows icon theme, to the Linux machine you name.

## The plugin

- It reads the SVG data that a Qt application asks it to draw and turns it into an image in memory.
  Nothing is stored or passed on.
- It makes no network connections and contains no telemetry, analytics, crash reporting or update
  checks.
- It does not follow references from an SVG to other files on disk or on the network. Images
  embedded in the SVG itself (`data:` URIs) are still drawn.
- When an SVG can't be parsed or drawn, it logs a short error from librsvg under the `rsvgqt`
  logging category. The message goes to the application's standard error, which on Plasma usually
  ends up in your local systemd journal. It never leaves your machine.

## The scripts

- `install.sh` and `undo.sh` only add or remove files in your home folder:
  `~/.local/lib/rsvg-qt-icons/`, `~/.config/plasma-workspace/env/rsvg-qt-icons.sh` and KDE's icon
  cache.
- `test/dolphin-test.sh` takes a screenshot of the Dolphin window it opens and saves it in
  `test/screenshots/`. Look at the screenshot before sharing it, as it shows your Dolphin sidebar
  (places, network shares).
- `test/check-session.sh` reads your systemd user environment and the memory maps of your own
  plasmashell, Dolphin and System Settings processes, and prints the result to your terminal.
- The other tests read SVG files and write images under `build/`, inside this folder.

## The Windows icon theme (windows/)

- `fetch.sh` connects only to the ssh host you set in `RENDER_HOST`, with your own ssh setup. It
  sends `render.py`, the theme name and a list of icon names, and gets back the rendered icons and
  a log of which SVG files were used. It keeps those in `windows/` (`ico/` with an `.ico` and a
  preview image per icon, `sources.txt`, `render.log`, `svgs.txt`, and `ico.tgz` and `ico.new/`
  while it runs).
- `render.py` runs on that Linux machine. It reads icon themes in `~/.local/share/icons`, `~/.icons`,
  `/usr/local/share/icons` and `/usr/share/icons`, works in a temporary folder that it deletes, and
  writes only to its output.
- `dump_icons.py`, `check_live.py` and `unmapped_sheet.py` read Windows' own icons (and
  `icon-map.txt`) and write images where you tell them to; the README uses `windows/`.
- `build_theme.py` writes only the theme folder you give it (the theme DLL and `theme.ini`, and it
  deletes older theme DLLs there) and files in `windows/`.
- `refresh-icons.cmd` restarts Explorer, asks Windows to refresh its icons (`ie4uinit.exe -show`)
  and deletes Windows' icon cache files, which Windows rebuilds.
- None of them make other network connections or collect anything.

## Third parties

The plugin uses librsvg, cairo and Qt from your Linux distribution. None of them make network
connections when drawing images. The Windows icon theme is loaded by Windhawk and its Resource
Redirect mod, which you install yourself; their own privacy terms apply. GitHub hosts this repository; its own privacy statement covers
what GitHub collects when you visit or clone it.

## Contact

Questions about this policy: open an issue at
https://github.com/baverrr/svg-icon-renderer/issues
