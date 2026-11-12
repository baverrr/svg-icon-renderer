#!/usr/bin/env python3
"""Render KDE / freedesktop icons to Windows .ico files, for build_theme.py.

Runs on the Linux machine that has the icon theme (fetch.sh sends it over ssh, or run it there yourself):

    python3 render.py --theme Manila-Folders places/folder.svg emblems/emblem-shared.svg:overlay ... > icons.tgz

Each argument is "<context>/<name>.svg" as written in icon-map.txt; ":overlay" draws the icon at half size in
the bottom-left corner of an empty canvas, like a Windows badge. For each icon it finds the SVG file
(see find_icon), renders 10 sizes with rsvg-convert and packs them into one .ico with ImageMagick, plus a
48 px .preview.png. A tar.gz of all of them goes to stdout.

stderr gets one "USES <arg> <file>" line per icon, "MISSING <arg>" for icons it can't find, and any
warnings from the tools. Exits 3 if any icon is missing, 2 on bad arguments, 1 on any other error. Needs rsvg-convert
(librsvg2-bin) and ImageMagick 7 (`magick`).
"""
import argparse, configparser, functools, io, os, re, subprocess, sys, tarfile, tempfile

SIZES = (256, 128, 96, 64, 48, 40, 32, 24, 20, 16)
ARG = re.compile(r"^(places|devices|mimetypes|apps|actions|preferences|categories|status|emblems)/[\w.+-]+\.svg(:overlay)?$")
# icon-map.txt contexts -> the Context= names themes use in index.theme
CONTEXTS = {"places": "places", "devices": "devices", "mimetypes": "mimetypes", "apps": "applications",
            "actions": "actions", "preferences": "preferences", "categories": "categories",
            "status": "status", "emblems": "emblems"}
SEARCH = [os.path.expanduser("~/.local/share/icons"), os.path.expanduser("~/.icons"), "/usr/local/share/icons", "/usr/share/icons"]


def theme_dir(name):
    for base in SEARCH:
        d = os.path.join(base, name)
        if os.path.isfile(os.path.join(d, "index.theme")):
            return d
    return None


def number(text):
    """An index.theme size or scale as a whole number ("48" and "48.0" both give 48), or None."""
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


@functools.lru_cache(maxsize=None)
def read_theme(name):
    """(dir, [(subdir, context, pixels)], [inherited theme names]) from a theme's index.theme, or None
    if the theme isn't installed. An index.theme that can't be read stops the render (RuntimeError):
    skipping it would quietly take icons from a later theme. Folders with an unreadable size are
    skipped with a WARNING line."""
    d = theme_dir(name)
    if d is None:
        return None
    path = os.path.join(d, "index.theme")
    ini = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        read_ok = ini.read(path, encoding="utf-8-sig")  # -sig: a byte order mark at the start is fine
    except (configparser.Error, UnicodeDecodeError) as e:
        raise RuntimeError(f"{path}: can't be read ({e})") from e
    if not read_ok or not ini.has_section("Icon Theme"):
        raise RuntimeError(f"{path}: can't be opened, or has no [Icon Theme] section")
    top = ini["Icon Theme"]
    dirs = []
    for sub in [s.strip() for s in (top.get("Directories", "") + "," + top.get("ScaledDirectories", "")).split(",") if s.strip()]:
        if "symbolic" in sub or not ini.has_section(sub):
            continue
        sec = ini[sub]
        if sec.get("Type", "Threshold").strip().lower() == "scalable":
            # Drawn at any size, so it beats every fixed size; between two scalable folders, the one
            # meant for bigger sizes (MaxSize) wins.
            pixels = 4096 + (number(sec.get("MaxSize")) or 0)
        else:
            size, scale = number(sec.get("Size")), number(sec.get("Scale", "1"))
            if not size or not scale:
                print(f"WARNING {name}: folder {sub} has Size={sec.get('Size')!r} Scale={sec.get('Scale', '1')!r}; skipping it",
                      file=sys.stderr)
                continue
            pixels = size * scale
        dirs.append((sub, sec.get("Context", "").strip().lower(), pixels))
    inherits = [s.strip() for s in top.get("Inherits", "").split(",") if s.strip()]
    return d, dirs, inherits


