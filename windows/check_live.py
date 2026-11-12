"""Check that the Resource Redirect theme serves the right icon for every imageres.dll icon ID.

For each ID it loads the icon through shell32's ExtractIconExW (which Resource Redirect hooks in
this process), at Windows' large and small icon sizes, and compares it with:
  - the icon icon-map.txt names for that ID (from ico/), and
  - Windows' original (from imageres-dump/, dumped before the theme was on).
A mapped ID passes when the live icon matches its themed icon and not the Windows one; an unmapped
ID passes when it still matches Windows. Every icon is drawn the same way onto the same grey
background, so frame choice, scaling and transparency are identical on all sides.

This proves the redirect inside this process. Explorer can still show old icons from its icon cache
until refresh-icons.cmd runs.

Usage: .venv\\Scripts\\python.exe -I check_live.py <out.png>
Exits 1 and lists the IDs if any icon is wrong. <out.png> shows Windows | theme | live for each mapped ID.
"""
import ctypes, importlib.util, os, sys
from ctypes import wintypes as wt
from PIL import Image, ImageChops, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("build_theme", os.path.join(HERE, "build_theme.py"))
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)  # its main() only runs when it is the script started
read_map, ico_path = _build.read_map, _build.ico_path

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32.ExtractIconExW.restype = wt.UINT
shell32.ExtractIconExW.argtypes = [wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.HICON), ctypes.POINTER(wt.HICON), wt.UINT]
user32.DestroyIcon.argtypes = [wt.HICON]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.DrawIconEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, wt.HICON, ctypes.c_int, ctypes.c_int, wt.UINT, wt.HBRUSH, wt.UINT]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]

IMAGERES = os.path.expandvars(r"%SystemRoot%\System32\imageres.dll")
LARGE, SMALL = user32.GetSystemMetrics(11), user32.GetSystemMetrics(49)  # SM_CXICON, SM_CXSMICON
GREY = 0x40  # background every icon is drawn onto, so transparency can't hide a difference
TOL = 16  # a pixel counts as changed when any channel differs by more than this (0-255)
# Drawn the same way, the live icon and its source .ico match with 0 changed pixels (measured
# 2026-11-12); a plain folder and a Music folder (Manila-Folders) differ by 11 pixels at 16 px.
# So "same icon" means no changed pixels at all. Limit: two different SVGs that draw identically at
# 32 and 16 px (Manila's drive-harddisk and drive-harddisk-system do) can't be told apart here.


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


if ctypes.sizeof(BITMAPINFOHEADER) != 40:  # a real check, not assert: python -O drops asserts
    raise RuntimeError(f"BITMAPINFOHEADER is {ctypes.sizeof(BITMAPINFOHEADER)} bytes, expected 40")


def extract(path, index):
    """(large, small) HICONs; a negative index is a resource ID, as in 'imageres.dll,-3' icon paths."""
    large, small = wt.HICON(), wt.HICON()
    n = shell32.ExtractIconExW(path, index, ctypes.byref(large), ctypes.byref(small), 1)
    if n == 0 or n == 0xFFFFFFFF or not large or not small:
        for h in (large, small):
            if h:
                user32.DestroyIcon(h)
        raise LookupError(f"no icon {index} in {path}")
    return large, small


def draw(hicon, size):
    """The icon drawn at size x size onto solid grey, as an RGB image."""
    bmi = BITMAPINFOHEADER(40, size, -size, 1, 32, 0)  # top-down 32-bit
    bits = ctypes.c_void_p()
    dc = gdi32.CreateCompatibleDC(None)
    if not dc:
        raise ctypes.WinError(ctypes.get_last_error())
    bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not bmp or not bits:
        gdi32.DeleteDC(dc)
        raise ctypes.WinError(ctypes.get_last_error())
    old = gdi32.SelectObject(dc, bmp)
    try:
        ctypes.memset(bits, GREY, size * size * 4)
        if not user32.DrawIconEx(dc, 0, 0, hicon, size, size, 0, None, 3):  # DI_NORMAL
            raise ctypes.WinError(ctypes.get_last_error())
        raw = ctypes.string_at(bits, size * size * 4)
        return Image.frombuffer("RGB", (size, size), raw, "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)


def drawings(path, index):
    """{size: image} for the large and small icon at path/index."""
    large, small = extract(path, index)
    try:
        return {LARGE: draw(large, LARGE), SMALL: draw(small, SMALL)}
    finally:
        user32.DestroyIcon(large)
        user32.DestroyIcon(small)


def changed(a, b):
    """How many pixels differ by more than TOL in any channel."""
    r, g, bl = ImageChops.difference(a, b).split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    return sum(worst.histogram()[TOL + 1:])


def blank(im):
    """True if almost nothing was drawn over the grey background."""
    return changed(im, Image.new("RGB", im.size, (GREY, GREY, GREY))) < im.width * im.height // 20


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: .venv\\Scripts\\python.exe -I check_live.py <out.png>")
    out = sys.argv[1]
    mapped = dict(read_map())
    all_ids = sorted(int(f[:-4]) for f in os.listdir(os.path.join(HERE, "imageres-dump")) if f.endswith(".ico"))
    problems, rows = [], []
    for gid in all_ids:
        try:
            live = drawings(IMAGERES, -gid)
            win = drawings(os.path.join(HERE, "imageres-dump", f"{gid}.ico"), 0)
            man = drawings(ico_path(mapped[gid]), 0) if gid in mapped else None
        except (OSError, LookupError) as e:
            problems.append(f"{gid}: {e}")
            continue
        for size in (LARGE, SMALL):
            expected = win[size] if man is None else man[size]
            if blank(live[size]) and not blank(expected):
                problems.append(f"{gid} @{size}px: live icon drew as blank")
                continue
            c_win = changed(live[size], win[size])
            if man is None:
                if c_win:
                    problems.append(f"{gid} @{size}px: not in the map but no longer Windows' icon ({c_win} pixels differ)")
                continue
            c_man, c_ref = changed(live[size], man[size]), changed(man[size], win[size])
            if c_ref == 0:
                problems.append(f"{gid} @{size}px: themed and Windows icons look the same, so this proves nothing")
            elif c_man:
                problems.append(f"{gid} @{size}px: live icon isn't {mapped[gid]} ({c_man} pixels differ; {c_win} from Windows')")
        if man is not None:
            rows.append((gid, mapped[gid], win[LARGE], man[LARGE], live[LARGE]))

    cell, label = LARGE + 8, 150
    sheet = Image.new("RGB", (2 * (3 * cell + label), ((len(rows) + 1) // 2) * cell), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for n, (gid, rel, win, man, live) in enumerate(rows):
        x, y = (n % 2) * (3 * cell + label), (n // 2) * cell
        for k, im in enumerate((win, man, live)):
            sheet.paste(im, (x + 4 + k * cell, y + 4))
        d.text((x + 3 * cell + 6, y + 4), str(gid), fill=(255, 220, 0))
        d.text((x + 3 * cell + 6, y + 18), _build.short_name(rel)[:22], fill=(200, 200, 200))
    sheet.save(out)

    checked = len(all_ids) * 2
    print(f"{len(all_ids)} icon IDs ({len(mapped)} mapped, {len(all_ids) - len(mapped)} unmapped) at {LARGE}px and {SMALL}px: "
          f"{checked} checks, {len(problems)} problems. Sheet (Windows | theme | live): {out}")
    if problems:
        sys.exit("Problems:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
