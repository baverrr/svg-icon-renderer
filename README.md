# svg-icon-renderer

A Qt 6 image-format plugin (`librsvgqt.so`) that draws `svg`/`svgz` with librsvg instead of
QtSvg. KDE's icon loader (KIconLoader/KIconEngine) reads SVG icons through `QImageReader`, so with
this plugin your icons get full SVG 1.1 rendering: `feDropShadow`, `feTurbulence`,
`feDiffuseLighting`/`feSpecularLighting`, masks and the rest. QtSvg 6.10 does a few filters (plain
blur, offset, colour matrix, merge), but it drops all of those.

## Use

```
sudo apt install qt6-base-dev librsvg2-dev libcairo2-dev pkgconf   # once
bash build.sh                       # -> build/imageformats/librsvgqt.so
python3 test/compare.py build test/filter-test.svg build/compare     # renders QtSvg vs plugin, checks the effects
python3 test/stress.py build        # every icon in /usr/share/icons on 8 threads, broken input, speed
bash test/dolphin-test.sh before    # same Dolphin window without the plugin -> test/screenshots/before.png
bash test/dolphin-test.sh after     # real Dolphin window using the plugin -> test/screenshots/after.png
bash install.sh                     # no sudo; takes effect at next login
bash test/check-session.sh          # after login: which svg plugin plasmashell/Dolphin loaded
bash undo.sh                        # back to QtSvg at next login
```

## How it takes over without touching system files

`install.sh` copies the plugin to `~/.local/lib/rsvg-qt-icons/plugins/imageformats/` and adds
`~/.config/plasma-workspace/env/rsvg-qt-icons.sh`, which puts that folder first on `QT_PLUGIN_PATH`
for the Plasma session. When two plugins claim the same format, Qt uses the first one it finds,
and `QT_PLUGIN_PATH` folders are searched before the system one. Checked here: with the folder on
the path, `/usr/.../imageformats/libqsvg.so` isn't even loaded.

## Test results (2026-10-28, Qt 6.10.2, librsvg 2.61.3)

- `compare.py`: drop shadow and paper grain present with the plugin, absent with QtSvg, for both
  `.svg` and `.svgz`. PASS.
- `dolphin-test.sh`: the Dolphin process maps `librsvgqt.so` instead of `libqsvg.so`, and the folder
  icon shows the sheen, shadow and grain. See `test/screenshots/before.png` and `after.png`.
- `stress.py`: 43,333/43,333 system icons rendered at 64 px on 8 threads in 2.8 s, no crash. On a
  single thread it takes 1.04 s per 3,000 icons, against 0.73 s for QtSvg. Broken input is
  rejected: empty data, truncated files, garbage gzip, a 100000×100000 px request, and an XML
  entity bomb. A `file://` image reference is not loaded.
- Memory stays flat (about 46 MB) over 6,000 renders of the filter test icon.
- Installed and re-logged in: `test/check-session.sh` shows `QT_PLUGIN_PATH` in the systemd user
  environment, and plasmashell and Dolphin both load `librsvgqt.so`. No plugin warnings in the journal.

## Scope and risks

- Covers everything that loads SVG through `QImageReader`: KDE icons in Dolphin, the task manager,
  menus, Qt `QIcon`s from SVG files. It does not cover Plasma's own theme graphics (panel
  backgrounds, widgets), which KSvg draws with `QSvgRenderer` directly, nor `libqsvgicon.so` users.
- Every Qt app in the session uses it. Each read gets its own librsvg handle, so it is thread-safe.
  Image size is capped by Qt's allocation limit. External files are never loaded: no base path is
  given to librsvg, though `data:` URIs still work.
- librsvg is slower than QtSvg on heavy filters. KDE caches rendered icons, so that cost is paid
  once per icon and size.
- If Plasma ever fails to start, switch to a text console (Ctrl+Alt+F3), log in, run `bash undo.sh`,
  and log back in.

## License and privacy

MIT, see [LICENSE](LICENSE). The plugin collects no data and makes no network connections; see
[PRIVACY.md](PRIVACY.md).
