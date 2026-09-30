"""
Turns the transparent top-down render (07_overview.png) into a labelled map:
dark background, 10 m grid, area names (English + Hebrew), every FiveM ore spot
and station, legend and scale bar.

    pip install pillow bpy==4.2.0
    python label_overview.py previews/07_overview.png previews/07_overview_map.jpg
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont, features

sys.argv, args = sys.argv[:1], sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cave_mine_generator as g  # noqa: E402

src, dst = args[0], args[1]
lo, hi = g.grid_bounds()
CX, CY = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
SCALE = max(hi.x - lo.x, hi.y - lo.y) + 4          # same as the overview camera

img = Image.open(src).convert('RGBA')
N = img.size[0]
UP = 2
W = N * UP
px_per_m = W / SCALE
bg = Image.new('RGBA', (W, W), (18, 20, 26, 255))
d = ImageDraw.Draw(bg)
for k in range(-20, 21):
    x = W / 2 + (k * 10 - (CX % 10)) * px_per_m
    y = W / 2 + (k * 10 - (CY % 10)) * px_per_m
    d.line([(x, 0), (x, W)], fill=(30, 33, 42, 255), width=1)
    d.line([(0, y), (W, y)], fill=(30, 33, 42, 255), width=1)
bg.alpha_composite(img.resize((W, W), Image.LANCZOS))
d = ImageDraw.Draw(bg)

RAQM = features.check('raqm')
FONT_DIR = '/usr/share/fonts/truetype/dejavu/'


def he(text):
    return text if RAQM else text[::-1]


def font(bold, size):
    try:
        return ImageFont.truetype(FONT_DIR + ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)
    except OSError:
        return ImageFont.load_default()


def to_px(x, y):
    p = g.local(x, y)
    return (W / 2 + (p.x - CX) * px_per_m, W / 2 - (p.y - CY) * px_per_m)


big, small, title = font(True, 26), font(False, 19), font(True, 34)

for x, y, _ in g.ORE_SPOTS:
    px, py = to_px(x, y)
    d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(255, 190, 60, 255), outline=(40, 30, 10, 255), width=2)
stations = [(g.SMELTER, (255, 110, 40))] + [(b, (120, 200, 255)) for b in g.CRACK_BENCHES] + \
           [(b, (200, 120, 255)) for b in g.JEWEL_BENCHES] + [(g.SHOP_PED, (90, 230, 120)), (g.BUYER_PED, (90, 230, 120))]
for (x, y, _), c in stations:
    px, py = to_px(x, y)
    d.rectangle([px - 6, py - 6, px + 6, py + 6], fill=c + (255,), outline=(0, 0, 0, 255), width=2)
ex, ey = g.ENTRANCE[0], g.ENTRANCE[1]
px, py = to_px(ex, ey)
d.polygon([(px, py - 12), (px + 11, py + 8), (px - 11, py + 8)], fill=(255, 70, 70, 255), outline=(0, 0, 0, 255))

labels = [
    ('Quarry', 'המחצבה', 2958, 2770),
    ('Entrance', 'כניסה', 2946, 2728),
    ('Main chamber', 'אולם ראשי', 2930, 2708),
    ('Upper ledge', 'מדף עליון', 2862, 2716),
    ('West gallery', 'גלריה מערבית', 2838, 2678),
    ('Workshop', 'בית המלאכה', 2934, 2674),
    ('Lower tunnel', 'מנהרה תחתונה', 2870, 2622),
    ('Deep shaft', 'הפיר הדרומי', 2862, 2600),
    ('Crystal chamber', 'אולם הגבישים', 2818, 2664),
]
for en, hb, x, y in labels:
    px, py = to_px(x, y)
    for txt, f, dy in ((en, big, 0), (he(hb), small, 30)):
        w = d.textlength(txt, font=f)
        d.text((px - w / 2 + 2, py + dy + 2), txt, font=f, fill=(0, 0, 0, 200))
        d.text((px - w / 2, py + dy), txt, font=f, fill=(240, 240, 240, 255) if f is big else (190, 196, 210, 255))

d.text((28, 22), 'URBAN RP - Cave Mining', font=title, fill=(255, 200, 70, 255))
d.text((28, 64), 'K4MB1 layout - origin 2889.01, 2664.66, 41.72', font=small, fill=(170, 176, 190, 255))
d.line([(30, 118), (30 + 20 * px_per_m, 118)], fill=(230, 230, 230, 255), width=4)
d.text((30 + 20 * px_per_m + 12, 106), '20 m', font=small, fill=(230, 230, 230, 255))
legend = [((255, 190, 60), 'ore spot (35)', 'dot'), ((255, 70, 70), 'mine portal', 'tri'), ((255, 110, 40), 'smelter', 'sq'),
          ((120, 200, 255), 'stone cracking', 'sq'), ((200, 120, 255), 'jewel bench', 'sq'), ((90, 230, 120), 'shop / buyer', 'sq')]
y0 = W - 30 * len(legend) - 20
lx = W - 250
for i, (c, t, shape) in enumerate(legend):
    y = y0 + i * 30
    if shape == 'dot':
        d.ellipse([lx, y + 4, lx + 14, y + 18], fill=c + (255,))
    elif shape == 'tri':
        d.polygon([(lx + 7, y + 3), (lx + 14, y + 18), (lx, y + 18)], fill=c + (255,))
    else:
        d.rectangle([lx, y + 4, lx + 14, y + 18], fill=c + (255,))
    d.text((lx + 24, y), t, font=small, fill=(220, 224, 232, 255))
bg.convert('RGB').save(dst, quality=90)
print('map ->', dst)
