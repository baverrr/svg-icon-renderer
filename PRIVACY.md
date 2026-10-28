# Privacy policy

Last updated: 2026-10-28

svg-icon-renderer runs only on your computer. It collects no personal data and sends nothing
anywhere.

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

## Third parties

The plugin uses librsvg, cairo and Qt from your Linux distribution. None of them make network
connections when drawing images. GitHub hosts this repository; its own privacy statement covers
what GitHub collects when you visit or clone it.

## Contact

Questions about this policy: open an issue at
https://github.com/baverrr/svg-icon-renderer/issues
