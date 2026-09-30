"""
Draws the 45 inventory icons for urban_cavemining (256x256 transparent PNG).

    pip install pillow numpy
    python fivem/tools/generate_icons.py

Output: fivem/urban_cavemining/install/images/<item>.png
Everything is drawn from code - no third-party art.
"""

import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 4                      # supersampling
SIZE = 256
W = SIZE * SS
OUT = os.path.join(os.path.dirname(__file__), '..', 'urban_cavemining', 'install', 'images')


# ───────────────────────────── helpers ─────────────────────────────
def canvas():
    return Image.new('RGBA', (W, W), (0, 0, 0, 0))


def P(x, y):
    """0..256 design coords -> supersampled pixels"""
    return (x * SS, y * SS)


def pts(seq):
    return [P(x, y) for x, y in seq]


def gradient(c1, c2, angle=90.0):
    a = math.radians(angle)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32) / W
    t = xx * math.cos(a) + yy * math.sin(a)
    t = (t - t.min()) / (t.max() - t.min())
    c1 = np.array(c1 + (255,) if len(c1) == 3 else c1, dtype=np.float32)
    c2 = np.array(c2 + (255,) if len(c2) == 3 else c2, dtype=np.float32)
    arr = c1[None, None, :] * (1 - t[..., None]) + c2[None, None, :] * t[..., None]
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def mask_poly(points):
    m = Image.new('L', (W, W), 0)
    ImageDraw.Draw(m).polygon(pts(points), fill=255)
    return m


def mask_ellipse(box, width=None):
    m = Image.new('L', (W, W), 0)
    d = ImageDraw.Draw(m)
    b = [box[0] * SS, box[1] * SS, box[2] * SS, box[3] * SS]
    if width:
        d.ellipse(b, outline=255, width=int(width * SS))
    else:
        d.ellipse(b, fill=255)
    return m


def paint(img, mask, c1, c2=None, angle=90.0):
    fill = gradient(c1, c2 or c1, angle)
    img.paste(fill, (0, 0), mask)


def outline(img, points, color, width=2.5):
    d = ImageDraw.Draw(img)
    p = pts(points)
    d.line(p + [p[0]], fill=color, width=int(width * SS), joint='curve')


def lines(img, segs, color, width=2.0):
    d = ImageDraw.Draw(img)
    for a, b in segs:
        d.line([P(*a), P(*b)], fill=color, width=int(width * SS))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def finish(img, name):
    # soft drop shadow
    alpha = img.split()[3]
    sh = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    sh.putalpha(ImageChops.multiply(alpha, Image.new('L', (W, W), 110)))
    sh = ImageChops.offset(sh, 3 * SS, 5 * SS).filter(ImageFilter.GaussianBlur(5 * SS))
    base = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    base.alpha_composite(sh)
    base.alpha_composite(img)
    base = base.resize((SIZE, SIZE), Image.LANCZOS)
    base.save(os.path.join(OUT, name + '.png'))


def rock_shape(seed, cx=128, cy=140, r=78, n=11, jag=0.22, squash=0.78):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        a = i / n * 2 * math.pi + rng.uniform(-0.15, 0.15)
        rr = r * rng.uniform(1 - jag, 1 + jag * 0.4)
        out.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * squash))
    return out


def facets(img, shape, seed, color, cx=128, cy=140):
    """draw faint facet lines from the centre for a chiselled look"""
    rng = random.Random(seed + 99)
    c = (cx + rng.uniform(-15, 15), cy + rng.uniform(-18, 0))
    segs = [(c, p) for i, p in enumerate(shape) if i % 3 == 0]
    lines(img, segs, color, 1.6)


# ───────────────────────────── rocks + ores ─────────────────────────────
ORES = {
    'stone':     ((120, 116, 110), None),
    'coal':      ((38, 38, 42), (90, 90, 100)),
    'copperore': ((96, 88, 80), (214, 120, 60)),
    'ironore':   ((92, 84, 80), (150, 70, 45)),
    'tinore':    ((100, 98, 96), (200, 204, 212)),
    'leadore':   ((88, 90, 96), (110, 124, 150)),
    'bauxite':   ((140, 70, 40), (205, 120, 70)),
    'goldore':   ((96, 88, 80), (255, 200, 60)),
}