def theme_chain(name):
    """The theme, then everything it inherits from (depth first, each once), then hicolor, as KDE looks."""
    order, todo = [], [name]
    while todo:
        t = todo.pop(0)
        if t in order:
            continue
        order.append(t)
        info = read_theme(t)
        if info:
            todo = info[2] + todo
        elif t != "hicolor" and t != name:  # main() has already checked the theme itself
            print(f"WARNING inherited theme {t!r} is not installed; icons it would give come from later themes",
                  file=sys.stderr)
    if "hicolor" not in order:
        order.append("hicolor")
    return order


def find_icon(chain, rel):
    """The SVG file for "<context>/<name>.svg": the first theme in the chain that has the name, as KDE
    does. Within that theme, the folder KDE would pick for a large icon: scalable first, then the largest
    size; the Context matching <context> only breaks ties. Symbolic folders are skipped."""
    ctx, file = rel.split("/", 1)
    want = CONTEXTS[ctx]
    for t in chain:
        info = read_theme(t)
        if not info:
            continue
        d, dirs, _ = info
        hits = [(px, c == want, os.path.join(d, sub, file)) for sub, c, px in dirs if os.path.isfile(os.path.join(d, sub, file))]
        if hits:
            hits.sort(key=lambda h: (h[0], h[1]), reverse=True)
            return hits[0][2]
    return None


def run(cmd):
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({p.returncode}): {p.stderr.strip()}")
    if p.stderr.strip():
        print(f"WARNING {cmd[0]}: {p.stderr.strip()}", file=sys.stderr)


def render(svg, overlay, work, name):
    pngs = []
    for s in SIZES:
        png = os.path.join(work, f"{name}-{s}.png")
        if overlay:
            e = max(8, s // 2)
            small = os.path.join(work, f"{name}-{s}-badge.png")
            run(["rsvg-convert", "-w", str(e), "-h", str(e), svg, "-o", small])
            run(["magick", "-size", f"{s}x{s}", "xc:none", small, "-gravity", "southwest", "-composite", "PNG32:" + png])
        else:
            run(["rsvg-convert", "-w", str(s), "-h", str(s), svg, "-o", png])
        pngs.append(png)
    ico = os.path.join(work, name + ".ico")
    run(["magick", *pngs, ico])
    return ico, os.path.join(work, f"{name}-48.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--theme", required=True, help="icon theme folder name, e.g. Manila-Folders")
    ap.add_argument("icons", nargs="+", help='"<context>/<name>.svg", optionally with ":overlay"')
    a = ap.parse_args()
    bad = [i for i in a.icons if not ARG.match(i)]
    if bad:
        sys.exit(f"not '<context>/<name>.svg[:overlay]': {bad}")
    if theme_dir(a.theme) is None:
        sys.exit(f"icon theme {a.theme!r} not found in {SEARCH}")
    chain = theme_chain(a.theme)
    missing, buf = 0, io.BytesIO()
    with tempfile.TemporaryDirectory() as work, tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for arg in a.icons:
            rel, overlay = (arg[:-len(":overlay")], True) if arg.endswith(":overlay") else (arg, False)
            svg = find_icon(chain, rel)
            if svg is None:
                print(f"MISSING {arg}", file=sys.stderr)
                missing += 1
                continue
            print(f"USES {arg} {svg.replace(os.path.expanduser('~'), '~', 1)}", file=sys.stderr)
            name = rel.replace("/", "_")[:-len(".svg")] + ("__overlay" if overlay else "")
            ico, preview = render(svg, overlay, work, name)
            tar.add(ico, arcname=name + ".ico")
            tar.add(preview, arcname=name + ".preview.png")
    if missing:
        sys.exit(3)
    sys.stdout.buffer.write(buf.getvalue())


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        sys.exit(str(e))
