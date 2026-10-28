#!/usr/bin/env python3
"""Renders an SVG through QImageReader (the path KIconLoader uses) with and without the plugin and
checks that the filter effects only show up with it.

Usage: python3 compare.py PLUGIN_DIR SVG OUT_DIR
PLUGIN_DIR is the folder that holds imageformats/librsvgqt.so.
Writes OUT_DIR/qtsvg.png and OUT_DIR/rsvg.png and exits non-zero if a check fails.
"""
import os
import subprocess
import sys

RENDER = r"""
import sys
from PyQt6.QtGui import QGuiApplication, QImageReader
app = QGuiApplication(sys.argv)
r = QImageReader(sys.argv[1]); r.setFormat(b"svgz" if sys.argv[1].endswith(".svgz") else b"svg"); r.setScaledSize(__import__("PyQt6.QtCore", fromlist=["QSize"]).QSize(256, 256))
img = r.read()
if img.isNull(): sys.exit("read failed: " + r.errorString())
img.save(sys.argv[2])
paths = {l.split(maxsplit=5)[-1].strip() for l in open("/proc/self/maps") if len(l.split()) > 5}
plugin = sorted(p for p in paths if "svg" in p.rsplit("/", 1)[-1] and p.endswith(".so"))
print(", ".join(plugin))
"""


def render(svg, png, plugin_dir):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("QT_PLUGIN_PATH", None)
    if plugin_dir:
        env["QT_PLUGIN_PATH"] = plugin_dir
    res = subprocess.run([sys.executable, "-c", RENDER, svg, png], env=env, capture_output=True, text=True)
    if res.returncode:
        sys.exit(res.stderr)
    return res.stdout.strip()


def main():
    plugin_dir, svg, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    before, after = os.path.join(out, "qtsvg.png"), os.path.join(out, "rsvg.png")
    print("QtSvg render used:", render(svg, before, None))
    print("Plugin render used:", render(svg, after, plugin_dir))

    from PyQt6.QtGui import QGuiApplication, QImage
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QGuiApplication([])  # noqa: F841 (QImage needs a gui app for some formats)

    def alpha(path, x, y):
        return QImage(path).pixelColor(x, y).alpha()

    def distinct_colors(path, x0, y0, x1, y1):
        img = QImage(path)
        return len({img.pixel(x, y) for x in range(x0, x1) for y in range(y0, y1)})

    # At 256 px the folder spans x 28..228; its bottom edge is y 208. The drop shadow sits below it,
    # the paper grain makes the tab area (y 70..95) noisy instead of one flat colour.
    checks = [
        ("drop shadow under the folder", lambda p: alpha(p, 128, 222) > 40),
        ("paper grain on the tab", lambda p: distinct_colors(p, 40, 72, 90, 96) > 20),
    ]
    failed = False
    for name, check in checks:
        b, a = check(before), check(after)
        print(f"{name}: QtSvg={'yes' if b else 'no'} plugin={'yes' if a else 'no'}")
        failed |= b or not a
    print("PASS" if not failed else "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