def draw_rock(name, base, fleck, seed):
    img = canvas()
    shape = rock_shape(seed)
    paint(img, mask_poly(shape), shade(base, 1.35), shade(base, 0.6), 70)
    facets(img, shape, seed, shade(base, 0.75) + (160,))
    if fleck:
        rng = random.Random(seed * 7)
        for _ in range(16 if name != 'coal' else 9):
            cx, cy = rng.uniform(70, 186), rng.uniform(100, 180)
            s = rng.uniform(6, 15)
            fl = [(cx + math.cos(a) * s * rng.uniform(0.6, 1.2), cy + math.sin(a) * s * rng.uniform(0.5, 1.0))
                  for a in np.linspace(0, 2 * math.pi, 6, endpoint=False)]
            m = ImageChops.multiply(mask_poly(fl), mask_poly(shape))
            paint(img, m, shade(fleck, 1.3), shade(fleck, 0.75), 60)
    outline(img, shape, shade(base, 0.35) + (255,), 3)
    # top highlight
    hl = [(p[0], p[1] - 3) for p in shape[5:9]]
    lines(img, list(zip(hl, hl[1:])), (255, 255, 255, 70), 3)
    finish(img, name)


def draw_nugget():
    img = canvas()
    m = Image.new('L', (W, W), 0)
    d = ImageDraw.Draw(m)
    for cx, cy, r in ((110, 140, 46), (150, 128, 40), (140, 160, 36), (95, 165, 28), (170, 158, 26)):
        d.ellipse([(cx - r) * SS, (cy - r * 0.85) * SS, (cx + r) * SS, (cy + r * 0.85) * SS], fill=255)
    paint(img, m, (255, 226, 120), (170, 110, 20), 65)
    hl = Image.new('L', (W, W), 0)
    ImageDraw.Draw(hl).ellipse([P(100, 108), P(140, 126)], fill=200)
    img.paste(Image.new('RGBA', (W, W), (255, 250, 220, 255)), (0, 0), ImageChops.multiply(hl, m).filter(ImageFilter.GaussianBlur(4 * SS)))
    finish(img, 'goldnugget')


# ───────────────────────────── gems ─────────────────────────────
GEMS = {
    'ruby':     (230, 30, 50),
    'emerald':  (30, 200, 90),
    'sapphire': (40, 90, 235),
    'diamond':  (215, 235, 255),
}


def draw_uncut(name, col):
    img = canvas()
    base = rock_shape(len(name), cx=128, cy=190, r=70, n=9, squash=0.35)
    paint(img, mask_poly(base), (110, 104, 98), (60, 56, 52), 90)
    outline(img, base, (40, 36, 34, 255), 3)
    crystals = [(-40, -18, 22, 95), (0, 0, 30, 130), (40, -10, 20, 100), (-18, 8, 16, 70), (22, 10, 15, 64)]
    for i, (dx, tilt, w, h) in enumerate(crystals):
        cx, by = 128 + dx, 185
        ang = math.radians(tilt)
        ux, uy = math.sin(ang), -math.cos(ang)
        px, py = -uy, ux
        b1 = (cx - px * w / 2, by - py * w / 2)
        b2 = (cx + px * w / 2, by + py * w / 2)
        t1 = (b1[0] + ux * h, b1[1] + uy * h)
        t2 = (b2[0] + ux * h, b2[1] + uy * h)
        tip = (cx + ux * (h + w * 0.9), by + uy * (h + w * 0.9))
        left = [b1, (cx, by), (cx + ux * h, by + uy * h), t1]
        right = [(cx, by), b2, t2, (cx + ux * h, by + uy * h)]
        paint(img, mask_poly(left), shade(col, 1.15), shade(col, 0.7), 90)
        paint(img, mask_poly(right), shade(col, 0.8), shade(col, 0.45), 90)
        paint(img, mask_poly([t1, (cx + ux * h, by + uy * h), tip]), shade(col, 1.4), shade(col, 1.0), 90)
        paint(img, mask_poly([(cx + ux * h, by + uy * h), t2, tip]), shade(col, 1.0), shade(col, 0.7), 90)
        outline(img, [b1, b2, t2, tip, t1], shade(col, 0.3) + (255,), 2)
    finish(img, 'uncut_' + name)


