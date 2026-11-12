"""Dump every numbered icon group in a Windows resource file as <id>.ico, plus a labeled contact sheet.

Usage: python -I dump_icons.py <resource file> <out dir> [max id on the sheet, default 400 [min id, default 0]]
Exits 1 if any icon group can't be read or drawn.
"""
import ctypes, struct, sys, os
from ctypes import wintypes as wt
from PIL import Image, ImageDraw

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = wt.HMODULE
k32.LoadLibraryExW.argtypes = [wt.LPCWSTR, wt.HANDLE, wt.DWORD]
k32.FreeLibrary.argtypes = [wt.HMODULE]
k32.FindResourceW.restype = wt.HANDLE
k32.FindResourceW.argtypes = [wt.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
k32.LoadResource.restype = wt.HANDLE
k32.LoadResource.argtypes = [wt.HMODULE, wt.HANDLE]
k32.LockResource.restype = ctypes.c_void_p
k32.LockResource.argtypes = [wt.HANDLE]
k32.SizeofResource.restype = wt.DWORD
k32.SizeofResource.argtypes = [wt.HMODULE, wt.HANDLE]
ENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
k32.EnumResourceNamesW.argtypes = [wt.HMODULE, ctypes.c_void_p, ENUMPROC, ctypes.c_void_p]

RT_ICON, RT_GROUP_ICON = 3, 14
AS_DATA = 0x00000002 | 0x00000020  # LOAD_LIBRARY_AS_DATAFILE | AS_IMAGE_RESOURCE


def load(path):
    h = k32.LoadLibraryExW(path, None, AS_DATA)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error(), f"can't load {path}")
    return h


def raw(h, name, rtype, what):
    """The bytes of one resource; raises LookupError naming `what` if it isn't there."""
    r = k32.FindResourceW(h, name, rtype)
    if not r:
        raise LookupError(f"{what} not found")
    hg = k32.LoadResource(h, r)
    p = k32.LockResource(hg) if hg else None
    if not p:
        raise ctypes.WinError(ctypes.get_last_error(), f"can't load {what}")
    return ctypes.string_at(p, k32.SizeofResource(h, r))


def group_ids(h):
    ids = []

    @ENUMPROC
    def cb(hm, t, name, lp):
        if name < 0x10000:  # numeric IDs only; string-named groups are skipped
            ids.append(name)
        return True

    if not k32.EnumResourceNamesW(h, RT_GROUP_ICON, cb, None):
        raise ctypes.WinError(ctypes.get_last_error(), "no icon groups")
    return sorted(ids)


def group_to_ico(h, gid):
    """Rebuild a standalone .ico file from icon group `gid` and the RT_ICON images it points to."""
    grp = raw(h, gid, RT_GROUP_ICON, f"icon group {gid}")
    _, _, count = struct.unpack_from("<HHH", grp)
    entries, images = [], []
    for i in range(count):
        w, hh, cc, res, planes, bits, size, iid = struct.unpack_from("<BBBBHHIH", grp, 6 + i * 14)
        img = raw(h, iid, RT_ICON, f"image {iid} of icon group {gid}")
        entries.append((w, hh, cc, res, planes, bits, len(img)))
        images.append(img)
    out = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    for e, img in zip(entries, images):
        out += struct.pack("<BBBBHHII", *e, offset)
        offset += len(img)
    return out + b"".join(images)


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    sheet_max = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    sheet_min = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    os.makedirs(outdir, exist_ok=True)
    h = load(src)
    ids = group_ids(h)
    thumbs, failed = [], []
    for gid in ids:
        path = os.path.join(outdir, f"{gid}.ico")
        try:
            with open(path, "wb") as f:
                f.write(group_to_ico(h, gid))
            if sheet_min <= gid <= sheet_max:
                im = Image.open(path)
                im.size = max(im.info.get("sizes", {(48, 48)}), key=lambda s: s[0] if s[0] <= 64 else 0)
                thumbs.append((gid, im.convert("RGBA").resize((48, 48))))
        except (OSError, ValueError, LookupError, SyntaxError) as e:
            failed.append(gid)
            print(f"icon group {gid}: {e}", file=sys.stderr)
    k32.FreeLibrary(h)
    print(f"{len(ids) - len(failed)} of {len(ids)} icon groups dumped; ids {ids[0]}..{ids[-1]}")
    if thumbs:
        cols, cell = 16, 72
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * cell, rows * cell), (40, 40, 40, 255))
        d = ImageDraw.Draw(sheet)
        for n, (gid, im) in enumerate(thumbs):
            x, y = (n % cols) * cell, (n // cols) * cell
            sheet.alpha_composite(im, (x + 12, y + 2))
            d.text((x + 4, y + 54), str(gid), fill=(255, 255, 0, 255))
        sheet.save(os.path.join(outdir, "_sheet.png"))
    else:
        print(f"no icon groups between {sheet_min} and {sheet_max}; no sheet made")
    if failed:
        sys.exit(f"failed icon groups: {failed}")


if __name__ == "__main__":
    main()
