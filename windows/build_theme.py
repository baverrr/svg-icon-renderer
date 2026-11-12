"""Build a Windows icon theme for Windhawk's Resource Redirect mod from a KDE icon theme.

Needs, in this folder: icon-map.txt (imageres icon ID -> KDE icon), ico/ (rendered by fetch.sh and
render.py), empty.dll (compiled from empty.c) and imageres-dump/ (from dump_icons.py).
Writes:
  <theme dir>/imageres-<time>.dll  an empty DLL holding only the replacement icon groups
  <theme dir>/theme.ini            the redirection rules for Resource Redirect, naming that DLL
  verify-dump/<id>.ico (this folder)  each icon read back from the new DLL
  compare.png (this folder)        Windows' icon next to the new one, for each mapped ID
and deletes older imageres*.dll files in <theme dir> that nothing has open, so keep only built DLLs there.

The DLL is built in a temp file and checked icon by icon against the .ico files; only then are it and
theme.ini moved into place, so a failed build leaves the working theme alone. Each build gets a new DLL
name because Windows won't replace a DLL that Explorer has open.

Usage: .venv\\Scripts\\python.exe -I build_theme.py <theme dir>
"""
import ctypes, importlib.util, os, re, shutil, struct, sys, time
from ctypes import wintypes as wt
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
# python -I keeps this folder off sys.path, so load the sibling module by its full path.
_spec = importlib.util.spec_from_file_location("dump_icons", os.path.join(HERE, "dump_icons.py"))
_dump = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dump)
load, group_ids, group_to_ico = _dump.load, _dump.group_ids, _dump.group_to_ico
RT_ICON, RT_GROUP_ICON, LANG_NEUTRAL = 3, 14, 0
MAP_LINE = re.compile(r"^(\d+)\s+((?:places|devices|mimetypes|apps|actions|preferences|categories|status|emblems)"
                      r"/[\w.+-]+\.svg)(\s+overlay)?$")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.BeginUpdateResourceW.restype = wt.HANDLE
k32.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
k32.UpdateResourceW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.WORD, ctypes.c_void_p, wt.DWORD]
k32.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]
k32.FreeLibrary.argtypes = [wt.HMODULE]