def draw_cut(name, col):
    img = canvas()
    if name == 'emerald':
        # step cut (octagon)
        outer = [(78, 80), (178, 80), (200, 102), (200, 170), (178, 192), (78, 192), (56, 170), (56, 102)]
        inner = [(96, 100), (160, 100), (176, 116), (176, 156), (160, 172), (96, 172), (80, 156), (80, 116)]
        paint(img, mask_poly(outer), shade(col, 0.7), shade(col, 0.4), 60)
        paint(img, mask_poly(inner), shade(col, 1.35), shade(col, 0.85), 60)
        for a, b in zip(outer, inner):
            lines(img, [(a, b)], shade(col, 1.6) + (150,), 1.6)
        outline(img, inner, shade(col, 1.8) + (180,), 1.6)
        outline(img, outer, shade(col, 0.3) + (255,), 3)
    else:
        crown = [(64, 110), (92, 76), (164, 76), (192, 110)]
        pav = [(64, 110), (192, 110), (128, 206)]
        paint(img, mask_poly(crown), shade(col, 1.45), shade(col, 0.95), 80)
        paint(img, mask_poly(pav), shade(col, 0.95), shade(col, 0.45), 80)
        table = [(104, 76), (152, 76), (140, 96), (116, 96)]
        paint(img, mask_poly(table), shade(col, 1.8), shade(col, 1.3), 90)
        segs = [((92, 76), (116, 96)), ((164, 76), (140, 96)), ((116, 96), (140, 96)), ((116, 96), (96, 110)),
                ((140, 96), (160, 110)), ((64, 110), (192, 110)), ((96, 110), (128, 206)), ((160, 110), (128, 206)),
                ((128, 110), (128, 206))]
        lines(img, segs, shade(col, 1.7) + (140,), 1.6)
        outline(img, crown[:1] + crown[1:] + [(128, 206)], shade(col, 0.3) + (255,), 3)
    # sparkle
    d = ImageDraw.Draw(img)
    for sx, sy, s in ((170, 72, 14), (84, 150, 8)):
        d.line([P(sx - s, sy), P(sx + s, sy)], fill=(255, 255, 255, 230), width=2 * SS)
        d.line([P(sx, sy - s), P(sx, sy + s)], fill=(255, 255, 255, 230), width=2 * SS)
    finish(img, name)


# ───────────────────────────── ingots ─────────────────────────────
METALS = {
    'copper':    (200, 110, 60),
    'iron':      (110, 112, 118),
    'tin':       (190, 194, 200),
    'lead':      (96, 104, 124),
    'aluminum':  (215, 220, 228),
    'steel':     (140, 156, 176),
    'bronze':    (176, 120, 56),
    'goldingot': (250, 196, 64),
}


def draw_ingot(name, col):
    img = canvas()
    top = [(84, 96), (190, 96), (214, 122), (60, 122)]
    front = [(60, 122), (214, 122), (200, 176), (74, 176)]
    paint(img, mask_poly(top), shade(col, 1.45), shade(col, 1.1), 90)
    paint(img, mask_poly(front), shade(col, 1.0), shade(col, 0.55), 90)
    outline(img, [(84, 96), (190, 96), (214, 122), (200, 176), (74, 176), (60, 122)], shade(col, 0.3) + (255,), 3)
    lines(img, [((60, 122), (214, 122))], shade(col, 1.7) + (200,), 2)
    # stamp
    ImageDraw.Draw(img).rounded_rectangle([P(110, 136), P(164, 162)], radius=4 * SS, outline=shade(col, 0.6) + (200,), width=2 * SS)
    lines(img, [((96, 104), (150, 104))], (255, 255, 255, 110), 3)
    finish(img, name)


# ───────────────────────────── jewellery ─────────────────────────────
GOLD = (245, 190, 60)


def gem_dot(img, cx, cy, r, col):
    shape = [(cx, cy - r), (cx + r * 0.9, cy - r * 0.2), (cx + r * 0.55, cy + r * 0.9), (cx - r * 0.55, cy + r * 0.9), (cx - r * 0.9, cy - r * 0.2)]
    paint(img, mask_poly(shape), shade(col, 1.5), shade(col, 0.6), 70)
    outline(img, shape, shade(col, 0.3) + (255,), 2)
    lines(img, [((cx - r * 0.3, cy - r * 0.35), (cx + r * 0.05, cy - r * 0.55))], (255, 255, 255, 220), 2)


