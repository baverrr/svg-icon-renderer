#!/usr/bin/env python3
"""Robustness and speed check for the plugin, run against every SVG under a folder.

Usage: python3 stress.py PLUGIN_DIR [ICON_DIR]   (ICON_DIR defaults to /usr/share/icons)
Renders each file at 64 px on 8 threads with the plugin, then times QtSvg vs the plugin on the
same files, and feeds the plugin broken input. A crash ends the process, so reaching the end is the test.
"""
import os
import subprocess
import sys

WORKER = r"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import QBuffer, QByteArray, QSize, QIODevice
from PyQt6.QtGui import QGuiApplication, QImageReader
app = QGuiApplication(sys.argv)
files = sys.stdin.read().split("\n")
threads = int(sys.argv[1])

def load(path):
    r = QImageReader(path)
    r.setFormat(b"svgz" if path.endswith(".svgz") else b"svg")
    r.setScaledSize(QSize(64, 64))
    return not r.read().isNull()

t = time.perf_counter()
with ThreadPoolExecutor(threads) as ex:
    ok = sum(ex.map(load, files))
print(f"{ok}/{len(files)} rendered in {time.perf_counter() - t:.2f}s on {threads} threads")

if threads > 1:
    bad = [b"", b"<svg", b"not an svg at all", b"\x1f\x8b\x08garbage", b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='1e9' height='1e9'/></svg>",
           b"<svg xmlns='http://www.w3.org/2000/svg' width='0' height='0'/>",
           b"<svg xmlns='http://www.w3.org/2000/svg' width='100000' height='100000'><rect width='10' height='10'/></svg>",
           b"<!DOCTYPE svg [<!ENTITY a 'aaaaaaaaaa'><!ENTITY b '&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;'><!ENTITY c '&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;'><!ENTITY d '&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;'><!ENTITY e '&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;'><!ENTITY f '&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;'>]><svg xmlns='http://www.w3.org/2000/svg'><text>&f;&f;&f;&f;&f;&f;&f;&f;</text></svg>",
           b"<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='8' height='8'><image xlink:href='file:///etc/passwd' width='8' height='8'/></svg>"]
    for i, data in enumerate(bad):
        buf = QBuffer(); buf.setData(QByteArray(data)); buf.open(QIODevice.OpenModeFlag.ReadOnly)
        r = QImageReader(buf, b"svg")
        img = r.read()
        print(f"bad input {i}: {'image ' + str(img.width()) + 'x' + str(img.height()) if not img.isNull() else 'rejected'}")
"""


def run(files, plugin_dir, threads):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_LOGGING_RULES="rsvgqt.warning=false")
    env.pop("QT_PLUGIN_PATH", None)
    if plugin_dir:
        env["QT_PLUGIN_PATH"] = plugin_dir
    res = subprocess.run([sys.executable, "-c", WORKER, str(threads)],
                         input="\n".join(files), env=env, capture_output=True, text=True)
    out = res.stdout.strip()
    if res.returncode:
        out += f"\nEXITED WITH {res.returncode}\n" + res.stderr[-2000:]
    return out


def main():
    plugin_dir = os.path.abspath(sys.argv[1])
    icon_dir = sys.argv[2] if len(sys.argv) > 2 else "/usr/share/icons"
    files = [os.path.join(d, f) for d, _, fs in os.walk(icon_dir) for f in fs
             if f.endswith((".svg", ".svgz")) and os.path.isfile(os.path.join(d, f))]
    print(f"{len(files)} SVG files under {icon_dir}")
    print("plugin, 8 threads + bad input:\n" + run(files, plugin_dir, 8))
    sample = files[:3000]
    print("QtSvg,  1 thread (first 3000):", run(sample, None, 1))
    print("plugin, 1 thread (first 3000):", run(sample, plugin_dir, 1))


if __name__ == "__main__":
    main()
