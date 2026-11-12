"""Contact sheets of the imageres icons icon-map.txt doesn't cover yet, 60 per sheet, big labels.

Usage: .venv\\Scripts\\python.exe -I unmapped_sheet.py <out dir>
"""
import os, re, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "imageres-dump")
mapped = set()
for line in open(os.path.join(HERE, "icon-map.txt"), encoding="utf-8"):
    m = re.match(r"\s*(\d+)\s", line)
    if m:
        mapped.add(int(m[1]))
ids = sorted(int(f[:-4]) for f in os.listdir(DUMP) if f.endswith(".ico") and int(f[:-4]) not in mapped)
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
cols, cell, per = 10, 96, 60
for page in range(0, len(ids), per):
    chunk = ids[page:page + per]
    sheet = Image.new("RGBA", (cols * cell, ((len(chunk) + cols - 1) // cols) * cell), (60, 60, 60, 255))
    d = ImageDraw.Draw(sheet)
    for n, gid in enumerate(chunk):
        im = Image.open(os.path.join(DUMP, f"{gid}.ico"))
        sizes = im.info.get("sizes", {(48, 48)})
        im.size = (48, 48) if (48, 48) in sizes else max(sizes)
        x, y = (n % cols) * cell, (n // cols) * cell
        sheet.alpha_composite(im.convert("RGBA").resize((64, 64)), (x + 16, y + 4))
        d.text((x + 6, y + 74), str(gid), fill=(255, 230, 0, 255), font_size=16)
    path = os.path.join(out, f"unmapped-{page // per + 1}.png")
    sheet.save(path)
    print(path, chunk[0], "..", chunk[-1])
print(len(ids), "unmapped")