def draw_ring(name, gem=None):
    img = canvas()
    band = mask_ellipse((58, 92, 198, 212), width=20)
    paint(img, band, (255, 230, 140), (170, 110, 20), 60)
    if gem:
        ImageDraw.Draw(img).rectangle([P(114, 80), P(142, 100)], fill=shade(GOLD, 0.8) + (255,))
        gem_dot(img, 128, 70, 26, GEMS[gem])
    finish(img, name)


def chain(img, path, link=9):
    d = ImageDraw.Draw(img)
    for i, (x, y) in enumerate(path):
        box = [P(x - link, y - link * 0.55), P(x + link, y + link * 0.55)] if i % 2 == 0 else [P(x - link * 0.55, y - link), P(x + link * 0.55, y + link)]
        d.ellipse(box, outline=shade(GOLD, 0.55) + (255,), width=int(5.5 * SS))
        d.ellipse(box, outline=GOLD + (255,), width=int(3.5 * SS))


def u_path(cx=128, top=56, bottom=176, half=78, n=22):
    out = []
    for i in range(n):
        t = i / (n - 1)
        a = math.pi * t
        out.append((cx - math.cos(a) * half, top + math.sin(a) * (bottom - top)))
    return out


def draw_chain(name, gem=None):
    img = canvas()
    path = u_path()
    chain(img, path)
    if gem:
        cx, cy = path[len(path) // 2]
        gem_dot(img, cx, cy + 32, 28, GEMS[gem])
    finish(img, name)


def draw_earrings(name, gem):
    img = canvas()
    d = ImageDraw.Draw(img)
    for cx in (88, 168):
        d.arc([P(cx - 20, 50), P(cx + 20, 100)], 180, 400, fill=GOLD + (255,), width=5 * SS)
        d.line([P(cx, 100), P(cx, 132)], fill=GOLD + (255,), width=5 * SS)
        gem_dot(img, cx, 162, 30, GEMS[gem])
    finish(img, name)


# ───────────────────────────── tools ─────────────────────────────
def draw_pickaxe():
    img = canvas()
    handle = [(70, 212), (84, 222), (184, 86), (170, 76)]
    paint(img, mask_poly(handle), (160, 105, 60), (90, 55, 28), 0)
    outline(img, handle, (50, 30, 15, 255), 2.5)
    head = [(96, 58), (140, 50), (190, 62), (232, 104), (220, 110), (184, 84), (150, 78), (112, 86), (62, 118), (58, 108)]
    paint(img, mask_poly(head), (200, 205, 212), (90, 94, 100), 80)
    outline(img, head, (40, 42, 46, 255), 3)
    lines(img, [((104, 64), (176, 66))], (255, 255, 255, 150), 3)
    finish(img, 'pickaxe')


def draw_drill():
    img = canvas()
    body = [(56, 96), (168, 96), (180, 110), (180, 150), (168, 160), (56, 160), (46, 148), (46, 108)]
    paint(img, mask_poly(body), (255, 200, 40), (190, 120, 10), 90)
    outline(img, body, (70, 45, 5, 255), 3)
    grip = [(84, 160), (122, 160), (112, 222), (74, 222)]
    paint(img, mask_poly(grip), (60, 60, 66), (25, 25, 28), 0)
    outline(img, grip, (10, 10, 10, 255), 3)
    chuck = [(180, 114), (204, 118), (204, 138), (180, 142)]
    paint(img, mask_poly(chuck), (90, 90, 96), (40, 40, 44), 90)
    bit = [(204, 122), (238, 128), (204, 134)]
    paint(img, mask_poly(bit), (210, 214, 220), (120, 124, 130), 90)
    lines(img, [((60, 112), (160, 112))], (255, 245, 200, 160), 3)
    for x in (70, 84, 98):
        lines(img, [((x, 126), (x, 146))], (120, 80, 5, 255), 3)
    finish(img, 'miningdrill')


def draw_drillbit():
    img = canvas()
    shaft = [(118, 40), (138, 40), (138, 92), (118, 92)]
    paint(img, mask_poly(shaft), (160, 164, 170), (90, 92, 98), 0)
    cone = [(106, 92), (150, 92), (128, 226)]
    paint(img, mask_poly(cone), (225, 228, 232), (110, 114, 120), 0)
    outline(img, cone, (40, 42, 46, 255), 3)
    outline(img, shaft, (40, 42, 46, 255), 3)
    for k in range(6):
        y = 100 + k * 20
        w = 22 * (1 - (y - 92) / 134)
        lines(img, [((128 - w, y), (128 + w, y + 12))], (60, 62, 66, 255), 3)
    finish(img, 'drillbit')


def draw_laser():
    img = canvas()
    body = [(40, 100), (176, 92), (196, 104), (196, 140), (176, 150), (40, 146), (30, 134), (30, 110)]
    paint(img, mask_poly(body), (80, 86, 100), (30, 32, 40), 90)
    outline(img, body, (10, 10, 14, 255), 3)
    lines(img, [((44, 112), (170, 106))], (0, 220, 255, 220), 4)
    grip = [(70, 146), (108, 146), (98, 214), (60, 214)]
    paint(img, mask_poly(grip), (50, 52, 60), (20, 20, 24), 0)
    outline(img, grip, (10, 10, 12, 255), 3)
    emitter = [(196, 108), (218, 112), (218, 132), (196, 136)]
    paint(img, mask_poly(emitter), (255, 80, 60), (150, 20, 20), 0)
    beam = Image.new('L', (W, W), 0)
    ImageDraw.Draw(beam).line([P(218, 122), P(254, 122)], fill=255, width=8 * SS)
    img.paste(Image.new('RGBA', (W, W), (255, 60, 50, 255)), (0, 0), beam.filter(ImageFilter.GaussianBlur(2 * SS)))
    finish(img, 'mininglaser')


def draw_pan():
    img = canvas()
    paint(img, mask_ellipse((34, 84, 222, 200)), (120, 124, 130), (50, 52, 56), 90)
    paint(img, mask_ellipse((56, 100, 200, 180)), (70, 72, 78), (140, 144, 150), 90)
    rng = random.Random(5)
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x, y, r = rng.uniform(80, 176), rng.uniform(118, 164), rng.uniform(2.5, 6)
        d.ellipse([P(x - r, y - r * 0.7), P(x + r, y + r * 0.7)], fill=(250, 200, 70, 255))
    d.ellipse([P(34, 84), P(222, 200)], outline=(30, 30, 34, 255), width=3 * SS)
    finish(img, 'goldpan')


def draw_helmet():
    img = canvas()
    dome = Image.new('L', (W, W), 0)
    ImageDraw.Draw(dome).pieslice([P(52, 60), P(204, 220)], 180, 360, fill=255)
    paint(img, dome, (255, 214, 60), (200, 130, 10), 90)
    brim = [(34, 140), (222, 140), (214, 156), (42, 156)]
    paint(img, mask_poly(brim), (240, 190, 40), (170, 110, 10), 90)
    outline(img, brim, (90, 60, 5, 255), 3)
    lines(img, [((128, 62), (128, 138))], (220, 160, 20, 255), 7)
    lamp = mask_ellipse((106, 88, 150, 126))
    paint(img, lamp, (255, 255, 230), (255, 220, 120), 90)
    ImageDraw.Draw(img).ellipse([P(106, 88), P(150, 126)], outline=(60, 60, 60, 255), width=3 * SS)
    glow = mask_ellipse((96, 78, 160, 136)).filter(ImageFilter.GaussianBlur(8 * SS))
    img.paste(Image.new('RGBA', (W, W), (255, 250, 200, 255)), (0, 0), ImageChops.multiply(glow, Image.new('L', (W, W), 90)))
    finish(img, 'mining_helmet')


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, (name, (base, fleck)) in enumerate(ORES.items()):
        draw_rock(name, base, fleck, 11 + i * 7)
    draw_nugget()
    for name, col in GEMS.items():
        draw_uncut(name, col)
        draw_cut(name, col)
    for name, col in METALS.items():
        draw_ingot(name, col)
    draw_ring('gold_ring')
    draw_chain('goldchain')
    for gem in GEMS:
        draw_ring(gem + '_ring', gem)
        draw_chain(gem + '_necklace', gem)
        draw_earrings(gem + '_earring', gem)
    draw_pickaxe()
    draw_drill()
    draw_drillbit()
    draw_laser()
    draw_pan()
    draw_helmet()
    print(f'{len(os.listdir(OUT))} icons in {os.path.normpath(OUT)}')


if __name__ == '__main__':
    main()
