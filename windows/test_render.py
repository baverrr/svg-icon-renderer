#!/usr/bin/env python3
"""Tests for render.py's icon lookup and rendering, with small made-up themes. Linux only.

Builds fixture themes under a temporary HOME (render.py looks in ~/.local/share/icons first), runs
render.py on them and checks which SVG it picked (its "USES" lines), its exit codes, and the overlay
geometry of the .ico it makes. Needs rsvg-convert and ImageMagick 7, like render.py.

Usage: python3 windows/test_render.py
"""
import io, os, subprocess, sys, tarfile, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "render.py")
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
       '<rect width="16" height="16" fill="#c08040"/></svg>')
failures = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def theme(home, name, dirs, inherits="", scaled=()):
    """dirs: {subdir: (context, size, type, scale)}; writes index.theme only."""
    d = os.path.join(home, ".local", "share", "icons", name)
    os.makedirs(d, exist_ok=True)
    plain = [s for s in dirs if s not in scaled]
    lines = ["[Icon Theme]", f"Name={name}", "Directories=" + ",".join(plain)]
    if scaled:
        lines.append("ScaledDirectories=" + ",".join(scaled))
    if inherits:
        lines.append("Inherits=" + inherits)
    for sub, (ctx, size, kind, scale) in dirs.items():
        lines += ["", f"[{sub}]", f"Context={ctx}", f"Size={size}", f"Type={kind}", f"Scale={scale}"]
    with open(os.path.join(d, "index.theme"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return d


def icon(theme_dir, sub, name):
    os.makedirs(os.path.join(theme_dir, sub), exist_ok=True)
    with open(os.path.join(theme_dir, sub, name), "w") as f:
        f.write(SVG)


def render(home, theme_name, *args, timeout=60):
    env = dict(os.environ, HOME=home)
    p = subprocess.run([sys.executable, RENDER, "--theme", theme_name, *args], env=env,
                       capture_output=True, timeout=timeout)
    uses = {l.split(" ", 2)[1]: l.split(" ", 2)[2] for l in p.stderr.decode().splitlines() if l.startswith("USES ")}
    return p.returncode, p.stdout, uses, p.stderr.decode()


def magick(*args):
    return subprocess.run(["magick", *args], capture_output=True, text=True, check=True).stdout.strip()


def main():
    with tempfile.TemporaryDirectory() as home:
        # Inherits: T1 -> T2 -> (T4, T1 again: a loop), T1 -> T3. Depth first means T4 before T3.
        t1 = theme(home, "TestT1", {"16/places": ("Places", 16, "Fixed", 1)}, inherits="TestT2,TestT3")
        t2 = theme(home, "TestT2", {"16/places": ("Places", 16, "Fixed", 1)}, inherits="TestT4,TestT1")
        t3 = theme(home, "TestT3", {"16/places": ("Places", 16, "Fixed", 1)})
        t4 = theme(home, "TestT4", {"16/places": ("Places", 16, "Fixed", 1)})
        hc = theme(home, "hicolor", {"16/places": ("Places", 16, "Fixed", 1)})
        icon(t4, "16/places", "depth.svg"); icon(t3, "16/places", "depth.svg")
        icon(hc, "16/places", "only-hicolor.svg")
        icon(t1, "16/places", "first-wins.svg")
        t2s = theme(home, "TestT2", {"16/places": ("Places", 16, "Fixed", 1), "scalable/places": ("Places", 16, "Scalable", 1)},
                    inherits="TestT4,TestT1")
        icon(t2s, "scalable/places", "first-wins.svg")
        rc, out, uses, err = render(home, "TestT1", "places/depth.svg", "places/only-hicolor.svg", "places/first-wins.svg", timeout=30)
        check("inherits loop finishes", rc == 0, err)
        check("inherits depth first (T4 before T3)", "/TestT4/" in uses.get("places/depth.svg", ""), uses)
        check("hicolor is searched last", "/hicolor/" in uses.get("places/only-hicolor.svg", ""), uses)
        check("first theme with the name wins over a bigger copy in a parent", "/TestT1/" in uses.get("places/first-wins.svg", ""), uses)

        # Ranking inside one theme: scalable > largest Size*Scale > matching Context. Symbolic and
        # folders without their own section are never used.
        r = theme(home, "TestRank", {
            "48/places": ("Places", 48, "Fixed", 1),
            "32@2x/places": ("Places", 32, "Fixed", 2),
            "scalable/places": ("Places", 16, "Scalable", 1),
            "64/status": ("Status", 64, "Fixed", 1),
            "64/places": ("Places", 64, "Fixed", 1),
            "512/symbolic": ("Places", 512, "Fixed", 1),
        }, scaled=("32@2x/places",))
        # A folder listed in Directories but with no section of its own.
        idx = open(os.path.join(r, "index.theme")).read().replace("Directories=", "Directories=999/nosection,", 1)
        open(os.path.join(r, "index.theme"), "w").write(idx)
        for sub in ("48/places", "32@2x/places", "scalable/places"):
            icon(r, sub, "rank.svg")
        for sub in ("48/places", "32@2x/places"):
            icon(r, sub, "scale.svg")
        for sub in ("64/status", "64/places"):
            icon(r, sub, "ctx.svg")
        for sub in ("512/symbolic", "999/nosection", "48/places"):
            icon(r, sub, "skip.svg")
        rc, out, uses, err = render(home, "TestRank", "places/rank.svg", "places/scale.svg", "places/ctx.svg", "places/skip.svg")
        check("rank: render ran", rc == 0, err)
        check("rank: scalable wins", "/scalable/places/" in uses.get("places/rank.svg", ""), uses)
        check("rank: 32@2x (64 px) beats 48", "/32@2x/places/" in uses.get("places/scale.svg", ""), uses)
        check("rank: same size, matching Context wins", "/64/places/" in uses.get("places/ctx.svg", ""), uses)
        check("rank: symbolic and section-less folders skipped", "/48/places/" in uses.get("places/skip.svg", ""), uses)

        # Overlay geometry and the 10 frames.
        rc, out, uses, err = render(home, "TestRank", "places/rank.svg", "places/rank.svg:overlay")
        check("overlay: render ran", rc == 0 and out, err)
        if rc == 0 and out:
            tdir = os.path.join(home, "out")
            with tarfile.open(fileobj=io.BytesIO(out)) as tar:
                tar.extractall(tdir, filter="data")
            want = "256 128 96 64 48 40 32 24 20 16"
            for name in ("places_rank.ico", "places_rank__overlay.ico"):
                sizes = magick("identify", "-format", "%w ", os.path.join(tdir, name)).strip()
                check(f"{name}: 10 sizes", sizes == want, sizes)
            ov = os.path.join(tdir, "places_rank__overlay.ico")
            for i in range(10):
                tr = magick(f"{ov}[{i}]", "-gravity", "northeast", "-crop", "50%x50%+0+0", "+repage", "-format", "%[fx:maxima.a]", "info:")
                bl = magick(f"{ov}[{i}]", "-gravity", "southwest", "-crop", "50%x50%+0+0", "+repage", "-format", "%[fx:maxima.a]", "info:")
                check(f"overlay frame {i}: top-right empty, bottom-left drawn", float(tr) == 0 and float(bl) > 0, f"tr={tr} bl={bl}")

        # Failures: a missing icon among good ones -> exit 3 and no tar; unknown theme; bad argument.
        rc, out, _, _ = render(home, "TestRank", "places/rank.svg", "places/no-such.svg")
        check("missing icon: exit 3 and nothing on stdout", rc == 3 and not out, f"rc={rc} bytes={len(out)}")
        rc, out, _, _ = render(home, "NoSuchTheme", "places/rank.svg")
        check("unknown theme: fails, nothing on stdout", rc != 0 and not out, f"rc={rc}")
        rc, out, _, _ = render(home, "TestRank", "foo/bar.svg")
        check("bad argument: fails, nothing on stdout", rc != 0 and not out, f"rc={rc}")
        # Sizes written as "48.0" still count; a folder whose Size can't be read is skipped with a warning.
        odd = theme(home, "TestOddSize", {"x/places": ("Places", "48.0", "Fixed", 1), "y/places": ("Places", "big", "Fixed", 1)})
        icon(odd, "x/places", "a.svg"); icon(odd, "y/places", "b.svg")
        rc, out, uses, err = render(home, "TestOddSize", "places/a.svg")
        check('Size="48.0" is read as 48', rc == 0 and "/x/places/" in uses.get("places/a.svg", ""), err[-300:])
        rc, out, _, err = render(home, "TestOddSize", "places/b.svg")
        check("unreadable Size: folder skipped with a warning, no traceback",
              rc == 3 and "Traceback" not in err and "WARNING TestOddSize: folder y/places" in err and not out, err[-300:])
        # Two scalable folders: the one with the bigger MaxSize wins.
        two = theme(home, "TestTwoScalable", {"small/places": ("Places", 16, "Scalable", 1),
                                              "big/places": ("Places", 16, "Scalable", 1)})
        idx = open(os.path.join(two, "index.theme")).read()
        idx = idx.replace("[small/places]", "[small/places]\nMaxSize=16").replace("[big/places]", "[big/places]\nMaxSize=256")
        open(os.path.join(two, "index.theme"), "w").write(idx)
        icon(two, "small/places", "s.svg"); icon(two, "big/places", "s.svg")
        rc, out, uses, err = render(home, "TestTwoScalable", "places/s.svg")
        check("two scalable folders: bigger MaxSize wins", "/big/places/" in uses.get("places/s.svg", ""), err[-300:])

        # An inherited theme that isn't installed: a warning, and the render goes on.
        lone = theme(home, "TestLone", {"16/places": ("Places", 16, "Fixed", 1)}, inherits="NotInstalledTheme")
        icon(lone, "16/places", "l.svg")
        rc, out, uses, err = render(home, "TestLone", "places/l.svg")
        check("missing inherited theme: warned, still renders",
              rc == 0 and "WARNING inherited theme 'NotInstalledTheme' is not installed" in err, err[-300:])

        # An index.theme without [Icon Theme] stops the render with a clear message, no traceback.
        broken = os.path.join(home, ".local", "share", "icons", "TestBroken")
        os.makedirs(os.path.join(broken, "16/places"))
        open(os.path.join(broken, "index.theme"), "w").write("[16/places]\nSize=16\n")
        icon(broken, "16/places", "b.svg")
        rc, out, uses, err = render(home, "TestBroken", "places/b.svg")
        check("index.theme without [Icon Theme]: clear error, nothing on stdout",
              rc == 1 and "no [Icon Theme] section" in err and "Traceback" not in err and not out, err[-300:])
    print(f"{len(failures)} failed" if failures else "all passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