def read_map():
    """[(id, rel)] from icon-map.txt, rel being "<context>/<name>.svg" with ":overlay" added for
    badge icons; exits naming the line if any line is wrong."""
    pairs, errors, seen = [], [], set()
    with open(os.path.join(HERE, "icon-map.txt"), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            text = line.split("#", 1)[0].strip()
            if not text:
                continue
            m = MAP_LINE.match(text)
            if not m:
                errors.append(f"line {n}: expected '<id> <context>/<name>.svg [overlay]', got {text!r}")
                continue
            gid, rel = int(m[1]), m[2] + (":overlay" if m[3] else "")
            if not os.path.exists(os.path.join(HERE, "imageres-dump", f"{gid}.ico")):
                errors.append(f"line {n}: {gid} is not an icon in imageres.dll")
            elif gid in seen:
                errors.append(f"line {n}: {gid} is listed twice")
            seen.add(gid)
            pairs.append((gid, rel))
    if errors:
        sys.exit("icon-map.txt:\n  " + "\n  ".join(errors))
    if not pairs:
        sys.exit("icon-map.txt has no icons in it")
    return pairs


def ico_path(rel):
    """ico/<context>_<name>.ico, or ico/<context>_<name>__overlay.ico (same naming as render.py)."""
    base, overlay = (rel[:-len(":overlay")], "__overlay") if rel.endswith(":overlay") else (rel, "")
    return os.path.join(HERE, "ico", base.replace("/", "_")[:-len(".svg")] + overlay + ".ico")


def short_name(rel):
    """'folder-music' from 'places/folder-music.svg', with ' (badge)' for overlays."""
    base = rel.split(":")[0].split("/")[1][:-len(".svg")]
    return base + (" (badge)" if rel.endswith(":overlay") else "")


def parse_ico(path):
    """[(header fields without size/offset, image bytes)] from a .ico file; raises if it's damaged."""
    data = open(path, "rb").read()
    if len(data) < 6:
        raise ValueError(f"{path}: too short to be an .ico")
    _, kind, count = struct.unpack_from("<HHH", data)
    if kind != 1 or count == 0 or len(data) < 6 + 16 * count:
        raise ValueError(f"{path}: not an .ico with images in it")
    out = []
    for i in range(count):
        w, h, cc, res, planes, bits, size, off = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        if size == 0 or off + size > len(data):
            raise ValueError(f"{path}: image {i} runs past the end of the file ({off}+{size} > {len(data)})")
        out.append(((w, h, cc, res, planes, bits), data[off:off + size]))
    return out


def update(handle, rtype, rid, payload):
    buf = ctypes.create_string_buffer(payload, len(payload))
    if not k32.UpdateResourceW(handle, rtype, rid, LANG_NEUTRAL, buf, len(payload)):
        raise ctypes.WinError(ctypes.get_last_error())


def build_dll(pairs, dll):
    shutil.copyfile(os.path.join(HERE, "empty.dll"), dll)
    h = k32.BeginUpdateResourceW(dll, True)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    next_icon_id, images_for = 1, {}
    try:
        for gid, rel in pairs:
            if rel not in images_for:  # each .ico's images are stored once and shared
                entries = []
                for fields, img in parse_ico(ico_path(rel)):
                    update(h, RT_ICON, next_icon_id, img)
                    entries.append((fields, len(img), next_icon_id))
                    next_icon_id += 1
                images_for[rel] = entries
            entries = images_for[rel]
            grp = struct.pack("<HHH", 0, 1, len(entries))
            for fields, size, iid in entries:
                grp += struct.pack("<BBBBHHIH", *fields, size, iid)
            update(h, RT_GROUP_ICON, gid, grp)
    except BaseException:
        k32.EndUpdateResourceW(h, True)  # discard the half-written changes
        raise
    if not k32.EndUpdateResourceW(h, False):
        raise ctypes.WinError(ctypes.get_last_error())
    return next_icon_id - 1


def verify_dll(pairs, dll):
    """Read the DLL back: same IDs as the map, and each group holds exactly its .ico's images."""
    h = load(dll)
    try:
        got = set(group_ids(h))
        want = {gid for gid, _ in pairs}
        if got != want:
            raise RuntimeError(f"DLL icon IDs differ from the map: extra {sorted(got - want)}, missing {sorted(want - got)}")
        for gid, rel in pairs:
            readback = os.path.join(HERE, "verify-dump", f"{gid}.ico")
            os.makedirs(os.path.dirname(readback), exist_ok=True)
            with open(readback, "wb") as f:
                f.write(group_to_ico(h, gid))
            if [img for _, img in parse_ico(readback)] != [img for _, img in parse_ico(ico_path(rel))]:
                raise RuntimeError(f"icon {gid} in the DLL doesn't match {ico_path(rel)}")
    finally:
        k32.FreeLibrary(h)


def compare_sheet(pairs, out):
    cols, cw, ch = 4, 230, 64
    rows = (len(pairs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (32, 32, 32, 255))
    d = ImageDraw.Draw(sheet)
    for n, (gid, rel) in enumerate(pairs):
        x, y = (n % cols) * cw, (n // cols) * ch
        win = Image.open(os.path.join(HERE, "imageres-dump", f"{gid}.ico"))
        win.size = (48, 48) if (48, 48) in win.info.get("sizes", ()) else max(win.info["sizes"])
        sheet.alpha_composite(win.convert("RGBA").resize((48, 48)), (x + 4, y + 8))
        man = Image.open(ico_path(rel))
        man.size = (48, 48)
        sheet.alpha_composite(man.convert("RGBA"), (x + 58, y + 8))
        d.text((x + 112, y + 14), str(gid), fill=(255, 220, 0, 255))
        d.text((x + 112, y + 32), short_name(rel)[:18], fill=(200, 200, 200, 255))
    sheet.save(out)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: .venv\\Scripts\\python.exe -I build_theme.py <theme dir>")
    theme = sys.argv[1]
    if not os.path.exists(os.path.join(HERE, "empty.dll")):
        sys.exit("empty.dll is missing: compile empty.c first (see the README)")
    pairs = read_map()
    wanted = {os.path.basename(ico_path(rel)) for _, rel in pairs}
    have = {f for f in os.listdir(os.path.join(HERE, "ico"))} if os.path.isdir(os.path.join(HERE, "ico")) else set()
    have = {f for f in have if f.endswith(".ico")}
    if wanted - have:
        sys.exit(f"no .ico rendered for: {sorted(wanted - have)} (run fetch.sh)")
    if have - wanted:  # fetch.sh read the map differently from read_map(), or ico/ is stale
        sys.exit(f"ico/ has icons the map doesn't name: {sorted(have - wanted)} (run fetch.sh)")
    os.makedirs(theme, exist_ok=True)
    # Each build gets its own DLL name, because Explorer keeps the one in use open and Windows won't
    # replace an open file. theme.ini is switched to the new name last; new processes pick it up at
    # once, Explorer after refresh-icons.cmd restarts it.
    name = "imageres-" + time.strftime("%Y%m%d-%H%M%S") + ".dll"
    dll, ini = os.path.join(theme, name), os.path.join(theme, "theme.ini")
    tmp_dll, tmp_ini = dll + ".new", ini + ".new"
    try:
        n = build_dll(pairs, tmp_dll)
        verify_dll(pairs, tmp_dll)
        with open(tmp_ini, "w", encoding="utf-8") as f:
            f.write("; Built by svg-icon-renderer's windows\\build_theme.py from a KDE icon theme.\n"
                    "; Icons the DLL doesn't have fall back to Windows' own.\n"
                    "[redirections]\n"
                    f"%SystemRoot%\\System32\\imageres.dll={name}\n"
                    f"%SystemRoot%\\SysWOW64\\imageres.dll={name}\n")
        compare_sheet(pairs, os.path.join(HERE, "compare.png"))
        os.replace(tmp_dll, dll)
        os.replace(tmp_ini, ini)
    finally:
        for leftover in (tmp_dll, tmp_ini):
            if os.path.exists(leftover):
                os.remove(leftover)
    # The new theme is live from here on; report that before cleaning up, so a cleanup problem can't hide it.
    print(f"{len(pairs)} icon groups, {n} images, checked against the .ico files -> {dll}")
    print("Run refresh-icons.cmd (Win+R) so Explorer loads the new icons; new programs already have them.")
    kept = []
    for old in os.listdir(theme):
        if old.lower().endswith(".dll") and old.startswith("imageres") and old != name:
            try:
                os.remove(os.path.join(theme, old))
            except OSError as e:  # usually still open in a running program; the next build retries
                kept.append(f"{old} ({e.strerror})")
    if kept:
        print(f"older builds not removed (the next build tries again): {', '.join(kept)}")


if __name__ == "__main__":
    main()
