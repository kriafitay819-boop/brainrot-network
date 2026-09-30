"""
URBAN RP - Cave Mining generator for Blender 4.x (v2, photoreal)
================================================================

Builds a complete, photoreal mining cave in the style of the K4MB1 "Cave Mining" MLO,
entered from the Davis Quartz quarry wall:

* quarry wall, road bench and quarry floor around a timber mine portal, with the
  props from the real spot (flat-bed rail cart, pipe stack, drums, tank, site toilets)
* natural rock tunnels and chambers meshed from a signed-distance field, with
  render-time displacement for millimetre rock detail
* one 4-layer terrain material (cave rock / sand / quarry rock / quarry dirt) blended by
  vertex colours - the same idea as GTA's terrain_cb_w_4lyr shader
* loose sand floor with pebbles, scree, footprints and cart ruts
* timber sets with lagging, rails with sleepers, ore carts, work lamps, flood towers,
  ore veins on the 35 FiveM ore spots, crystal chamber and the full workshop
* sun + sky outside, warm incandescent lamps and mine dust inside
* optional 4K seamless texture bake (albedo / normal / roughness / height) for GTA

Everything is placed in FiveM space: local (0,0,0) = MLO origin 2889.014, 2664.655, 41.72483.
The ore veins and stations sit exactly where fivem/urban_cavemining spawns them.

Usage
-----
Blender:   Scripting -> Open -> this file -> Run Script
Headless:  blender -b -P cave_mine_generator.py -- [options]
   or      python cave_mine_generator.py [options]        (pip install bpy==4.2.0)

Options:
   --save FILE.blend          save the scene
   --render DIR               render every camera to DIR
   --res 3840x2160            render resolution (default 3840x2160 = 4K)
   --samples N                max samples per pixel (adaptive, default 96)
   --only a,b                 only render cameras whose name contains a or b
   --bake DIR                 bake the seamless 4K PBR texture sets to DIR first, then use them
   --bake-size 4096           bake resolution (default 4096 = 4K)
   --textures DIR             use texture sets baked earlier (default: ./textures next to this file)
   --fast                     preview quality: no displacement, fewer pebbles

Only numpy (bundled with Blender) is needed - no add-ons, no downloads.
"""

import math
import os
import random
import sys
import time

import bpy      # must come first when running with the stand-alone bpy module
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# ─────────────────────────────────────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
ORIGIN = Vector((2889.014, 2664.655, 41.72483))   # K4MB1 MLO origin (GTA world)

# Mine portal in the quarry wall: GTA x, y, floor z, heading looking INTO the cave.
# In-game: stand in the opening, run /cavecoords and paste the numbers here.
ENTRANCE = (2937.98, 2744.81, 42.25, 102.0)
QUARRY_FLOOR = 42.0          # quarry ground in front of the wall (world z)
QUARRY_WALL = 11.5           # first quarry wall height (m), road bench on top
QUARRY_BENCH = 8.0           # width of the road bench
QUARRY_FRONT = 34.0          # how much quarry floor is built in front of the wall
QUARRY_HALF = 40.0           # wall length on each side of the portal

VOXEL = 0.3                  # rock mesh resolution (m)
Z_SCALE = 1.18               # >1 = tunnels wider than tall
CENTER_FRAC = 0.55           # tube centre height above the floor, in radii
SMOOTH_K = 2.2               # how softly tunnels blend into chambers
NOISE_LARGE = 1.35
NOISE_MED = 0.7
NOISE_SMALL = 0.28
NOISE_RIDGE = 0.45
DISPLACEMENT = 0.14          # render-time rock displacement (m)
DUST_DENSITY = 0.006         # mine dust in the air (0 = off)
SEED = 1337

# Tunnel graph in GTA world coords: name -> (x, y, floor_z, radius)
NODES = {
    'e1':      (2930.0, 2743.0, 42.6, 3.7),
    'e2':      (2912.0, 2737.0, 42.8, 3.7),
    'e3':      (2897.0, 2723.0, 43.0, 3.5),
    'e4':      (2903.0, 2709.0, 43.4, 3.9),
    'main':    (2906.0, 2694.0, 44.4, 9.5),
    'main_e':  (2925.0, 2692.0, 44.8, 6.0),
    'main_w':  (2889.0, 2684.0, 44.0, 7.5),
    'ledge':   (2884.0, 2703.0, 48.2, 5.5),
    'ledge_w': (2872.0, 2708.0, 48.4, 4.0),
    'west1':   (2870.0, 2673.0, 46.0, 5.0),
    'west2':   (2860.0, 2665.0, 44.2, 5.0),
    'link1':   (2886.0, 2662.0, 42.6, 4.2),
    'link2':   (2892.0, 2646.0, 40.8, 4.6),
    'shop':    (2915.5, 2650.2, 42.1, 10.5),
    'low1':    (2877.0, 2638.0, 38.3, 4.2),
    'low2':    (2860.0, 2630.0, 36.8, 4.0),
    'low3':    (2846.0, 2622.0, 35.6, 4.2),
    'south1':  (2834.0, 2606.0, 34.0, 5.0),
    'south2':  (2821.0, 2595.0, 31.6, 5.2),
    'south3':  (2823.0, 2610.0, 36.8, 4.2),
    'fw1':     (2826.0, 2626.0, 37.2, 4.0),
    'fw2':     (2812.0, 2633.0, 38.0, 5.0),
    'crystal': (2799.0, 2637.0, 38.2, 7.5),
}

EDGES = [
    ('apron', 'portal'), ('portal', 'e1'), ('e1', 'e2'), ('e2', 'e3'), ('e3', 'e4'), ('e4', 'main'),
    ('main', 'main_e'), ('main', 'main_w'), ('main', 'ledge'), ('ledge', 'ledge_w'),
    ('main_w', 'west1'), ('west1', 'west2'), ('main_w', 'link1'), ('link1', 'link2'),
    ('link2', 'shop'), ('link2', 'low1'), ('low1', 'low2'), ('low2', 'low3'),
    ('low3', 'south1'), ('south1', 'south2'), ('south1', 'south3'), ('south3', 'fw1'),
    ('low3', 'fw1'), ('fw1', 'fw2'), ('fw2', 'crystal'),
]
OUTSIDE_EDGES = {('apron', 'portal')}
CHAMBERS = {'main', 'main_e', 'main_w', 'shop', 'crystal', 'ledge'}

# Ore spots (GTA world, same list as fivem/urban_cavemining/shared/locations.lua)
ORE_SPOTS = [
    (2906.33, 2736.05, 43.85), (2906.98, 2732.64, 43.47), (2895.62, 2718.17, 44.25), (2909.86, 2707.41, 44.63),
    (2930.71, 2693.23, 46.09), (2909.24, 2692.78, 47.27), (2908.31, 2695.83, 46.5), (2903.37, 2676.71, 45.94),
    (2890.67, 2679.4, 45.05), (2892.67, 2701.3, 49.89), (2876.93, 2707.35, 49.4), (2900.65, 2684.42, 47.24),
    (2878.67, 2686.09, 47.72), (2866.0, 2677.71, 47.3), (2859.24, 2668.93, 45.27), (2858.36, 2663.24, 45.0),
    (2864.22, 2665.22, 48.21), (2868.6, 2669.71, 47.88), (2888.64, 2634.32, 42.04), (2879.55, 2650.2, 43.89),
    (2896.12, 2648.21, 40.65), (2808.16, 2650.5, 38.2), (2792.43, 2640.55, 39.45), (2793.02, 2632.56, 39.91),
    (2799.6, 2629.83, 40.89), (2812.67, 2633.02, 40.79), (2817.65, 2590.74, 32.64), (2835.04, 2600.4, 34.93),
    (2837.77, 2605.3, 35.40), (2819.55, 2606.31, 38.08), (2823.73, 2611.07, 38.3), (2827.98, 2611.26, 34.15),
    (2873.53, 2634.1, 39.42), (2871.89, 2642.97, 39.05), (2848.97, 2624.63, 36.58),
]

# Workshop (GTA world coords + heading) - matches the FiveM stations
SMELTER = (2921.81, 2653.42, 0.0)
CRACK_BENCHES = [(2914.9, 2650.78, 231.77), (2914.61, 2649.06, 272.74)]
JEWEL_BENCHES = [(2917.45, 2654.24, 229.61), (2919.89, 2656.36, 199.99)]
SHOP_PED = (2908.8, 2643.6, 328.32)
BUYER_PED = (2917.79, 2646.26, 6.14)

RAIL_ROUTES = [
    ['apron', 'portal', 'e1', 'e2', 'e3', 'e4', 'main', 'main_w', 'link1', 'link2', 'shop'],
    ['link2', 'low1', 'low2', 'low3', 'south1', 'south2'],
]

RNG = random.Random(SEED)


def local(x, y, z=0.0):
    return Vector((x - ORIGIN.x, y - ORIGIN.y, z - ORIGIN.z))


def entrance_frame():
    """Portal floor point (local), direction INTO the cave, direction along the wall"""
    x, y, f, h = ENTRANCE
    into = Vector((-math.sin(math.radians(h)), math.cos(math.radians(h)), 0.0))
    along = Vector((-into.y, into.x, 0.0))
    return local(x, y, f), into, along


def _add_entrance_nodes():
    x, y, f, h = ENTRANCE
    E, into, _ = entrance_frame()
    NODES['portal'] = (x, y, f, 3.2)
    NODES['apron'] = (x - into.x * 6.0, y - into.y * 6.0, QUARRY_FLOOR, 4.0)


_add_entrance_nodes()


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ─────────────────────────────────────────────────────────────────────────────
#  NOISE (numpy value noise, runs inside Blender's bundled Python)
# ─────────────────────────────────────────────────────────────────────────────
def _hash3(ix, iy, iz, seed):
    h = (ix * np.int64(73856093)) ^ (iy * np.int64(19349663)) ^ (iz * np.int64(83492791)) ^ np.int64(seed * 2654435761 & 0xFFFFFFFF)
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    h = h ^ (h >> np.int64(16))
    return (h & np.int64(0xFFFFFF)).astype(np.float32) / np.float32(0xFFFFFF)


def value_noise(x, y, z, seed):
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    xi, yi, zi = xi.astype(np.int64), yi.astype(np.int64), zi.astype(np.int64)
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    w = zf * zf * (3 - 2 * zf)
    out = np.zeros_like(x, dtype=np.float32)
    for dx in (0, 1):
        wx = u if dx else 1 - u
        for dy in (0, 1):
            wy = v if dy else 1 - v
            for dz in (0, 1):
                wz = w if dz else 1 - w
                out += wx * wy * wz * _hash3(xi + dx, yi + dy, zi + dz, seed)
    return out * 2.0 - 1.0     # -1..1


def rock_noise(x, y, z):
    wx = x + 2.5 * value_noise(x * 0.05, y * 0.05, z * 0.05, SEED + 7)
    wy = y + 2.5 * value_noise(x * 0.05, y * 0.05, z * 0.05, SEED + 8)
    n = NOISE_LARGE * value_noise(wx * 0.06, wy * 0.06, z * 0.08, SEED)
    n += NOISE_MED * value_noise(wx * 0.17, wy * 0.17, z * 0.22, SEED + 1)
    n += NOISE_SMALL * value_noise(wx * 0.5, wy * 0.5, z * 0.55, SEED + 2)
    n += NOISE_RIDGE * (1.0 - 2.0 * np.abs(value_noise(wx * 0.33, wy * 0.33, z * 0.45, SEED + 3)))
    return n


def quarry_noise(x, y, z):
    """Quarry wall: vertical blast fractures + horizontal bedding"""
    n = 0.9 * value_noise(x * 0.32, y * 0.32, z * 0.045, SEED + 11)
    n += 0.45 * value_noise(x * 0.9, y * 0.9, z * 0.12, SEED + 12)
    n += 0.35 * (1.0 - 2.0 * np.abs(value_noise(x * 0.18, y * 0.18, z * 0.6, SEED + 13)))
    n += 0.5 * value_noise(x * 0.08, y * 0.08, z * 0.08, SEED + 14)
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  CAVE + QUARRY SDF  (F < 0 = open air, F > 0 = rock)
# ─────────────────────────────────────────────────────────────────────────────
def node_center(name):
    x, y, f, r = NODES[name]
    p = local(x, y, f)
    return Vector((p.x, p.y, p.z + CENTER_FRAC * r)), p.z, r


def nearest_edge_point(p, skip_outside=True):
    """Closest point (in plan view) on the tunnel graph: (distance, point, floor, direction)"""
    best = None
    for a, b in EDGES:
        if skip_outside and (a, b) in OUTSIDE_EDGES:
            continue
        A, fa, ra = node_center(a)
        B, fb, rb = node_center(b)
        ab = Vector((B.x - A.x, B.y - A.y, 0))
        t = max(0.0, min(1.0, Vector((p.x - A.x, p.y - A.y, 0)).dot(ab) / max(ab.dot(ab), 1e-6)))
        q = Vector((A.x + ab.x * t, A.y + ab.y * t, 0))
        d = (Vector((p.x, p.y, 0)) - q).length
        if best is None or d < best[0]:
            best = (d, q, fa + (fb - fa) * t, ab.normalized() if ab.length else Vector((1, 0, 0)))
    return best


def interaction_points():
    pts = [local(x, y, z - 0.2) for x, y, z in ORE_SPOTS]
    pts.append(local(SMELTER[0], SMELTER[1], 43.0))
    pts += [local(x, y, 43.0) for x, y, _ in CRACK_BENCHES + JEWEL_BENCHES]
    pts += [local(SHOP_PED[0], SHOP_PED[1], 43.2), local(BUYER_PED[0], BUYER_PED[1], 43.2)]
    return pts


def segments():
    """Tunnel segments + a mined-out alcove leading to every ore spot"""
    segs = []
    for a, b in EDGES:
        A, fa, ra = node_center(a)
        B, fb, rb = node_center(b)
        segs.append((A, fa, ra, B, fb, rb))
    for x, y, z in ORE_SPOTS:
        spot = local(x, y, z)
        d, q, fq, _ = nearest_edge_point(spot)
        if d < 1.2:
            continue
        out = Vector((spot.x - q.x, spot.y - q.y, 0)).normalized()
        end = Vector((spot.x, spot.y, 0)) - out * 1.0
        f_end = spot.z - 1.05
        ra, rb = 2.1, 1.95
        A = Vector((q.x, q.y, fq + CENTER_FRAC * ra))
        B = Vector((end.x, end.y, f_end + CENTER_FRAC * rb))
        segs.append((A, fq, ra, B, f_end, rb))
    return segs


def quarry_field(X, Y, Z):
    """Rock SDF of the quarry around the portal (positive = rock)"""
    E, into, along = entrance_frame()
    qf = QUARRY_FLOOR - ORIGIN.z
    s = -((X - E.x) * into.x + (Y - E.y) * into.y)          # + in front of the wall
    t = (X - E.x) * along.x + (Y - E.y) * along.y            # along the wall
    ground = Z - qf
    wall1 = np.maximum(s, Z - (qf + QUARRY_WALL))             # first wall, bench on top
    wall2 = s + QUARRY_BENCH                                  # upper wall behind the bench
    sides = QUARRY_HALF - np.abs(t)                           # quarry closes at the sides
    far = QUARRY_FRONT - s                                    # opposite quarry wall
    rock = np.minimum(np.minimum(ground, wall1), np.minimum(np.minimum(wall2, sides), far))
    floor = np.where(s > 0, qf, qf + QUARRY_WALL).astype(np.float32)
    return -rock, floor, s


def grid_bounds():
    pts = []
    for name in NODES:
        c, f, r = node_center(name)
        pts += [c - Vector((r, r, r)), c + Vector((r, r, r))]
    E, into, along = entrance_frame()
    qf = QUARRY_FLOOR - ORIGIN.z
    for s in (-(QUARRY_BENCH + 4.0), QUARRY_FRONT + 3.0):
        for t in (-QUARRY_HALF - 3, QUARRY_HALF + 3):
            p = E - into * s + along * t
            pts += [Vector((p.x, p.y, qf - 3)), Vector((p.x, p.y, qf + QUARRY_WALL + 8))]
    lo = Vector((min(p.x for p in pts) - 3, min(p.y for p in pts) - 3, min(p.z for p in pts) - 3))
    hi = Vector((max(p.x for p in pts) + 3, max(p.y for p in pts) + 3, max(p.z for p in pts) + 1))
    hi.z = qf + QUARRY_WALL + 8          # the quarry pit is open to the sky at the grid top
    lo = Vector([math.floor(v / VOXEL) * VOXEL for v in lo])
    return lo, hi


def build_field():
    lo, hi = grid_bounds()
    nx = int((hi.x - lo.x) / VOXEL) + 1
    ny = int((hi.y - lo.y) / VOXEL) + 1
    nz = int((hi.z - lo.z) / VOXEL) + 1
    print(f'[cave] grid {nx} x {ny} x {nz} = {nx * ny * nz / 1e6:.1f}M samples')

    F = np.full((nx, ny, nz), 50.0, dtype=np.float32)
    floor_at = np.full((nx, ny, nz), -1000.0, dtype=np.float32)
    ext = np.zeros((nx, ny, nz), dtype=np.uint8)

    def block(bmin, bmax):
        i0 = max(0, int((bmin.x - lo.x) / VOXEL)); i1 = min(nx, int((bmax.x - lo.x) / VOXEL) + 2)
        j0 = max(0, int((bmin.y - lo.y) / VOXEL)); j1 = min(ny, int((bmax.y - lo.y) / VOXEL) + 2)
        k0 = max(0, int((bmin.z - lo.z) / VOXEL)); k1 = min(nz, int((bmax.z - lo.z) / VOXEL) + 2)
        if i0 >= i1 or j0 >= j1 or k0 >= k1:
            return None
        X, Y, Z = np.meshgrid(
            (lo.x + np.arange(i0, i1) * VOXEL).astype(np.float32),
            (lo.y + np.arange(j0, j1) * VOXEL).astype(np.float32),
            (lo.z + np.arange(k0, k1) * VOXEL).astype(np.float32),
            indexing='ij')
        return (slice(i0, i1), slice(j0, j1), slice(k0, k1)), X, Y, Z

    def smin_into(sl, seg, fl, k=SMOOTH_K, mark_ext=False):
        cur = F[sl]
        h = np.clip(k - np.abs(cur - seg), 0.0, None) / k
        blended = np.minimum(cur, seg) - h * h * k * 0.25
        closer = seg < cur
        fcur = floor_at[sl]
        fcur[closer] = fl[closer]
        if mark_ext:
            ecur = ext[sl]
            ecur[closer] = 1
        F[sl] = blended

    # tunnels, chambers and ore alcoves
    for A, fa, ra, B, fb, rb in segments():
        rmax = max(ra, rb) + SMOOTH_K + 2.5
        blk = block(Vector((min(A.x, B.x) - rmax, min(A.y, B.y) - rmax, min(A.z, B.z) - rmax)),
                    Vector((max(A.x, B.x) + rmax, max(A.y, B.y) + rmax, max(A.z, B.z) + rmax)))
        if not blk:
            continue
        sl, X, Y, Z = blk
        ba = B - A
        t = np.clip(((X - A.x) * ba.x + (Y - A.y) * ba.y + (Z - A.z) * ba.z) / ba.dot(ba), 0.0, 1.0)
        r = ra + (rb - ra) * t
        cx, cy, cz = A.x + ba.x * t, A.y + ba.y * t, A.z + ba.z * t
        fl = fa + (fb - fa) * t
        d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + ((Z - cz) * Z_SCALE) ** 2) - r
        smin_into(sl, np.maximum(d, fl - Z), fl)

    # quarry outside the portal
    E, into, along = entrance_frame()
    corners = []
    for s in (-(QUARRY_BENCH + 5.0), QUARRY_FRONT + 4):
        for t in (-QUARRY_HALF - 4, QUARRY_HALF + 4):
            corners.append(E - into * s + along * t)
    blk = block(Vector((min(c.x for c in corners), min(c.y for c in corners), lo.z)),
                Vector((max(c.x for c in corners), max(c.y for c in corners), hi.z)))
    if blk:
        sl, X, Y, Z = blk
        qf, qfloor, _ = quarry_field(X, Y, Z)
        smin_into(sl, qf.astype(np.float32), qfloor, k=1.6, mark_ext=True)

    # rock shelves under ore spots that sit high above the tunnel floor
    for x, y, z in ORE_SPOTS:
        spot = local(x, y, z)
        d, q, fq, _ = nearest_edge_point(spot)
        shelf = spot.z - 1.05
        if shelf - fq < 1.0:
            continue
        rad = 1.7
        blk = block(Vector((spot.x - 4, spot.y - 4, fq - 2)), Vector((spot.x + 4, spot.y + 4, shelf + 1)))
        if not blk:
            continue
        sl, X, Y, Z = blk
        zc = np.clip(Z, fq - 2.0, shelf - rad)
        mound = np.sqrt((X - spot.x) ** 2 + (Y - spot.y) ** 2 + (Z - zc) ** 2) - rad
        F[sl] = np.maximum(F[sl], -mound)
        fcur = floor_at[sl]
        np.maximum(fcur, np.where(mound < 0.5, shelf, -1000.0).astype(np.float32), out=fcur)

    # rock noise only near the surface
    band = np.abs(F) < 3.4
    idx = np.nonzero(band)
    X = lo.x + idx[0].astype(np.float32) * VOXEL
    Y = lo.y + idx[1].astype(np.float32) * VOXEL
    Z = lo.z + idx[2].astype(np.float32) * VOXEL
    is_ext = ext[idx].astype(np.float32)
    n = rock_noise(X, Y, Z) * (1 - is_ext) + quarry_noise(X, Y, Z) * is_ext
    above = np.clip((Z - floor_at[idx]) / 1.6, 0.1, 1.0)

    # FiveM interaction points stay in open cave
    dmin = np.full(X.shape, 1e9, dtype=np.float32)
    for q in interaction_points():
        d = np.sqrt((X - q.x) ** 2 + (Y - q.y) ** 2 + ((Z - q.z) * 0.8) ** 2)
        np.minimum(dmin, d, out=dmin)
    calm = np.clip((dmin - 1.2) / 3.0, 0.15, 1.0)
    # keep the portal opening clean for the timber frame
    s = -((X - E.x) * into.x + (Y - E.y) * into.y)
    t = (X - E.x) * along.x + (Y - E.y) * along.y
    portal = np.clip((np.maximum(np.abs(s + 1.0) - 2.5, 0) + np.maximum(np.abs(t) - 2.6, 0)) / 2.0, 0.15, 1.0)
    vals = F[idx] + n * above * calm * portal
    F[idx] = np.minimum(vals, dmin - 0.75)
    return F, lo, floor_at, ext


CORNERS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]])
CUBE_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def surface_nets(F, lo):
    """Naive surface nets. Quads face the negative side of F (the open cave),
    every edge is shared by exactly two quads, winding is consistent."""
    nx, ny, nz = F.shape
    n = np.array([nx, ny, nz])
    inside = F < 0
    any_in = np.zeros((nx - 1, ny - 1, nz - 1), dtype=bool)
    all_in = np.ones((nx - 1, ny - 1, nz - 1), dtype=bool)
    for c in CORNERS:
        s = inside[c[0]:nx - 1 + c[0], c[1]:ny - 1 + c[1], c[2]:nz - 1 + c[2]]
        any_in |= s
        all_in &= s
    active = any_in & ~all_in
    del any_in, all_in
    cells = np.argwhere(active)
    print(f'[cave] {len(cells)} surface cells')

    acc = np.zeros((len(cells), 3), dtype=np.float64)
    cnt = np.zeros(len(cells), dtype=np.float64)
    for e0, e1 in CUBE_EDGES:
        p0 = cells + CORNERS[e0]
        p1 = cells + CORNERS[e1]
        a = F[p0[:, 0], p0[:, 1], p0[:, 2]]
        b = F[p1[:, 0], p1[:, 1], p1[:, 2]]
        m = (a < 0) != (b < 0)
        t = np.where(m, a / np.where(m, a - b, 1.0), 0.0)
        pos = p0 + (p1 - p0) * t[:, None]
        acc[m] += pos[m]
        cnt[m] += 1
    verts = acc / cnt[:, None] * VOXEL + np.array([lo.x, lo.y, lo.z])

    vid = np.full(active.shape, -1, dtype=np.int64)
    vid[active] = np.arange(len(cells))

    faces = []
    eye = np.eye(3, dtype=np.int64)
    for axis, bax, cax in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):     # cyclic -> consistent winding
        ea, eb, ec = eye[axis], eye[bax], eye[cax]
        start = np.where(np.arange(3) == axis, 0, 1)
        stop = n - 1
        sl_a = tuple(slice(start[d], stop[d]) for d in range(3))
        sl_b = tuple(slice(start[d] + ea[d], stop[d] + ea[d]) for d in range(3))
        change = inside[sl_a] != inside[sl_b]
        p = np.argwhere(change) + start
        flip = inside[p[:, 0], p[:, 1], p[:, 2]]
        quad = [p - eb - ec, p - ec, p, p - eb]
        ids = np.stack([vid[c[:, 0], c[:, 1], c[:, 2]] for c in quad], axis=1)
        ids[flip] = ids[flip][:, ::-1]
        faces.append(ids)
    return verts, np.concatenate(faces)


def keep_big_components(verts, faces, min_faces=400):
    parent = np.arange(len(verts))

    def find(i):
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    for f in faces:
        r0 = find(f[0])
        for v in f[1:]:
            rv = find(v)
            if rv != r0:
                parent[rv] = r0
    roots = np.array([find(i) for i in range(len(verts))])
    face_root = roots[faces[:, 0]]
    uniq, counts = np.unique(face_root, return_counts=True)
    keep_roots = set(uniq[counts >= min_faces].tolist())
    keep = np.array([r in keep_roots for r in face_root])
    print(f'[cave] kept {keep.sum()} / {len(faces)} faces in {len(keep_roots)} component(s)')
    faces = faces[keep]
    used = np.unique(faces)
    remap = np.full(len(verts), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return verts[used], remap[faces]


# ─────────────────────────────────────────────────────────────────────────────
#  GEOMETRY HELPERS  (every helper writes metric UVs + a per-piece random value)
# ─────────────────────────────────────────────────────────────────────────────
def collection(name, parent=None, link=True):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if link:
        target = parent or bpy.context.scene.collection
        if col.name not in target.children:
            target.children.link(col)
    return col


def _layers(bm):
    uv = bm.loops.layers.uv.verify()
    piece = bm.faces.layers.float.get('piece') or bm.faces.layers.float.new('piece')
    return uv, piece


def _faces_of(verts):
    return {f for v in verts for f in v.link_faces}


def add_box(bm, center, size, rot=None, piece=None):
    rot = rot if rot is not None else Matrix.Identity(3)
    m = Matrix.Translation(center) @ rot.to_4x4() @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    uvl, pl = _layers(bm)
    inv = rot.transposed()
    pv = RNG.random() if piece is None else piece
    ou, ov = RNG.uniform(0, 40), RNG.uniform(0, 40)
    for f in _faces_of(res['verts']):
        f[pl] = pv
        f.normal_update()
        nrm = inv @ f.normal
        k = max(range(3), key=lambda i: abs(nrm[i]))
        a, b = [i for i in range(3) if i != k]
        if size[b] > size[a]:
            a, b = b, a
        for loop in f.loops:
            lc = inv @ (loop.vert.co - center)
            loop[uvl].uv = (lc[a] + ou, lc[b] + ov)
    return res['verts']


def add_cylinder(bm, start, end, radius, segments=12, cap=True, radius2=None, piece=None):
    d = end - start
    length = d.length
    if length < 1e-5:
        return []
    q = (d / length).to_track_quat('Z', 'Y').to_matrix()
    mid = (start + end) * 0.5
    m = Matrix.Translation(mid) @ q.to_4x4()
    res = bmesh.ops.create_cone(bm, cap_ends=cap, segments=segments, radius1=radius,
                                radius2=radius if radius2 is None else radius2, depth=length, matrix=m)
    uvl, pl = _layers(bm)
    inv = q.transposed()
    pv = RNG.random() if piece is None else piece
    ou, ov = RNG.uniform(0, 40), RNG.uniform(0, 40)
    for f in _faces_of(res['verts']):
        f[pl] = pv
        f.normal_update()
        cap_face = abs((inv @ f.normal).z) > 0.9
        coords = [inv @ (l.vert.co - mid) for l in f.loops]
        if cap_face:
            for l, c in zip(f.loops, coords):
                l[uvl].uv = (c.x + ou, c.y + ov)
            continue
        angs = [math.atan2(c.y, c.x) for c in coords]
        if max(angs) - min(angs) > math.pi:
            angs = [a + 2 * math.pi if a < 0 else a for a in angs]
        for l, c, a in zip(f.loops, coords, angs):
            l[uvl].uv = (c.z + length / 2 + ou, a * radius + ov)
    return res['verts']


def add_lathe(bm, base, rot, profile, segments=24, caps=(True, True), piece=None):
    """Revolve [(radius, height)] around the local Z axis of rot, placed at base"""
    rot = rot if rot is not None else Matrix.Identity(3)
    uvl, pl = _layers(bm)
    pv = RNG.random() if piece is None else piece
    rings = []
    for r, z in profile:
        ring = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            ring.append(bm.verts.new(base + rot @ Vector((math.cos(a) * r, math.sin(a) * r, z))))
        rings.append(ring)
    faces = []
    vpos = 0.0
    vs = [0.0]
    for j in range(1, len(profile)):
        vpos += math.hypot(profile[j][0] - profile[j - 1][0], profile[j][1] - profile[j - 1][1])
        vs.append(vpos)
    for j in range(len(rings) - 1):
        rmean = (profile[j][0] + profile[j + 1][0]) * 0.5
        for i in range(segments):
            i2 = (i + 1) % segments
            f = bm.faces.new((rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]))
            f[pl] = pv
            u0 = 2 * math.pi * rmean * i / segments
            u1 = 2 * math.pi * rmean * (i + 1) / segments
            for l, uv in zip(f.loops, ((u0, vs[j]), (u1, vs[j]), (u1, vs[j + 1]), (u0, vs[j + 1]))):
                l[uvl].uv = uv
            faces.append(f)
    if caps[0]:
        f = bm.faces.new(list(reversed(rings[0])))
        f[pl] = pv
        faces.append(f)
    if caps[1]:
        f = bm.faces.new(rings[-1])
        f[pl] = pv
        faces.append(f)
    for f in faces[-2:]:
        for l in f.loops:
            c = rot.transposed() @ (l.vert.co - base)
            l[uvl].uv = (c.x, c.y)
    return faces


def frames_along(path, up=Vector((0, 0, 1))):
    out = []
    for i, p in enumerate(path):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        t = (b - a)
        t = t.normalized() if t.length > 1e-6 else Vector((1, 0, 0))
        side = t.cross(up)
        side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
        out.append((p, t, side, side.cross(t)))
    return out


def add_sweep(bm, path, profile, closed=True, piece=None):
    """Sweep a 2D profile [(side, up)] along a 3D path. U = length along the path"""
    uvl, pl = _layers(bm)
    pv = RNG.random() if piece is None else piece
    fr = frames_along(path)
    rings = [[bm.verts.new(p + side * px + upv * py) for px, py in profile] for p, t, side, upv in fr]
    lens = [0.0]
    for i in range(1, len(path)):
        lens.append(lens[-1] + (path[i] - path[i - 1]).length)
    per = [0.0]
    loop = profile + ([profile[0]] if closed else [])
    for i in range(1, len(loop)):
        per.append(per[-1] + math.hypot(loop[i][0] - loop[i - 1][0], loop[i][1] - loop[i - 1][1]))
    n = len(profile)
    count = n if closed else n - 1
    for j in range(len(rings) - 1):
        for i in range(count):
            i2 = (i + 1) % n
            f = bm.faces.new((rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]))
            f[pl] = pv
            for l, uv in zip(f.loops, ((lens[j], per[i]), (lens[j], per[i + 1]), (lens[j + 1], per[i + 1]), (lens[j + 1], per[i]))):
                l[uvl].uv = uv


def look_rot(forward, up=Vector((0, 0, 1))):
    """X = right, Y = forward, Z = up"""
    f = forward.normalized()
    r = f.cross(up)
    if r.length < 1e-4:
        r = Vector((1, 0, 0))
    r.normalize()
    u = r.cross(f)
    return Matrix((r, f, u)).transposed()


def finish_object(name, bm, material, col, bevel=0.0, smooth_angle=35.0, extra_mats=None):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if material:
        mesh.materials.append(material)
    for m in extra_mats or []:
        mesh.materials.append(m)
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    try:
        mesh.shade_smooth()
        mesh.set_sharp_from_angle(angle=math.radians(smooth_angle))
    except (AttributeError, TypeError):
        pass
    if bevel > 0:
        mod = obj.modifiers.new('Bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = 'ANGLE'
        mod.angle_limit = math.radians(40)
        try:
            mod.harden_normals = True
        except AttributeError:
            pass
    return obj


# ─────────────────────────────────────────────────────────────────────────────
#  SHADER NODE BUILDER
# ─────────────────────────────────────────────────────────────────────────────
class NB:
    """Small helper to build node trees in a few lines"""

    def __init__(self, name):
        self.mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.N = self.nt.nodes
        self.L = self.nt.links
        self.N.clear()
        self.out = self.N.new('ShaderNodeOutputMaterial')
        geo = self.N.new('ShaderNodeNewGeometry')
        self.P = geo.outputs['Position']
        self.Nrm = geo.outputs['Normal']
        self.pointiness = geo.outputs['Pointiness']
        self.tc = self.N.new('ShaderNodeTexCoord')
        self.UV = self.tc.outputs['UV']
        self.OBJ = self.tc.outputs['Object']

    def set(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.L.new(val, sock)
        elif val is not None:
            sock.default_value = val

    def node(self, kind, inputs=None, **attrs):
        n = self.N.new(kind)
        for k, v in attrs.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(n.inputs[k], v)
        return n

    def math(self, op, a, b=0.0, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def vec(self, op, a, b=None, s=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.set(n.inputs[0], a)
        if b is not None:
            self.set(n.inputs[1], b)
        if s is not None:
            self.set(n.inputs['Scale'], s)
        return n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']

    def xyz(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.set(n.inputs[0], v)
        return n.outputs

    def combine(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self.set(n.inputs['X'], x)
        self.set(n.inputs['Y'], y)
        self.set(n.inputs['Z'], z)
        return n.outputs[0]

    def scale(self, v, sx, sy, sz):
        return self.vec('MULTIPLY', v, (sx, sy, sz))

    def mix(self, fac, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        self.set(n.inputs[0], fac)
        self.set(n.inputs[6], a)
        self.set(n.inputs[7], b)
        return n.outputs[2]

    def mixf(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT')
        self.set(n.inputs[0], fac)
        self.set(n.inputs[2], a)
        self.set(n.inputs[3], b)
        return n.outputs[0]

    @staticmethod
    def _coord(c):
        """accepts a socket (3D) or a (vector, w, dims) tuple from Coord.at()"""
        if isinstance(c, tuple):
            return c
        return c, None, '3D'

    def noise(self, c, scale, detail=4.0, rough=0.5, distortion=0.0, kind='FBM'):
        vec, w, dims = self._coord(c)
        n = self.node('ShaderNodeTexNoise', noise_dimensions=dims)
        if hasattr(n, 'noise_type'):
            n.noise_type = kind
        self.set(n.inputs['Vector'], vec)
        if w is not None:
            self.set(n.inputs['W'], w)
        self.set(n.inputs['Scale'], scale)
        self.set(n.inputs['Detail'], detail)
        self.set(n.inputs['Roughness'], rough)
        self.set(n.inputs['Distortion'], distortion)
        return n

    def voronoi(self, c, scale, feature='F1', random_=1.0, metric='EUCLIDEAN'):
        vec, w, dims = self._coord(c)
        n = self.node('ShaderNodeTexVoronoi', voronoi_dimensions=dims, feature=feature, distance=metric)
        self.set(n.inputs['Vector'], vec)
        if w is not None:
            self.set(n.inputs['W'], w)
        self.set(n.inputs['Scale'], scale)
        self.set(n.inputs['Randomness'], random_)
        return n

    def wave(self, vec, scale, distortion=4.0, detail=3.0, kind='BANDS', direction='X', profile='SIN'):
        n = self.node('ShaderNodeTexWave', wave_type=kind, bands_direction=direction, wave_profile=profile)
        self.set(n.inputs['Vector'], vec)
        self.set(n.inputs['Scale'], scale)
        self.set(n.inputs['Distortion'], distortion)
        self.set(n.inputs['Detail'], detail)
        return n

    def ramp(self, fac, stops, interp='LINEAR'):
        n = self.node('ShaderNodeValToRGB')
        cr = n.color_ramp
        cr.interpolation = interp
        cr.elements[0].position, cr.elements[0].color = stops[0][0], stops[0][1]
        cr.elements[1].position, cr.elements[1].color = stops[-1][0], stops[-1][1]
        for pos, col in stops[1:-1]:
            e = cr.elements.new(pos)
            e.color = col
        self.set(n.inputs['Fac'], fac)
        return n.outputs['Color']

    def remap(self, val, a, b, c=0.0, d=1.0, clamp=True, interp='LINEAR'):
        n = self.node('ShaderNodeMapRange', clamp=clamp, interpolation_type=interp)
        self.set(n.inputs['Value'], val)
        n.inputs['From Min'].default_value = a
        n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c
        n.inputs['To Max'].default_value = d
        return n.outputs['Result']

    def smooth(self, val, a, b):
        return self.remap(val, a, b, 0.0, 1.0, True, 'SMOOTHSTEP')

    def bump(self, height, strength=0.5, distance=0.02, normal=None):
        n = self.node('ShaderNodeBump')
        self.set(n.inputs['Height'], height)
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = distance
        if normal is not None:
            self.set(n.inputs['Normal'], normal)
        return n.outputs['Normal']

    def attr(self, name, kind='GEOMETRY'):
        return self.node('ShaderNodeAttribute', attribute_name=name, attribute_type=kind)

    def bw(self, col):
        n = self.node('ShaderNodeRGBToBW')
        self.set(n.inputs[0], col)
        return n.outputs[0]

    def hsv(self, col, h=0.5, s=1.0, v=1.0):
        n = self.node('ShaderNodeHueSaturation')
        self.set(n.inputs['Hue'], h)
        self.set(n.inputs['Saturation'], s)
        self.set(n.inputs['Value'], v)
        self.set(n.inputs['Color'], col)
        return n.outputs['Color']

    def overlay(self, col, value, amount):
        """add greyscale detail (0..1, 0.5 neutral) on top of a colour"""
        grey = self.combine(value, value, value)
        return self.mix(amount, col, grey, 'OVERLAY')

    def image(self, img, vector, projection='FLAT', blend=0.0, interp='Linear'):
        n = self.node('ShaderNodeTexImage', image=img, interpolation=interp, projection=projection)
        if projection == 'BOX':
            n.projection_blend = blend
        self.set(n.inputs['Vector'], vector)
        return n

    def principled(self, **inputs):
        n = self.node('ShaderNodeBsdfPrincipled')
        for k, v in inputs.items():
            self.set(n.inputs[k.replace('_', ' ')], v)
        return n

    def output(self, shader, displacement=None, disp_scale=0.1, midlevel=0.5):
        self.set(self.out.inputs['Surface'], shader)
        if displacement is not None:
            d = self.node('ShaderNodeDisplacement')
            self.set(d.inputs['Height'], displacement)
            d.inputs['Midlevel'].default_value = midlevel
            d.inputs['Scale'].default_value = disp_scale
            self.set(self.out.inputs['Displacement'], d.outputs['Displacement'])
            set_displacement_method(self.mat, 'BOTH')
        return self.mat


def set_displacement_method(mat, method):
    for owner in (mat, getattr(mat, 'cycles', None)):
        try:
            owner.displacement_method = method
            return
        except (AttributeError, TypeError):
            continue


class Coord:
    """Texture space for the terrain layers.
    'world': 3D position in metres (used directly in the scene).
    'tile' : the UV square is wrapped onto a 4D torus, so anything built on it tiles
             seamlessly every `tile` metres (used to bake the 4K texture sets).
    at(sh, sv) gives coordinates scaled horizontally (sh) and vertically (sv), so the
    layers can stretch features along the wall's vertical axis in both modes."""

    def __init__(self, nb, mode='world', tile=4.0):
        self.nb, self.mode, self.tile = nb, mode, tile
        self._cache = {}
        if mode == 'tile':
            sep = nb.xyz(nb.UV)
            au = nb.math('MULTIPLY', sep['X'], 2 * math.pi)
            av = nb.math('MULTIPLY', sep['Y'], 2 * math.pi)
            self.au = au
            self.cu, self.su = nb.math('COSINE', au), nb.math('SINE', au)
            self.cv, self.sv = nb.math('COSINE', av), nb.math('SINE', av)

    def at(self, sh=1.0, sv=1.0):
        key = (sh, sv)
        if key in self._cache:
            return self._cache[key]
        nb = self.nb
        if self.mode == 'world':
            v = nb.P if sh == sv == 1.0 else nb.scale(nb.P, sh, sh, sv)
            out = (v, None, '3D')
        else:
            R = self.tile / (2 * math.pi)
            rh, rv = R * sh, R * sv
            vec = nb.combine(nb.math('MULTIPLY', self.cu, rh), nb.math('MULTIPLY', self.su, rh), nb.math('MULTIPLY', self.cv, rv))
            out = (vec, nb.math('MULTIPLY', self.sv, rv), '4D')
        self._cache[key] = out
        return out

    def bands(self, scale, distortion_noise=None, amount=0.0):
        """parallel bands (sand ripples); periodic in tile mode"""
        nb = self.nb
        if self.mode == 'world':
            return nb.wave(nb.P, scale, 6.0 if distortion_noise is None else 0.0, 2.0, 'BANDS', 'X').outputs['Fac']
        k = max(1, round(scale * self.tile * 1.6))
        phase = nb.math('MULTIPLY', self.au, float(k))
        if distortion_noise is not None:
            phase = nb.math('ADD', phase, nb.math('MULTIPLY', distortion_noise, amount))
        return nb.math('ADD', 0.5, nb.math('MULTIPLY', nb.math('SINE', phase), 0.5))


def rgb(r, g, b):
    return (r, g, b, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  TERRAIN LAYERS  (each returns colour, roughness, height, micro detail)
#  Only "material" detail lives here; anything that depends on the world
#  (strata height, dust on ledges, damp bases, the truck road) is added by the
#  terrain shader on top, so the same layer can be baked into a seamless tile.
# ─────────────────────────────────────────────────────────────────────────────
def _ridged(nb, c, scale, detail=7.0, rough=0.6):
    n = nb.noise(c, scale, detail, rough, 0.0, 'RIDGED_MULTIFRACTAL')
    return nb.remap(n.outputs['Fac'], 0.0, 1.6, 0.0, 1.0)


def _cracks(nb, c_warped, c_mask, scale, width, keep=0.5):
    """Fracture lines that do not close into cells: voronoi edges masked by noise"""
    edge = nb.voronoi(c_warped, scale, 'DISTANCE_TO_EDGE').outputs['Distance']
    line = nb.smooth(edge, width, 0.0)
    mask = nb.smooth(nb.noise(c_mask, scale * 0.9, 3).outputs['Fac'], 0.5 - keep * 0.2, 0.62 - keep * 0.2)
    return nb.math('MULTIPLY', line, mask)


def _warp(nb, c, amount, scale=1.0):
    vec, w, dims = c
    n = nb.noise(c, scale, 2).outputs['Color']
    return (nb.vec('ADD', vec, nb.vec('MULTIPLY', nb.vec('SUBTRACT', n, (0.5, 0.5, 0.5)), (amount, amount, amount))), w, dims)


def _facets(nb, c, scale, slope=0.8, jitter=0.35):
    """Chipped stone: every voronoi cell is a randomly tilted plane -> angular facets with sharp creases.
    Returns (height 0..1, per-cell random value)."""
    vec, w, dims = c
    vor = nb.voronoi(c, scale, 'F1')
    d = nb.vec('MULTIPLY', nb.vec('SUBTRACT', vec, vor.outputs['Position']), (scale, scale, scale))
    grad = nb.vec('SUBTRACT', nb.vec('MULTIPLY', vor.outputs['Color'], (2.0, 2.0, 2.0)), (1.0, 1.0, 1.0))
    tilt = nb.vec('DOT_PRODUCT', d, grad)
    rnd = nb.bw(vor.outputs['Color'])
    h = nb.math('ADD', nb.math('MULTIPLY', tilt, slope), nb.math('MULTIPLY', nb.math('SUBTRACT', rnd, 0.5), jitter * 2))
    return nb.math('ADD', nb.math('MULTIPLY', h, 0.5), 0.5), rnd


def layer_cave_rock(nb, c):
    """Cave limestone: angular chipped facets at two scales, ridged relief, hairline cracks, cavity shading"""
    wp = _warp(nb, c.at(), 0.45, 0.7)
    f1, r1 = _facets(nb, wp, 1.3, 0.9)
    f2, r2 = _facets(nb, _warp(nb, c.at(), 0.15, 2.5), 4.2, 0.7)
    f0, r0 = _facets(nb, _warp(nb, c.at(), 0.8, 0.4), 0.45, 0.8)
    swell = nb.noise(c.at(), 0.6, 3).outputs['Fac']
    ridge = _ridged(nb, c.at(), 2.2)
    bumps = nb.noise(c.at(), 16.0, 6, 0.6).outputs['Fac']
    grain = nb.noise(c.at(), 80.0, 4, 0.6).outputs['Fac']
    crack = nb.math('MULTIPLY', _cracks(nb, _warp(nb, c.at(), 0.3, 1.5), c.at(), 0.9, 0.008, 0.1), 0.7)
    height = nb.math('ADD', nb.math('MULTIPLY', f1, 0.34), nb.math('MULTIPLY', f2, 0.16))
    height = nb.math('ADD', height, nb.math('ADD', nb.math('MULTIPLY', f0, 0.22), nb.math('MULTIPLY', swell, 0.14)))
    height = nb.math('ADD', height, nb.math('MULTIPLY', ridge, 0.16))
    height = nb.math('ADD', height, nb.math('MULTIPLY', bumps, 0.1))
    height = nb.math('ADD', height, nb.math('MULTIPLY', grain, 0.04))
    height = nb.math('SUBTRACT', height, nb.math('MULTIPLY', crack, 0.2))

    mott = nb.noise(c.at(), 0.8, 4, 0.6).outputs['Fac']
    col = nb.ramp(mott, [(0.3, rgb(0.2, 0.185, 0.16)), (0.5, rgb(0.28, 0.26, 0.225)), (0.7, rgb(0.34, 0.315, 0.275))], 'EASE')
    tone = nb.noise(c.at(), 2.6, 3).outputs['Fac']
    col = nb.mix(nb.math('MULTIPLY', nb.smooth(tone, 0.56, 0.76), 0.45), col, rgb(0.3, 0.22, 0.15))
    col = nb.overlay(col, nb.remap(r0, 0.0, 1.0, 0.42, 0.58), 0.8)
    col = nb.overlay(col, nb.remap(r1, 0.0, 1.0, 0.45, 0.55), 0.6)
    col = nb.overlay(col, nb.remap(r2, 0.0, 1.0, 0.47, 0.53), 0.5)
    cavity = nb.smooth(height, 0.4, 0.15)
    col = nb.mix(nb.math('MULTIPLY', cavity, 0.6), col, rgb(0.06, 0.055, 0.05))
    col = nb.overlay(col, grain, 0.4)
    speck = nb.voronoi(c.at(), 90, 'F1').outputs['Distance']
    col = nb.mix(nb.math('MULTIPLY', nb.smooth(speck, 0.13, 0.05), 0.3), col, rgb(0.05, 0.045, 0.04))
    col = nb.mix(nb.math('MULTIPLY', crack, 0.7), col, rgb(0.03, 0.027, 0.023))
    rough = nb.math('ADD', nb.remap(grain, 0.3, 0.7, 0.72, 0.9), nb.math('MULTIPLY', cavity, 0.06))
    return col, rough, height, grain


def layer_quarry_rock(nb, c):
    """Blasted quarry face: tall angular blast facets, vertical drill traces, bedding, weathering"""
    vp = c.at(1.0, 0.35)
    wvp = _warp(nb, vp, 0.35, 0.6)
    f1, r1 = _facets(nb, wvp, 0.8, 1.0)
    f2, r2 = _facets(nb, _warp(nb, c.at(), 0.15, 2.0), 3.2, 0.7)
    ridge = _ridged(nb, c.at(1.0, 0.5), 1.8)
    bumps = nb.noise(c.at(), 14.0, 6, 0.6).outputs['Fac']
    grain = nb.noise(c.at(), 70.0, 4, 0.6).outputs['Fac']
    holes = c.bands(0.55, nb.noise(c.at(0.3, 0.3), 1.0, 2).outputs['Fac'], 1.5)
    hole_mask = nb.smooth(nb.noise(c.at(0.5, 0.08), 1.0, 2).outputs['Fac'], 0.5, 0.6)
    drill = nb.math('MULTIPLY', nb.smooth(holes, 0.8, 0.97), hole_mask)
    crack = nb.math('MULTIPLY', _cracks(nb, _warp(nb, c.at(1.0, 0.5), 0.3, 1.2), c.at(), 0.6, 0.008, 0.1), 0.7)
    swell = nb.noise(c.at(1.0, 0.6), 0.5, 3).outputs['Fac']
    height = nb.math('ADD', nb.math('MULTIPLY', f1, 0.42), nb.math('MULTIPLY', f2, 0.18))
    height = nb.math('ADD', height, nb.math('MULTIPLY', swell, 0.14))
    height = nb.math('ADD', height, nb.math('MULTIPLY', ridge, 0.15))
    height = nb.math('ADD', height, nb.math('MULTIPLY', bumps, 0.1))
    height = nb.math('ADD', height, nb.math('MULTIPLY', grain, 0.04))
    height = nb.math('SUBTRACT', height, nb.math('ADD', nb.math('MULTIPLY', crack, 0.2), nb.math('MULTIPLY', drill, 0.18)))

    mott = nb.noise(c.at(), 0.55, 4, 0.6).outputs['Fac']
    col = nb.ramp(mott, [(0.3, rgb(0.4, 0.37, 0.32)), (0.5, rgb(0.49, 0.46, 0.4)), (0.7, rgb(0.56, 0.53, 0.47))], 'EASE')
    stain = nb.noise(c.at(1.4, 0.12), 1.0, 5).outputs['Fac']
    col = nb.mix(nb.math('MULTIPLY', nb.smooth(stain, 0.52, 0.72), 0.4), col, rgb(0.27, 0.22, 0.16))
    col = nb.overlay(col, nb.remap(r1, 0.0, 1.0, 0.42, 0.58), 0.7)
    col = nb.overlay(col, nb.remap(r2, 0.0, 1.0, 0.46, 0.54), 0.5)
    cavity = nb.smooth(height, 0.4, 0.14)
    col = nb.mix(nb.math('MULTIPLY', cavity, 0.5), col, rgb(0.12, 0.11, 0.09))
    col = nb.overlay(col, grain, 0.35)
    col = nb.mix(nb.math('MULTIPLY', crack, 0.7), col, rgb(0.08, 0.07, 0.06))
    rough = nb.remap(grain, 0.3, 0.7, 0.8, 0.95)
    return col, rough, height, grain


def _pebbles(nb, c, scale, size, density_noise):
    """Rounded pebbles: dome height per voronoi cell, masked so they cluster"""
    vor = nb.voronoi(c, scale, 'F1')
    r = nb.math('DIVIDE', vor.outputs['Distance'], size)
    dome = nb.math('SQRT', nb.math('MAXIMUM', nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', r, r)), 0.0))
    mask = nb.smooth(density_noise, 0.44, 0.58)
    return nb.math('MULTIPLY', dome, mask), vor.outputs['Color']


def layer_sand(nb, c):
    """Loose mine sand: fine grain, grit, pebbles, soft ripples, compacted patches"""
    base = nb.noise(c.at(), 1.4, 5, 0.6).outputs['Fac']
    col = nb.ramp(base, [(0.3, rgb(0.28, 0.25, 0.21)), (0.5, rgb(0.34, 0.3, 0.25)), (0.7, rgb(0.3, 0.28, 0.25))])
    packed = nb.smooth(nb.noise(c.at(), 0.9, 3).outputs['Fac'], 0.52, 0.68)
    col = nb.mix(nb.math('MULTIPLY', packed, 0.4), col, rgb(0.18, 0.155, 0.125))
    grain = nb.noise(c.at(), 320, 2, 0.5).outputs['Fac']
    grit = nb.voronoi(c.at(), 120, 'F1')
    grit_m = nb.smooth(grit.outputs['Distance'], 0.3, 0.12)
    col = nb.overlay(col, grain, 0.6)
    col = nb.mix(nb.math('MULTIPLY', grit_m, 0.5), col,
                 nb.ramp(nb.bw(grit.outputs['Color']), [(0.0, rgb(0.08, 0.07, 0.06)), (0.5, rgb(0.33, 0.3, 0.26)), (1.0, rgb(0.45, 0.42, 0.37))]))
    peb_h, peb_c = _pebbles(nb, c.at(), 22.0, 0.3, nb.noise(c.at(), 1.6, 2).outputs['Fac'])
    peb_mask = nb.smooth(peb_h, 0.0, 0.25)
    peb_col = nb.ramp(nb.bw(peb_c), [(0.0, rgb(0.09, 0.08, 0.07)), (0.35, rgb(0.28, 0.25, 0.21)),
                                                   (0.7, rgb(0.19, 0.17, 0.15)), (1.0, rgb(0.4, 0.36, 0.31))])
    col = nb.mix(peb_mask, col, peb_col)
    rip_n = nb.noise(c.at(), 0.8, 2).outputs['Fac']
    ripple = c.bands(2.2, rip_n, 7.0)
    height = nb.math('ADD', nb.math('MULTIPLY', ripple, 0.08), nb.math('MULTIPLY', peb_h, 0.45))
    height = nb.math('ADD', height, nb.math('MULTIPLY', nb.noise(c.at(), 3.0, 5).outputs['Fac'], 0.3))
    height = nb.math('ADD', height, nb.math('ADD', nb.math('MULTIPLY', grain, 0.05), nb.math('MULTIPLY', grit_m, 0.06)))
    rough = nb.math('SUBTRACT', 0.96, nb.math('MULTIPLY', peb_mask, 0.22))
    return col, rough, height, grain


def layer_dirt(nb, c):
    """Quarry floor: pale dust over compacted ground, gravel and dried cracks"""
    base = nb.noise(c.at(), 0.9, 5, 0.6).outputs['Fac']
    col = nb.ramp(base, [(0.3, rgb(0.3, 0.27, 0.225)), (0.55, rgb(0.37, 0.335, 0.28)), (0.75, rgb(0.29, 0.265, 0.23))])
    grain = nb.noise(c.at(), 240, 2).outputs['Fac']
    col = nb.overlay(col, grain, 0.5)
    grit = nb.voronoi(c.at(), 80, 'F1')
    grit_m = nb.smooth(grit.outputs['Distance'], 0.28, 0.1)
    col = nb.mix(nb.math('MULTIPLY', grit_m, 0.45), col,
                 nb.ramp(nb.bw(grit.outputs['Color']), [(0.0, rgb(0.12, 0.11, 0.1)), (1.0, rgb(0.5, 0.47, 0.42))]))
    grav_h, grav_c = _pebbles(nb, c.at(), 11.0, 0.32, nb.noise(c.at(), 1.1, 2).outputs['Fac'])
    gmask = nb.smooth(grav_h, 0.0, 0.25)
    col = nb.mix(gmask, col, nb.ramp(nb.bw(grav_c), [(0.0, rgb(0.16, 0.145, 0.13)), (1.0, rgb(0.46, 0.43, 0.38))]))
    dry = nb.smooth(nb.noise(c.at(), 0.5, 2).outputs['Fac'], 0.55, 0.7)
    cracks = nb.math('MULTIPLY', _cracks(nb, _warp(nb, c.at(), 0.2, 2.0), c.at(), 2.2, 0.015, 0.7), dry)
    col = nb.mix(nb.math('MULTIPLY', cracks, 0.6), col, rgb(0.13, 0.115, 0.1))
    height = nb.math('ADD', nb.math('MULTIPLY', grav_h, 0.45), nb.math('MULTIPLY', nb.noise(c.at(), 2.2, 5).outputs['Fac'], 0.35))
    height = nb.math('ADD', height, nb.math('MULTIPLY', grit_m, 0.05))
    height = nb.math('SUBTRACT', height, nb.math('MULTIPLY', cracks, 0.15))
    rough = nb.math('SUBTRACT', 0.95, nb.math('MULTIPLY', gmask, 0.15))
    return col, rough, height, grain


TERRAIN_LAYERS = {
    'cave_rock':   (layer_cave_rock, 5.0),       # function, tile size (m)
    'cave_sand':   (layer_sand, 3.0),
    'quarry_rock': (layer_quarry_rock, 8.0),
    'quarry_dirt': (layer_dirt, 5.0),
}


def baked_set(tex_dir, name):
    """Load a baked texture set (albedo / roughness / height) or None"""
    if not tex_dir:
        return None
    files = {ch: os.path.join(tex_dir, f'{name}_{ch}.png') for ch in ('albedo', 'roughness', 'height')}
    if not all(os.path.exists(f) for f in files.values()):
        return None
    out = {}
    for ch, path in files.items():
        img = bpy.data.images.load(path, check_existing=True)
        if ch != 'albedo':
            img.colorspace_settings.name = 'Non-Color'
        out[ch] = img
    return out


def terrain_material(tex_dir=None):
    """Cave rock / sand / quarry rock / quarry dirt blended by the 'Layers' vertex colour
    (R = sand, G = quarry wall, B = quarry floor, A = damp) with world-scale variation on top.
    Uses the baked 4K sets from tex_dir when present (fast), else the procedural layers."""
    nb = NB('Cave_Terrain_4Layer')
    P, N = nb.P, nb.Nrm
    layers = nb.node('ShaderNodeVertexColor', layer_name='Layers')
    sep = nb.node('ShaderNodeSeparateColor')
    nb.set(sep.inputs[0], layers.outputs['Color'])
    w_sand, w_qrock, w_dirt = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    w_wet = layers.outputs['Alpha']

    res = {}
    world = Coord(nb, 'world')
    for key, (fn, tile) in TERRAIN_LAYERS.items():
        tex = baked_set(tex_dir, key)
        if tex:
            vec = nb.vec('DIVIDE', P, (tile, tile, tile))
            alb = nb.image(tex['albedo'], vec, 'BOX', 0.3)
            rou = nb.image(tex['roughness'], vec, 'BOX', 0.3)
            hei = nb.image(tex['height'], vec, 'BOX', 0.3)
            grain = nb.noise(P, 40, 2).outputs['Fac']
            res[key] = (alb.outputs['Color'], nb.bw(rou.outputs['Color']), nb.bw(hei.outputs['Color']), grain)
        else:
            res[key] = fn(nb, world)
    rc, rr, rh, rgrain = res['cave_rock']
    qc, qr, qh, _ = res['quarry_rock']
    sc, sr, sh, sgrain = res['cave_sand']
    dc, dr, dh, _ = res['quarry_dirt']

    # --- world-scale variation on the rock ---------------------------------------
    z = nb.xyz(P)['Z']
    warp = nb.noise(P, 0.12, 2).outputs['Fac']
    band = nb.math('FRACT', nb.math('MULTIPLY', nb.math('ADD', z, nb.math('MULTIPLY', warp, 3.5)), 0.34))
    strata = nb.ramp(band, [(0.0, rgb(0.9, 0.87, 0.83)), (0.22, rgb(1.0, 0.95, 0.87)), (0.4, rgb(0.82, 0.82, 0.84)),
                            (0.62, rgb(0.58, 0.58, 0.61)), (0.8, rgb(0.95, 0.86, 0.75)), (1.0, rgb(0.9, 0.87, 0.83))], 'EASE')
    rc = nb.mix(0.85, rc, strata, 'MULTIPLY')
    big = nb.noise(P, 0.2, 3).outputs['Fac']
    rc = nb.mix(nb.remap(big, 0.35, 0.7, 0.0, 0.45), rc, rgb(0.35, 0.33, 0.31), 'MULTIPLY')
    streak = nb.math('MULTIPLY', nb.smooth(nb.noise(nb.scale(P, 1.4, 1.4, 0.12), 1.0, 3).outputs['Fac'], 0.58, 0.72), 0.45)
    rc = nb.mix(streak, rc, rgb(0.2, 0.09, 0.035))
    qbig = nb.noise(P, 0.08, 2).outputs['Fac']
    qc = nb.mix(nb.remap(qbig, 0.3, 0.7, 0.0, 0.35), qc, rgb(0.62, 0.58, 0.52), 'MULTIPLY')
    qstain = nb.math('MULTIPLY', nb.smooth(nb.noise(nb.scale(P, 0.5, 0.5, 0.06), 1.0, 3).outputs['Fac'], 0.55, 0.75), 0.4)
    qc = nb.mix(qstain, qc, rgb(0.19, 0.16, 0.12))

    up = nb.xyz(N)['Z']
    dust_n = nb.remap(nb.noise(P, 1.3, 3).outputs['Fac'], 0.35, 0.6, 0.35, 0.9)
    wall_c = nb.mix(w_qrock, rc, qc)
    dust = nb.math('MULTIPLY', nb.smooth(up, 0.3, 0.75), dust_n)
    wall_c = nb.mix(dust, wall_c, nb.mix(w_qrock, rgb(0.3, 0.265, 0.215), rgb(0.47, 0.44, 0.39)))
    edges = nb.math('MULTIPLY', nb.smooth(nb.pointiness, 0.52, 0.6), 0.25)
    wall_c = nb.mix(edges, wall_c, rgb(0.45, 0.42, 0.37))
    wall_r = nb.mixf(w_qrock, rr, qr)
    wall_h = nb.mixf(w_qrock, rh, qh)

    # --- the truck road to the portal (tyre ruts in the quarry dirt) ------------------
    E, into, along = entrance_frame()
    rel = nb.vec('SUBTRACT', P, (E.x, E.y, E.z))
    lat = nb.math('ABSOLUTE', nb.vec('DOT_PRODUCT', rel, (along.x, along.y, 0.0)))
    fwd = nb.vec('DOT_PRODUCT', rel, (-into.x, -into.y, 0.0))
    lat = nb.math('ADD', lat, nb.math('MULTIPLY', nb.noise(P, 0.15, 2).outputs['Fac'], 1.2))
    road = nb.math('MULTIPLY', nb.smooth(lat, 3.4, 2.4), nb.smooth(fwd, -1.0, 1.5))
    rut = nb.math('MULTIPLY', nb.smooth(nb.math('ABSOLUTE', nb.math('SUBTRACT', lat, 1.0)), 0.32, 0.1), road)
    tread = nb.math('ADD', 0.5, nb.math('MULTIPLY', nb.math('SINE', nb.math('MULTIPLY', fwd, 60.0)), 0.5))
    dc = nb.mix(nb.math('MULTIPLY', road, 0.55), dc, rgb(0.47, 0.44, 0.39))
    dc = nb.mix(nb.math('MULTIPLY', rut, 0.5), dc, rgb(0.24, 0.215, 0.18))
    dh = nb.math('SUBTRACT', dh, nb.math('MULTIPLY', rut, nb.math('ADD', 0.3, nb.math('MULTIPLY', tread, 0.1))))
    dr = nb.math('SUBTRACT', dr, nb.math('MULTIPLY', road, 0.08))

    # --- height blend: loose material settles in the low parts of the rock first ------
    brk = nb.noise(P, 1.1, 3).outputs['Fac']

    def hblend(weight):
        m = nb.math('ADD', nb.math('MULTIPLY', weight, 2.2), nb.math('MULTIPLY', nb.math('SUBTRACT', 0.5, wall_h), 1.4))
        m = nb.math('ADD', m, nb.math('MULTIPLY', nb.math('SUBTRACT', brk, 0.5), 0.8))
        return nb.remap(nb.math('SUBTRACT', m, 0.9), 0.0, 0.35, 0.0, 1.0, True, 'SMOOTHSTEP')

    m_sand = hblend(w_sand)
    m_dirt = hblend(w_dirt)
    col = nb.mix(m_dirt, nb.mix(m_sand, wall_c, sc), dc)
    rough = nb.mixf(m_dirt, nb.mixf(m_sand, wall_r, sr), dr)
    loose_h = lambda h: nb.math('ADD', nb.math('MULTIPLY', h, 0.35), 0.3)
    height = nb.mixf(m_dirt, nb.mixf(m_sand, wall_h, loose_h(sh)), loose_h(dh))

    # damp walls near the floor inside the mine
    wet = nb.math('MULTIPLY', w_wet, nb.smooth(nb.noise(P, 0.8, 3).outputs['Fac'], 0.35, 0.6))
    col = nb.mix(nb.math('MULTIPLY', wet, 0.6), col, rgb(0.42, 0.4, 0.38), 'MULTIPLY')
    rough = nb.mixf(nb.math('MULTIPLY', wet, 0.7), rough, 0.3)

    # quarry walls get bigger displacement than the cave
    amp = nb.math('ADD', 1.0, nb.math('MULTIPLY', w_qrock, 1.6))
    height = nb.math('ADD', 0.5, nb.math('MULTIPLY', nb.math('SUBTRACT', height, 0.5), amp))

    micro = nb.mixf(m_sand, rgrain, sgrain)
    normal = nb.bump(micro, 0.2, 0.004)
    bsdf = nb.principled(Base_Color=col, Roughness=rough, Normal=normal)
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    return nb.output(bsdf.outputs[0], height, DISPLACEMENT, 0.5)


# ─────────────────────────────────────────────────────────────────────────────
#  PROP MATERIALS
# ─────────────────────────────────────────────────────────────────────────────
def wood_material(name='Timber_Weathered', tint=(1.0, 1.0, 1.0), grey=0.5):
    """Rough-sawn old timber. Grain follows U (the long axis) of the metric UVs"""
    nb = NB(name)
    piece = nb.attr('piece').outputs['Fac']
    uv = nb.vec('ADD', nb.UV, nb.vec('MULTIPLY', piece, (37.0, 19.0, 11.0)))
    streaks = nb.noise(nb.scale(uv, 0.6, 14.0, 1.0), 1.0, 8, 0.6).outputs['Fac']
    rings = nb.wave(nb.scale(uv, 1.0, 1.0, 1.0), 9.0, 10.0, 4.0, 'BANDS', 'Y').outputs['Fac']
    knots = nb.voronoi(nb.scale(uv, 0.4, 1.4, 1.0), 2.0, 'F1').outputs['Distance']
    knot = nb.smooth(knots, 0.12, 0.02)
    cracks = nb.smooth(nb.voronoi(nb.scale(uv, 0.08, 3.0, 1.0), 3.0, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.04, 0.0)
    g = nb.math('ADD', nb.math('MULTIPLY', rings, 0.45), nb.math('MULTIPLY', streaks, 0.55))
    col = nb.ramp(g, [(0.2, rgb(0.085 * tint[0], 0.058 * tint[1], 0.036 * tint[2])),
                      (0.55, rgb(0.20 * tint[0], 0.14 * tint[1], 0.085 * tint[2])),
                      (0.85, rgb(0.28 * tint[0], 0.2 * tint[1], 0.125 * tint[2]))])
    weather = nb.remap(nb.noise(nb.P, 0.9, 3).outputs['Fac'], 0.35, 0.7, 0.0, grey)
    col = nb.mix(weather, col, rgb(0.24, 0.22, 0.2))
    col = nb.hsv(col, 0.5, 1.0, nb.remap(piece, 0.0, 1.0, 0.75, 1.2))
    col = nb.mix(knot, col, rgb(0.05, 0.03, 0.02))
    col = nb.mix(nb.math('MULTIPLY', cracks, 0.9), col, rgb(0.015, 0.01, 0.008))
    edge = nb.smooth(nb.pointiness, 0.5, 0.56)
    col = nb.mix(nb.math('MULTIPLY', edge, 0.35), col, rgb(0.36, 0.33, 0.28))
    height = nb.math('SUBTRACT', nb.math('MULTIPLY', g, 0.5), nb.math('MULTIPLY', cracks, 0.6))
    normal = nb.bump(height, 0.5, 0.004)
    bsdf = nb.principled(Base_Color=col, Roughness=nb.remap(streaks, 0.3, 0.7, 0.78, 0.94), Normal=normal)
    return nb.output(bsdf.outputs[0])


def painted_metal_material(name, paint, rust_amount=0.45, metallic_paint=0.25):
    """Painted steel with chipped edges, rust patches and grime"""
    nb = NB(name)
    P = nb.P
    n1 = nb.noise(P, 2.4, 8, 0.6).outputs['Fac']
    n2 = nb.noise(P, 11.0, 6, 0.55).outputs['Fac']
    edge = nb.smooth(nb.pointiness, 0.505, 0.56)
    rust = nb.math('ADD', nb.smooth(n1, 0.72 - rust_amount * 0.3, 0.8 - rust_amount * 0.25), nb.math('MULTIPLY', edge, rust_amount * 1.6))
    rust = nb.math('MINIMUM', nb.math('MULTIPLY', rust, nb.remap(n2, 0.3, 0.7, 0.6, 1.3)), 1.0)
    rust_col = nb.ramp(n2, [(0.3, rgb(0.13, 0.05, 0.02)), (0.55, rgb(0.35, 0.13, 0.04)), (0.8, rgb(0.18, 0.08, 0.03))])
    paint_col = nb.mix(nb.remap(n1, 0.3, 0.7, 0.0, 0.25), rgb(*paint), rgb(0.05, 0.045, 0.04))
    col = nb.mix(rust, paint_col, rust_col)
    bare = nb.math('MULTIPLY', edge, nb.math('SUBTRACT', 1.0, rust))
    col = nb.mix(nb.math('MULTIPLY', bare, 0.6), col, rgb(0.35, 0.34, 0.33))
    metal = nb.mixf(rust, nb.math('ADD', metallic_paint, nb.math('MULTIPLY', bare, 0.6)), 0.0)
    rough = nb.mixf(rust, nb.remap(n2, 0.3, 0.7, 0.38, 0.6), 0.92)
    height = nb.math('ADD', nb.math('MULTIPLY', rust, 0.5), nb.math('MULTIPLY', n2, 0.2))
    bsdf = nb.principled(Base_Color=col, Metallic=metal, Roughness=rough, Normal=nb.bump(height, 0.35, 0.003))
    return nb.output(bsdf.outputs[0])


def plastic_material(name, color, dirt=0.4):
    nb = NB(name)
    n = nb.noise(nb.P, 3.0, 6).outputs['Fac']
    z = nb.xyz(nb.OBJ)['Z']
    grime = nb.math('MULTIPLY', nb.smooth(z, 0.6, 0.0), dirt)
    streak = nb.math('MULTIPLY', nb.smooth(nb.noise(nb.scale(nb.P, 6, 6, 0.4), 1.0, 4).outputs['Fac'], 0.55, 0.75), dirt * 0.6)
    col = nb.mix(nb.math('ADD', grime, streak), rgb(*color), rgb(0.22, 0.19, 0.15))
    col = nb.mix(0.12, col, nb.ramp(n, [(0.3, rgb(0.3, 0.3, 0.3)), (0.7, rgb(0.7, 0.7, 0.7))]), 'OVERLAY')
    bsdf = nb.principled(Base_Color=col, Roughness=nb.remap(n, 0.3, 0.7, 0.42, 0.62), Normal=nb.bump(n, 0.1, 0.002))
    return nb.output(bsdf.outputs[0])


def brick_material():
    nb = NB('Furnace_Brick')
    uv = nb.scale(nb.UV, 1.0, 1.0, 1.0)
    brick = nb.node('ShaderNodeTexBrick', inputs={'Vector': uv, 'Scale': 3.6, 'Mortar Size': 0.018,
                                                   'Color1': rgb(0.33, 0.12, 0.06), 'Color2': rgb(0.2, 0.075, 0.045),
                                                   'Mortar': rgb(0.2, 0.19, 0.17), 'Brick Width': 0.5, 'Row Height': 0.25})
    n = nb.noise(nb.P, 9.0, 6).outputs['Fac']
    col = nb.mix(0.35, brick.outputs['Color'], nb.ramp(n, [(0.3, rgb(0.25, 0.25, 0.25)), (0.7, rgb(0.75, 0.75, 0.75))]), 'OVERLAY')
    soot = nb.smooth(nb.xyz(nb.P)['Z'], 0.0, 3.0)
    col = nb.mix(nb.math('MULTIPLY', soot, 0.8), col, rgb(0.02, 0.018, 0.016))
    height = nb.math('SUBTRACT', 1.0, brick.outputs['Fac'])
    bsdf = nb.principled(Base_Color=col, Roughness=0.9, Normal=nb.bump(nb.math('ADD', height, nb.math('MULTIPLY', n, 0.3)), 0.6, 0.01))
    return nb.output(bsdf.outputs[0])


def simple_material(name, color, metallic=0.0, roughness=0.6, emission=None, strength=0.0, transmission=0.0, ior=1.45, coat=0.0):
    nb = NB(name)
    bsdf = nb.principled(Base_Color=rgb(*color), Metallic=metallic, Roughness=roughness, IOR=ior)
    if transmission:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    if emission:
        bsdf.inputs['Emission Color'].default_value = rgb(*emission)
        bsdf.inputs['Emission Strength'].default_value = strength
    if coat:
        bsdf.inputs['Coat Weight'].default_value = coat
    return nb.output(bsdf.outputs[0])


def ore_material(name, fleck, metallic, density):
    nb = NB(name)
    P = nb.P
    vor = nb.voronoi(P, density, 'F1')
    n = nb.noise(P, 3.0, 5).outputs['Fac']
    mask = nb.math('MULTIPLY', nb.smooth(vor.outputs['Distance'], 0.32, 0.12), nb.smooth(n, 0.4, 0.6))
    rock = nb.ramp(nb.noise(P, 9.0, 6).outputs['Fac'], [(0.3, rgb(0.07, 0.065, 0.06)), (0.7, rgb(0.2, 0.185, 0.17))])
    col = nb.mix(mask, rock, rgb(*fleck))
    edge = nb.smooth(nb.voronoi(P, 2.5, 'DISTANCE_TO_EDGE').outputs['Distance'], 0.04, 0.0)
    col = nb.mix(nb.math('MULTIPLY', edge, 0.7), col, rgb(0.01, 0.01, 0.01))
    bsdf = nb.principled(Base_Color=col, Metallic=nb.math('MULTIPLY', mask, metallic),
                         Roughness=nb.mixf(mask, 0.85, 0.3),
                         Normal=nb.bump(nb.math('ADD', mask, nb.math('MULTIPLY', n, 0.5)), 0.5, 0.01))
    return nb.output(bsdf.outputs[0])


def crystal_material(name, color):
    nb = NB(name)
    fres = nb.node('ShaderNodeLayerWeight', inputs={'Blend': 0.35})
    core = nb.mix(fres.outputs['Facing'], rgb(*[c * 0.9 for c in color]), rgb(*[c * 0.25 for c in color]))
    inner = nb.voronoi(nb.P, 14.0, 'F1').outputs['Distance']
    bsdf = nb.principled(Base_Color=core, Roughness=0.03, IOR=1.76, Coat_Weight=1.0,
                         Emission_Color=rgb(*color), Emission_Strength=nb.remap(inner, 0.0, 0.5, 1.6, 0.25),
                         Normal=nb.bump(inner, 0.25, 0.01))
    return nb.output(bsdf.outputs[0])


def fabric_duct_material():
    nb = NB('Vent_Duct_Fabric')
    ribs = nb.wave(nb.UV, 3.2, 0.0, 0.0, 'BANDS', 'X').outputs['Fac']
    n = nb.noise(nb.P, 4.0, 6).outputs['Fac']
    col = nb.mix(nb.remap(n, 0.3, 0.7, 0.0, 0.35), rgb(0.62, 0.43, 0.03), rgb(0.18, 0.14, 0.08))
    bsdf = nb.principled(Base_Color=col, Roughness=0.72, Sheen_Weight=0.3, Normal=nb.bump(ribs, 0.7, 0.02))
    return nb.output(bsdf.outputs[0])


def footprint_material(image):
    """Shoe print pressed into the sand (decal with alpha)"""
    nb = NB('Sand_Footprint')
    tex = nb.node('ShaderNodeTexImage', image=image, interpolation='Cubic')
    nb.set(tex.inputs['Vector'], nb.UV)
    sep = nb.node('ShaderNodeSeparateColor')
    nb.set(sep.inputs[0], tex.outputs['Color'])
    depth, rim, alpha = sep.outputs[0], sep.outputs[1], tex.outputs['Alpha']
    grain = nb.noise(nb.P, 240, 2).outputs['Fac']
    col = nb.mix(nb.math('MULTIPLY', depth, 0.6), rgb(0.33, 0.285, 0.225), rgb(0.19, 0.165, 0.13))
    col = nb.mix(0.4, col, nb.ramp(grain, [(0.3, rgb(0.3, 0.3, 0.3)), (0.7, rgb(0.7, 0.7, 0.7))]), 'OVERLAY')
    h = nb.math('ADD', nb.math('SUBTRACT', rim, depth), nb.math('MULTIPLY', grain, 0.08))
    bsdf = nb.principled(Base_Color=col, Roughness=0.95, Normal=nb.bump(h, 1.0, 0.012))
    transp = nb.node('ShaderNodeBsdfTransparent')
    mixs = nb.node('ShaderNodeMixShader')
    nb.set(mixs.inputs[0], alpha)
    nb.set(mixs.inputs[1], transp.outputs[0])
    nb.set(mixs.inputs[2], bsdf.outputs[0])
    return nb.output(mixs.outputs[0])


def footprint_image(w=96, h=256):
    """Procedural boot print: R = depth, G = pushed-up rim, A = mask"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = (x + 0.5) / w, (y + 0.5) / h
    fore = ((u - 0.5) / 0.44) ** 2 + ((v - 0.68) / 0.29) ** 2
    heel = ((u - 0.5) / 0.36) ** 2 + ((v - 0.19) / 0.15) ** 2
    arch = np.where((v > 0.28) & (v < 0.46), ((u - 0.5) / 0.3) ** 2, 9.0)
    d = np.minimum(np.minimum(fore, heel), arch)
    mask = np.clip((1.0 - d) * 4.0, 0, 1)
    lugs = 0.55 + 0.45 * (np.sin(v * 58.0) > 0.1)
    lugs = np.where(np.abs(u - 0.5) < 0.04, 0.4, lugs)
    depth = mask * lugs

    def blur(a, r):
        k = np.ones(2 * r + 1) / (2 * r + 1)
        a = np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 0, a)
        return np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 1, a)

    soft = blur(mask, 6)
    rim = np.clip((soft - mask) * 2.5, 0, 1)
    alpha = np.clip(soft * 1.6, 0, 1)
    img = np.stack([depth, rim, np.zeros_like(depth), alpha], axis=-1).astype(np.float32)
    image = bpy.data.images.get('Footprint_Sand') or bpy.data.images.new('Footprint_Sand', w, h, alpha=True)
    image.pixels.foreach_set(img.ravel())
    image.colorspace_settings.name = 'Non-Color'
    try:
        image.pack()
    except RuntimeError:
        pass
    return image


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD
# ─────────────────────────────────────────────────────────────────────────────
class Cave:
    def __init__(self, fast=False, tex_dir=None):
        self.fast = fast
        self.tex_dir = tex_dir
        self.rng = random.Random(SEED)
        self.mats = {}
        self.lamps = []
        self.sets = {}         # tunnel edge -> timber set positions (for lagging / cables)

    # --- setup -----------------------------------------------------------------
    def reset_scene(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.curves,
                      bpy.data.materials, bpy.data.particles, bpy.data.images):
            for item in list(block):
                block.remove(item)
        for col in list(bpy.data.collections):
            bpy.data.collections.remove(col)
        root = collection('CaveMining')
        self.cols = {k: collection(v, root) for k, v in {
            'shell': 'Cave_Shell', 'entrance': 'Quarry_Entrance', 'timber': 'Timber_Supports',
            'rails': 'Rails_Carts', 'lights': 'Lights', 'ores': 'Ore_Veins', 'crystals': 'Crystals',
            'workshop': 'Workshop', 'props': 'Cave_Props', 'decals': 'Decals', 'cameras': 'Cameras'}.items()}
        self.cols['instances'] = collection('Scatter_Instances', link=False)

    def make_materials(self):
        m = self.mats
        m['terrain'] = terrain_material(self.tex_dir)
        print('[cave] terrain textures: ' + ('baked 4K sets from ' + self.tex_dir if baked_set(self.tex_dir, 'cave_rock') else 'procedural (run --bake for the fast 4K sets)'))
        m['wood'] = wood_material()
        m['wood_new'] = wood_material('Timber_Fresh', (1.25, 1.15, 1.0), 0.15)
        m['rail'] = painted_metal_material('Rail_Steel', (0.09, 0.085, 0.08), 0.55, 0.6)
        m['cart'] = painted_metal_material('Cart_Paint', (0.2, 0.26, 0.23), 0.6)
        m['iron'] = painted_metal_material('Iron_Dark', (0.05, 0.05, 0.052), 0.35, 0.7)
        m['green'] = painted_metal_material('Machine_Green', (0.07, 0.16, 0.1), 0.3)
        m['yellow'] = painted_metal_material('Paint_Yellow', (0.62, 0.42, 0.02), 0.25)
        m['red_tank'] = painted_metal_material('Tank_Red', (0.32, 0.05, 0.03), 0.6)
        m['pipe'] = painted_metal_material('Pipe_Rust', (0.2, 0.08, 0.05), 0.8)
        m['drum_blue'] = plastic_material('Drum_Blue_Plastic', (0.03, 0.12, 0.35))
        m['drum_black'] = painted_metal_material('Drum_Black', (0.02, 0.02, 0.022), 0.3, 0.4)
        m['toilet'] = plastic_material('Toilet_Teal', (0.12, 0.3, 0.28), 0.5)
        m['toilet_roof'] = plastic_material('Toilet_White', (0.62, 0.62, 0.6), 0.5)
        m['brick'] = brick_material()
        m['duct'] = fabric_duct_material()
        m['bulb'] = simple_material('Lamp_Bulb', (1.0, 0.8, 0.5), emission=(1.0, 0.62, 0.3), strength=90.0)
        m['glass'] = simple_material('Lamp_Glass', (0.9, 0.9, 0.85), roughness=0.05, transmission=1.0, ior=1.45)
        m['cable'] = simple_material('Cable_Rubber', (0.012, 0.012, 0.012), roughness=0.55)
        m['flood'] = simple_material('Flood_Lens', (1.0, 1.0, 0.95), emission=(1.0, 0.95, 0.85), strength=60.0)
        m['molten'] = simple_material('Molten_Glow', (1.0, 0.35, 0.05), emission=(1.0, 0.3, 0.04), strength=45.0)
        m['coal'] = simple_material('Coal', (0.012, 0.012, 0.013), roughness=0.35, coat=0.3)
        m['gold'] = simple_material('Gold_Bar', (1.0, 0.72, 0.28), metallic=1.0, roughness=0.18)
        m['stone'] = ore_material('Loose_Stone', (0.3, 0.27, 0.23), 0.0, 3.0)
        ores = {
            'coal':    ((0.02, 0.02, 0.022), 0.3, 9.0),
            'copper':  ((0.78, 0.40, 0.18), 1.0, 7.0),
            'iron':    ((0.42, 0.18, 0.10), 0.6, 8.0),
            'tin':     ((0.62, 0.63, 0.66), 1.0, 7.0),
            'lead':    ((0.24, 0.27, 0.33), 0.9, 7.0),
            'bauxite': ((0.55, 0.22, 0.10), 0.1, 6.0),
            'gold':    ((1.00, 0.74, 0.25), 1.0, 8.0),
        }
        for name, (col, met, dens) in ores.items():
            m['ore_' + name] = ore_material('Ore_' + name.capitalize(), col, met, dens)
        for name, col in {'ruby': (1.0, 0.05, 0.07), 'emerald': (0.06, 1.0, 0.28),
                          'sapphire': (0.1, 0.28, 1.0), 'diamond': (0.85, 0.95, 1.0)}.items():
            m['crystal_' + name] = crystal_material('Crystal_' + name.capitalize(), col)
        self.foot_img = footprint_image()
        m['footprint'] = footprint_material(self.foot_img)

    # --- cave shell --------------------------------------------------------------
    def build_shell(self):
        t0 = time.time()
        F, lo, floor_at, ext = build_field()
        verts, faces = surface_nets(F, lo)
        del F
        verts, faces = keep_big_components(verts, faces)

        mesh = bpy.data.meshes.new('Cave_Shell')
        mesh.from_pydata(verts.tolist(), [], faces.tolist())
        mesh.validate(clean_customdata=False)
        mesh.update()
        try:
            mesh.shade_smooth()
        except AttributeError:
            mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
        mesh.materials.append(self.mats['terrain'])
        obj = bpy.data.objects.new('Cave_Shell', mesh)
        self.cols['shell'].objects.link(obj)
        self.shell = obj
        self.bvh = BVHTree.FromPolygons([v.co for v in mesh.vertices], [p.vertices for p in mesh.polygons])
        print(f'[cave] shell: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces ({time.time() - t0:.0f}s)')

        # --- per-vertex terrain layers ------------------------------------------
        nv = len(mesh.vertices)
        co = np.zeros(nv * 3); mesh.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        vn = np.zeros(nv * 3)
        try:
            mesh.vertex_normals.foreach_get('vector', vn)
        except AttributeError:
            mesh.vertices.foreach_get('normal', vn)
        vn = vn.reshape(-1, 3)
        gi = np.clip(np.round((co - np.array([lo.x, lo.y, lo.z])) / VOXEL).astype(np.int64), 0, np.array(ext.shape) - 1)
        e_w = ext[gi[:, 0], gi[:, 1], gi[:, 2]].astype(np.float64)
        fl = floor_at[gi[:, 0], gi[:, 1], gi[:, 2]].astype(np.float64)
        E, into, along = entrance_frame()
        s = -((co[:, 0] - E.x) * into.x + (co[:, 1] - E.y) * into.y)
        e_w = np.maximum(e_w, smoothstep(-5.0, 1.0, s))

        # smooth the exterior weight across the mesh so the portal blends
        edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 3]], faces[:, [3, 0]]])
        for _ in range(4):
            acc = np.zeros(nv); cnt = np.zeros(nv)
            np.add.at(acc, edges[:, 0], e_w[edges[:, 1]]); np.add.at(cnt, edges[:, 0], 1)
            np.add.at(acc, edges[:, 1], e_w[edges[:, 0]]); np.add.at(cnt, edges[:, 1], 1)
            e_w = 0.5 * e_w + 0.5 * acc / np.maximum(cnt, 1)

        nz = vn[:, 2]
        flat = smoothstep(0.42, 0.8, nz)
        sand = flat * (1 - e_w)
        dirt = flat * e_w
        qrock = (1 - flat) * e_w
        wet = np.clip(1.0 - (co[:, 2] - fl) / 1.4, 0, 1) * (1 - flat) * (1 - e_w)
        layer = np.stack([sand, qrock, dirt, wet], axis=1).astype(np.float32)
        attr = mesh.color_attributes.new('Layers', 'FLOAT_COLOR', 'POINT')
        attr.data.foreach_set('color', layer.ravel())
        mesh.color_attributes.active_color = attr
        self.layer = layer
        self.vco = co

        # scatter density groups
        scree = smoothstep(0.2, 0.5, nz) * (1 - smoothstep(0.6, 0.85, nz)) * (1 - e_w)
        self._vgroup(obj, 'sand', sand)
        self._vgroup(obj, 'scree', scree)
        self._vgroup(obj, 'quarry_floor', dirt)

        # metric box-projection UVs (for export / baking)
        uv = mesh.uv_layers.new(name='UVMap')
        fn = np.zeros(len(mesh.polygons) * 3); mesh.polygons.foreach_get('normal', fn); fn = fn.reshape(-1, 3)
        vidx = np.zeros(len(mesh.loops), dtype=np.int64); mesh.loops.foreach_get('vertex_index', vidx)
        totals = np.zeros(len(mesh.polygons), dtype=np.int64); mesh.polygons.foreach_get('loop_total', totals)
        n = np.abs(fn[np.repeat(np.arange(len(mesh.polygons)), totals)])
        p = co[vidx] / 4.0
        top = n[:, 2] >= np.maximum(n[:, 0], n[:, 1])
        u = np.where(top, p[:, 0], np.where(n[:, 0] > n[:, 1], p[:, 1], p[:, 0]))
        v = np.where(top, p[:, 1], p[:, 2])
        uvs = np.zeros(len(mesh.loops) * 2); uvs[0::2] = u; uvs[1::2] = v
        uv.data.foreach_set('uv', uvs)

        # GTA collision proxy (floor = SAND_LOOSE, walls = ROCK - see README)
        col_obj = obj.copy()
        col_obj.data = mesh.copy()
        col_obj.name = 'Cave_Collision'
        mod = col_obj.modifiers.new('Decimate', 'DECIMATE')
        mod.ratio = 0.3
        col_obj.hide_render = True
        col_obj.display_type = 'WIRE'
        self.cols['shell'].objects.link(col_obj)
        col_obj.hide_set(True)

    def add_displacement(self):
        """Render-time micro displacement of the rock + sand (adaptive subdivision, Cycles)"""
        if self.fast:
            set_displacement_method(self.mats['terrain'], 'BUMP')
            return
        try:
            bpy.context.scene.cycles.feature_set = 'EXPERIMENTAL'
            self.shell.cycles.use_adaptive_subdivision = True
        except AttributeError:
            pass
        sub = self.shell.modifiers.new('Displace_Subdiv', 'SUBSURF')
        sub.levels = 0
        sub.render_levels = 2
        sub.subdivision_type = 'SIMPLE'

    def _vgroup(self, obj, name, weights, bins=24):
        vg = obj.vertex_groups.new(name=name)
        q = np.round(np.clip(weights, 0, 1) * bins).astype(np.int64)
        for b in range(1, bins + 1):
            ids = np.nonzero(q == b)[0]
            if len(ids):
                vg.add(ids.tolist(), b / bins, 'REPLACE')

    # --- raycasts ------------------------------------------------------------------
    def ray(self, origin, direction, dist=30.0):
        hit, normal, _, d = self.bvh.ray_cast(origin, direction.normalized(), dist)
        return hit, normal, d

    def floor_at(self, p, up=2.5):
        hit, n, d = self.ray(p + Vector((0, 0, up)), Vector((0, 0, -1)), 12.0)
        return hit

    def floor_n(self, p, up=2.5):
        hit, n, d = self.ray(p + Vector((0, 0, up)), Vector((0, 0, -1)), 12.0)
        return hit, n

    # --- quarry entrance -----------------------------------------------------------
    def quarry_point(self, s, t, lift=0.0):
        """Ground point s metres in front of the wall, t metres along it"""
        E, into, along = entrance_frame()
        p = E - into * s + along * t
        hit = self.floor_at(Vector((p.x, p.y, E.z + 1.5)), up=3.0)
        return (hit if hit else Vector((p.x, p.y, E.z))) + Vector((0, 0, lift))

    def build_portal(self):
        """Timber mine portal in the quarry wall, like the real quarry entrance"""
        E, into, along = entrance_frame()
        wood = bmesh.new()
        iron = bmesh.new()
        rot = look_rot(into)
        for depth in (0.6, 2.4):
            base = E + into * depth
            fl = self.floor_at(base + Vector((0, 0, 1.0))) or base
            h = 3.6
            for sgn in (-1, 1):
                p = fl + along * (1.75 * sgn)
                add_box(wood, p + Vector((0, 0, h / 2)), (0.36, 0.36, h), rot)
                # foot block
                add_box(wood, p + Vector((0, 0, 0.1)), (0.5, 0.5, 0.2), rot)
            top = fl + Vector((0, 0, h + 0.22))
            add_cylinder(wood, top - along * 2.5, top + along * 2.5, 0.24, 14)
            for sgn in (-1, 1):
                b0 = fl + along * (1.62 * sgn) + Vector((0, 0, h - 0.9))
                b1 = fl + along * (1.1 * sgn) + Vector((0, 0, h))
                add_box(wood, (b0 + b1) / 2, (0.16, 0.16, (b1 - b0).length + 0.15),
                        look_rot(into) @ Matrix.Rotation(math.atan2(0.52, 0.9) * -sgn, 3, 'Y'))
        # lagging planks over both sets + header board
        fl0 = self.floor_at(E + into * 1.5 + Vector((0, 0, 1.0))) or E
        for k in range(-5, 6):
            p = fl0 + along * (k * 0.34) + Vector((0, 0, 4.12))
            add_box(wood, p, (0.3, 2.6, 0.06), rot)
        add_box(wood, E + into * 0.35 + Vector((0, 0, (self.floor_at(E + Vector((0, 0, 1))) or E).z - E.z + 4.45)),
                (3.6, 0.08, 0.5), rot)
        # iron straps + bolts on the posts
        for depth in (0.6, 2.4):
            fl = self.floor_at(E + into * depth + Vector((0, 0, 1.0))) or E
            for sgn in (-1, 1):
                p = fl + along * (1.75 * sgn) + Vector((0, 0, 3.2))
                add_box(iron, p, (0.4, 0.4, 0.06), rot)
        finish_object('Portal_Timber', wood, self.mats['wood'], self.cols['entrance'], bevel=0.02)
        finish_object('Portal_Iron', iron, self.mats['iron'], self.cols['entrance'], bevel=0.005)

    def build_flatbed(self, pos, fwd):
        """Flat-bed rail cart with a timber load (as parked outside the real portal)"""
        rot = look_rot(fwd)
        side = Vector((-fwd.y, fwd.x, 0))
        steel = bmesh.new(); deck = bmesh.new(); wheels = bmesh.new()
        c = pos + Vector((0, 0, 0.55))
        for sgn in (-1, 1):
            add_box(steel, c + side * 0.48 * sgn, (0.1, 2.6, 0.16), rot)
        for k in (-1.2, 0.0, 1.2):
            add_box(steel, c + fwd * k, (1.05, 0.1, 0.12), rot)
        for k in range(8):
            add_box(deck, c + fwd * (-1.2 + k * 0.34) + Vector((0, 0, 0.12)), (1.25, 0.3, 0.05), rot)
        for sx in (-0.45, 0.45):
            for sy in (-0.85, 0.85):
                wc = pos + side * sx + fwd * sy + Vector((0, 0, 0.26))
                add_lathe(wheels, wc - side * 0.05 * (1 if sx > 0 else -1), look_rot(side) @ Matrix.Rotation(math.radians(90), 3, 'X'),
                          [(0.05, -0.05), (0.22, -0.05), (0.22, 0.02), (0.26, 0.03), (0.26, 0.06), (0.05, 0.06)], 16)
            add_cylinder(steel, pos + side * -0.55 + fwd * 0 + Vector((0, 0, 0.26)) + fwd * (0.85 if sx > 0 else -0.85),
                         pos + side * 0.55 + Vector((0, 0, 0.26)) + fwd * (0.85 if sx > 0 else -0.85), 0.04, 8)
        # a few beams on the deck
        for k in range(3):
            add_box(deck, c + side * (-0.3 + k * 0.3) + Vector((0, 0, 0.3 + (k % 2) * 0.2)), (0.22, 2.4, 0.22),
                    rot @ Matrix.Rotation(self.rng.uniform(-0.04, 0.04), 3, 'Z'))
        finish_object('Flatbed_Frame', steel, self.mats['cart'], self.cols['entrance'], bevel=0.01)
        finish_object('Flatbed_Deck', deck, self.mats['wood'], self.cols['entrance'], bevel=0.012)
        finish_object('Flatbed_Wheels', wheels, self.mats['iron'], self.cols['entrance'], bevel=0.004)

    def build_quarry_props(self):
        E, into, along = entrance_frame()
        out = -into
        # flat-bed cart on the rails outside the portal
        self.build_flatbed(self.quarry_point(3.2, 0.0), out)

        # stacked pipes with straps (right of the portal)
        pipes = bmesh.new(); straps = bmesh.new()
        base = self.quarry_point(7.5, 7.5)
        pr = look_rot(Vector((out.x * 0.35 + along.x, out.y * 0.35 + along.y, 0)).normalized())
        for i, (ox, oz) in enumerate(((-0.5, 0.46), (0.5, 0.46), (0.0, 1.3))):
            c = base + pr @ Vector((ox, 0, oz))
            length = 5.8
            a = c - (pr @ Vector((0, 1, 0))) * length / 2
            b = c + (pr @ Vector((0, 1, 0))) * length / 2
            add_cylinder(pipes, a, b, 0.46, 28, cap=False)
            add_cylinder(pipes, a, b, 0.41, 28, cap=False)
            for end in (a, b):
                add_lathe(pipes, end, look_rot(b - a) @ Matrix.Rotation(math.radians(-90), 3, 'X'),
                          [(0.41, -0.01), (0.46, -0.01), (0.46, 0.01), (0.41, 0.01)], 28, (False, False))
        for k in (-1.6, 1.6):
            c = base + pr @ Vector((0, k, 0.9))
            add_lathe(straps, c, look_rot(pr @ Vector((0, 1, 0))) @ Matrix.Rotation(math.radians(-90), 3, 'X'),
                      [(1.05, -0.03), (1.08, -0.03), (1.08, 0.03), (1.05, 0.03)], 32, (False, False))
        finish_object('Quarry_Pipes', pipes, self.mats['pipe'], self.cols['entrance'])
        finish_object('Quarry_Pipe_Straps', straps, self.mats['iron'], self.cols['entrance'])

        # drums next to the pipes
        drums_blue = bmesh.new(); drums_black = bmesh.new()
        for i, (s, t) in enumerate(((5.2, 10.8), (5.9, 11.5), (4.6, 11.6), (9.6, 9.8))):
            p = self.quarry_point(s, t)
            self.steel_drum(drums_black if i % 2 else drums_blue, p, plastic=(i % 2 == 0))
        finish_object('Drums_Blue', drums_blue, self.mats['drum_blue'], self.cols['entrance'])
        finish_object('Drums_Black', drums_black, self.mats['drum_black'], self.cols['entrance'])

        # rusty tank lying on skids
        tank = bmesh.new()
        tp = self.quarry_point(8.5, 3.6)
        tr = look_rot(Vector((out.x * 0.8 + along.x * 0.6, out.y * 0.8 + along.y * 0.6, 0)).normalized())
        prof = [(0.0, -1.3), (0.35, -1.28), (0.55, -1.18), (0.62, -1.0), (0.62, 1.0), (0.55, 1.18), (0.35, 1.28), (0.0, 1.3)]
        prof = [(max(r, 0.02), z) for r, z in prof]
        add_lathe(tank, tp + Vector((0, 0, 0.75)), tr @ Matrix.Rotation(math.radians(90), 3, 'X'), prof, 28)
        for k in (-0.7, 0.7):
            add_box(tank, tp + (tr @ Vector((0, k, 0.08))), (1.3, 0.14, 0.16), tr)
        finish_object('Quarry_Tank', tank, self.mats['red_tank'], self.cols['entrance'], bevel=0.01)

        # row of site toilets (teal with white roofs)
        body = bmesh.new(); roof = bmesh.new()
        for i in range(3):
            p = self.quarry_point(12.0, -2.0 + i * 1.25)
            r = look_rot(along)
            add_box(body, p + Vector((0, 0, 1.12)), (1.12, 1.12, 2.24), r)
            add_box(body, p + (r @ Vector((0.0, -0.57, 1.1))), (0.86, 0.04, 1.95), r)   # door panel
            for k in range(4):
                add_box(body, p + (r @ Vector((0.0, -0.6, 1.75 + k * 0.08))), (0.5, 0.02, 0.025), r)  # vents
            add_lathe(roof, p + Vector((0, 0, 2.24)), r @ Matrix.Rotation(math.radians(45), 3, 'Z'),
                      [(0.8, 0.0), (0.8, 0.06), (0.64, 0.2), (0.3, 0.27), (0.02, 0.28)], 4)
            add_cylinder(roof, p + (r @ Vector((0.35, 0.35, 2.3))), p + (r @ Vector((0.35, 0.35, 2.75))), 0.05, 10)
        finish_object('Site_Toilets', body, self.mats['toilet'], self.cols['entrance'], bevel=0.03)
        finish_object('Site_Toilet_Roofs', roof, self.mats['toilet_roof'], self.cols['entrance'], bevel=0.01)

        # boulders around the portal
        rocks = bmesh.new()
        for s, t, size in ((1.6, -4.4, 1.2), (2.4, -3.2, 0.8), (1.2, 4.2, 1.0), (5.5, -7.0, 1.6), (4.0, 6.0, 0.7),
                           (14.0, 9.0, 1.3), (10.0, -9.5, 1.1), (3.0, -5.8, 0.5), (6.5, 1.8, 0.45)):
            p = self.quarry_point(s, t)
            self.rock_blob(rocks, p + Vector((0, 0, size * 0.3)), Vector((0, 0, 1)), size, 0.6, subdiv=2)
        finish_object('Quarry_Boulders', rocks, self.mats['stone'], self.cols['entrance'], smooth_angle=60)

    def steel_drum(self, bm, pos, plastic=False):
        if plastic:
            prof = [(0.02, 0.0), (0.27, 0.0), (0.29, 0.03), (0.3, 0.3), (0.29, 0.32), (0.3, 0.34), (0.3, 0.8),
                    (0.28, 0.86), (0.2, 0.88), (0.02, 0.88)]
        else:
            prof = [(0.02, 0.0), (0.285, 0.0), (0.3, 0.012), (0.29, 0.03), (0.29, 0.28), (0.302, 0.29), (0.302, 0.31),
                    (0.29, 0.32), (0.29, 0.56), (0.302, 0.57), (0.302, 0.59), (0.29, 0.6), (0.29, 0.85),
                    (0.3, 0.868), (0.285, 0.88), (0.02, 0.875)]
        add_lathe(bm, pos, Matrix.Rotation(self.rng.uniform(0, 6.28), 3, 'Z'), prof, 28, (False, False))

    # --- timber supports + lamps -----------------------------------------------
    def build_supports(self):
        bm = bmesh.new()
        lamp_index = 0
        for ei, (a, b) in enumerate(EDGES):
            if (a in CHAMBERS and b in CHAMBERS) or (a, b) in OUTSIDE_EDGES:
                continue
            A, fa, ra = node_center(a); B, fb, rb = node_center(b)
            seg = B - A
            flat = Vector((seg.x, seg.y, 0))
            if flat.length < 3:
                continue
            fwd = flat.normalized()
            side = Vector((-fwd.y, fwd.x, 0))
            length = seg.length
            start = (ra + 1.0) if a in CHAMBERS else (4.5 if a == 'portal' else 1.5)
            end = length - ((rb + 1.0) if b in CHAMBERS else 1.5)
            s = start
            sets = []
            while s < end:
                t = s / length
                axis = A + seg * t
                floor_z = fa + (fb - fa) * t
                base = Vector((axis.x, axis.y, floor_z + 1.0))
                fl = self.floor_at(base)
                if not fl:
                    s += 4.0
                    continue
                left_hit, _, ld = self.ray(base, side, 8)
                right_hit, _, rd = self.ray(base, -side, 8)
                if not left_hit or not right_hit or ld + rd < 2.2:
                    s += 4.0
                    continue
                pl = base + side * max(0.5, ld - 0.45)
                pr = base - side * max(0.5, rd - 0.45)
                top_l, _, tl = self.ray(pl, Vector((0, 0, 1)), 8)
                top_r, _, tr = self.ray(pr, Vector((0, 0, 1)), 8)
                zf = fl.z
                h = min(tl if top_l else 3.0, tr if top_r else 3.0) + (base.z - zf) - 0.45
                h = max(2.1, min(h, 3.3))
                pl.z = pr.z = zf
                rot = look_rot(fwd) @ Matrix.Rotation(self.rng.uniform(-0.03, 0.03), 3, 'Z')
                for p in (pl, pr):
                    add_box(bm, p + Vector((0, 0, h / 2 - 0.1)), (0.26, 0.26, h + 0.2), rot @ Matrix.Rotation(self.rng.uniform(-0.02, 0.02), 3, 'Y'))
                cap_c = (pl + pr) / 2 + Vector((0, 0, h + 0.16))
                add_cylinder(bm, cap_c - side * ((pl - pr).length / 2 + 0.3), cap_c + side * ((pl - pr).length / 2 + 0.3), 0.17, 12)
                for p, sgn in ((pl, -1), (pr, 1)):
                    b0 = p + Vector((0, 0, h - 0.75)) + side * (sgn * 0.08)
                    b1 = p + Vector((0, 0, h - 0.02)) + side * (sgn * 0.62)
                    add_box(bm, (b0 + b1) / 2, (0.12, 0.12, (b1 - b0).length), look_rot(b1 - b0) @ Matrix.Rotation(math.radians(90), 3, 'X'))
                    add_box(bm, p + Vector((0, 0, h + 0.03)), (0.3, 0.3, 0.08), rot)       # cap block
                sets.append((cap_c, side, (pl - pr).length))
                if lamp_index % 2 == 0:
                    self.lamps.append((cap_c - Vector((0, 0, 0.62)), ei, cap_c - Vector((0, 0, 0.17))))
                lamp_index += 1
                s += 3.6
            # lagging planks between consecutive sets
            for (c0, s0, w0), (c1, s1, w1) in zip(sets, sets[1:]):
                d = c1 - c0
                if d.length > 5.0:
                    continue
                for k in range(-3, 4):
                    off = s0 * (k * min(w0, w1) / 7.0)
                    a0 = c0 + off + Vector((0, 0, 0.21))
                    a1 = c1 + s1 * (k * min(w0, w1) / 7.0) + Vector((0, 0, 0.21))
                    add_box(bm, (a0 + a1) / 2, (0.2, (a1 - a0).length + 0.35, 0.05), look_rot(a1 - a0))
        finish_object('Timber_Sets', bm, self.mats['wood'], self.cols['timber'], bevel=0.015)

    def lamp_fixture(self, cages, glass, bulbs, pos):
        """Caged bulkhead work lamp"""
        add_cylinder(cages, pos + Vector((0, 0, 0.09)), pos + Vector((0, 0, 0.17)), 0.045, 12)
        add_lathe(glass, pos, None, [(0.02, -0.1), (0.05, -0.09), (0.065, -0.04), (0.06, 0.04), (0.045, 0.09)], 16, (True, False))
        for k in range(4):
            a = k * math.pi / 2 + math.pi / 4
            p0 = pos + Vector((math.cos(a) * 0.045, math.sin(a) * 0.045, 0.09))
            p1 = pos + Vector((math.cos(a) * 0.075, math.sin(a) * 0.075, -0.02))
            p2 = pos + Vector((0, 0, -0.12))
            add_cylinder(cages, p0, p1, 0.005, 5)
            add_cylinder(cages, p1, p2, 0.005, 5)
        for z in (-0.05, 0.03):
            add_lathe(cages, pos + Vector((0, 0, z)), None, [(0.07, -0.004), (0.078, -0.004), (0.078, 0.004), (0.07, 0.004)], 16, (False, False))
        bmesh.ops.create_uvsphere(bulbs, u_segments=12, v_segments=8, radius=0.035, matrix=Matrix.Translation(pos - Vector((0, 0, 0.02))))

    def add_point_light(self, name, pos, energy, color, radius=0.04, col='lights'):
        light = bpy.data.lights.new(name, 'POINT')
        light.energy = energy
        light.color = color
        light.shadow_soft_size = radius
        lo = bpy.data.objects.new(name, light)
        lo.location = pos
        self.cols[col].objects.link(lo)
        return lo

    def build_lamps(self):
        cages = bmesh.new(); glass = bmesh.new(); bulbs = bmesh.new()
        by_edge = {}
        for pos, ei, anchor in self.lamps:
            self.lamp_fixture(cages, glass, bulbs, pos)
            self.add_point_light('Work_Lamp', pos - Vector((0, 0, 0.03)), 120.0, (1.0, 0.66, 0.36))
            by_edge.setdefault(ei, []).append((pos, anchor))
        finish_object('Lamp_Cages', cages, self.mats['iron'], self.cols['lights'])
        finish_object('Lamp_Glass', glass, self.mats['glass'], self.cols['lights'])
        finish_object('Lamp_Bulbs', bulbs, self.mats['bulb'], self.cols['lights'])

        curve = bpy.data.curves.new('Lamp_Cables', 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = 0.011
        curve.bevel_resolution = 2
        for ei, items in by_edge.items():
            for (p0, a0), (p1, a1) in zip(items, items[1:]):
                sp = curve.splines.new('POLY')
                pts = []
                for i in range(17):
                    t = i / 16
                    q = a0.lerp(a1, t)
                    q.z -= math.sin(t * math.pi) * 0.35 + 0.04
                    pts.append(q)
                sp.points.add(len(pts) - 1)
                for i, q in enumerate(pts):
                    sp.points[i].co = (q.x, q.y, q.z, 1)
            for p, a in items:
                sp = curve.splines.new('POLY')
                sp.points.add(1)
                sp.points[0].co = (a.x, a.y, a.z - 0.04, 1)
                sp.points[1].co = (p.x, p.y, p.z + 0.17, 1)
        obj = bpy.data.objects.new('Lamp_Cables', curve)
        curve.materials.append(self.mats['cable'])
        self.cols['lights'].objects.link(obj)

    def build_floodlights(self):
        spots = [('main', Vector((3.0, -2.0, 0))), ('main', Vector((-5.0, 4.0, 0))), ('main_w', Vector((0, -2, 0))),
                 ('shop', Vector((-4.0, 3.0, 0))), ('south1', Vector((0, 0, 0))), ('west2', Vector((0, 0, 0))),
                 ('ledge', Vector((0, 0, 0)))]
        steel = bmesh.new(); lens = bmesh.new()
        for name, off in spots:
            c, f, r = node_center(name)
            fl = self.floor_at(Vector((c.x + off.x, c.y + off.y, f + 1.0)))
            if not fl:
                continue
            h = 3.2
            for k in range(3):
                ang = k * 2 * math.pi / 3
                foot = fl + Vector((math.cos(ang) * 0.65, math.sin(ang) * 0.65, 0))
                add_cylinder(steel, foot, fl + Vector((0, 0, 1.25)), 0.022, 8)
                add_box(steel, foot + Vector((0, 0, 0.01)), (0.08, 0.08, 0.02))
            add_cylinder(steel, fl + Vector((0, 0, 1.0)), fl + Vector((0, 0, h)), 0.032, 10)
            add_cylinder(steel, fl + Vector((0, 0, 0.3)), fl + Vector((0, 0, 1.3)), 0.045, 10)
            target = Vector((c.x, c.y, f + 0.5))
            d = (target - (fl + Vector((0, 0, h)))).normalized()
            for sgn in (-1, 1):
                head = fl + Vector((0, 0, h)) + Vector((-d.y, d.x, 0)).normalized() * 0.33 * sgn
                rot = look_rot(d)
                add_box(steel, head, (0.42, 0.16, 0.32), rot)
                for k in range(5):
                    add_box(steel, head - d * 0.1 + (rot @ Vector((-0.16 + k * 0.08, 0, 0))), (0.012, 0.08, 0.28), rot)
                add_box(lens, head + d * 0.085, (0.36, 0.012, 0.26), rot)
                light = bpy.data.lights.new('Flood', 'SPOT')
                light.energy = 1800.0
                light.spot_size = math.radians(80)
                light.spot_blend = 0.7
                light.color = (1.0, 0.9, 0.78)
                light.shadow_soft_size = 0.12
                lo = bpy.data.objects.new('Flood', light)
                lo.location = head + d * 0.14
                lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
                self.cols['lights'].objects.link(lo)
        finish_object('Flood_Towers', steel, self.mats['yellow'], self.cols['lights'], bevel=0.006)
        finish_object('Flood_Lenses', lens, self.mats['flood'], self.cols['lights'])

    # --- rails + carts -------------------------------------------------------------
    def rail_path(self, names):
        pts = []
        for n in names:
            c, f, r = node_center(n)
            pts.append(Vector((c.x, c.y, f)))
        out = []
        ext = [pts[0]] + pts + [pts[-1]]
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            steps = max(2, int((p2 - p1).length / 0.3))
            for s in range(steps):
                t = s / steps
                t2, t3 = t * t, t * t * t
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        out.append(pts[-1])
        zs = []
        for q in out:
            hit = self.floor_at(Vector((q.x, q.y, q.z + 1.2)))
            zs.append(hit.z if hit else q.z)
        zs = np.convolve(np.pad(zs, 8, mode='edge'), np.ones(17) / 17, mode='valid')
        return [Vector((q.x, q.y, z + 0.02)) for q, z in zip(out, zs)]

    def build_rails(self):
        rails = bmesh.new(); sleepers = bmesh.new(); spikes = bmesh.new()
        profile = [(-0.05, 0.0), (0.05, 0.0), (0.05, 0.012), (0.008, 0.02), (0.008, 0.085), (0.028, 0.09),
                   (0.028, 0.125), (-0.028, 0.125), (-0.028, 0.09), (-0.008, 0.085), (-0.008, 0.02), (-0.05, 0.012)]
        carts_at = []
        self.rail_paths = []
        for ri, route in enumerate(RAIL_ROUTES):
            path = self.rail_path(route)
            self.rail_paths.append(path)
            fr = frames_along(path)
            for off in (-0.45, 0.45):
                rp = [p + side * off + Vector((0, 0, 0.1)) for p, t, side, u in fr]
                add_sweep(rails, rp, [(x, y) for x, y in reversed(profile)], True)
            since = 0.0
            for i in range(1, len(path)):
                since += (path[i] - path[i - 1]).length
                if since < 0.62:
                    continue
                since = 0.0
                p, t, side, u = fr[i]
                rot = look_rot(Vector((t.x, t.y, 0))) @ Matrix.Rotation(self.rng.uniform(-0.05, 0.05), 3, 'Z')
                add_box(sleepers, p + Vector((0, 0, 0.03)), (1.4, 0.2, 0.13), rot)
                for off in (-0.45, 0.45):
                    add_box(spikes, p + side * off + Vector((0, 0, 0.1)), (0.22, 0.15, 0.012), rot)
            for frac in ((0.32, 0.66) if ri == 0 else (0.45,)):
                k = int(len(path) * frac)
                carts_at.append((path[k], path[k + 1] - path[k - 1]))
        finish_object('Rails', rails, self.mats['rail'], self.cols['rails'])
        finish_object('Rail_Sleepers', sleepers, self.mats['wood'], self.cols['rails'], bevel=0.012)
        finish_object('Rail_Tie_Plates', spikes, self.mats['iron'], self.cols['rails'])

        body = bmesh.new(); wheels = bmesh.new(); load = bmesh.new()
        for pos, tangent in carts_at:
            self.ore_cart(body, wheels, load, pos, Vector((tangent.x, tangent.y, 0)).normalized())
        finish_object('Mine_Carts', body, self.mats['cart'], self.cols['rails'], bevel=0.008)
        finish_object('Mine_Cart_Wheels', wheels, self.mats['iron'], self.cols['rails'])
        finish_object('Mine_Cart_Ore', load, self.mats['ore_copper'], self.cols['rails'], smooth_angle=60)

    def ore_cart(self, body, wheels, load, pos, fwd):
        """V-tub ore cart on a steel frame with flanged wheels"""
        rot = look_rot(fwd)
        side = Vector((-fwd.y, fwd.x, 0))
        base = pos + Vector((0, 0, 0.42))
        # tub as a flared lathe-free shell: bottom + 4 tilted plates + rolled rim
        add_box(body, base + Vector((0, 0, 0.05)), (0.62, 1.2, 0.05), rot)
        for sgn in (-1, 1):
            add_box(body, base + side * (0.4 * sgn) + Vector((0, 0, 0.36)), (0.035, 1.3, 0.66),
                    rot @ Matrix.Rotation(math.radians(-17 * sgn), 3, 'Y'))
            add_box(body, base + fwd * (0.66 * sgn) + Vector((0, 0, 0.36)), (0.8, 0.035, 0.66),
                    rot @ Matrix.Rotation(math.radians(12 * sgn), 3, 'X'))
        rim = []
        for x, y in ((-0.52, -0.73), (0.52, -0.73), (0.52, 0.73), (-0.52, 0.73), (-0.52, -0.73)):
            rim.append(base + rot @ Vector((x, y, 0.7)))
        for a, b in zip(rim, rim[1:]):
            add_cylinder(body, a, b, 0.022, 8)
        for k in (-0.45, 0.0, 0.45):
            for sgn in (-1, 1):
                add_box(body, base + fwd * k + side * (0.46 * sgn) + Vector((0, 0, 0.4)), (0.02, 0.06, 0.62),
                        rot @ Matrix.Rotation(math.radians(-17 * sgn), 3, 'Y'))
        for sgn in (-1, 1):
            add_box(body, pos + side * (0.3 * sgn) + Vector((0, 0, 0.36)), (0.08, 1.3, 0.1), rot)
            add_cylinder(body, pos + fwd * (0.75 * sgn) + Vector((0, 0, 0.36)), pos + fwd * (0.95 * sgn) + Vector((0, 0, 0.36)), 0.03, 8)
        for sx in (-0.45, 0.45):
            for sy in (-0.42, 0.42):
                wc = pos + side * sx + fwd * sy + Vector((0, 0, 0.19))
                add_lathe(wheels, wc, look_rot(side) @ Matrix.Rotation(math.radians(90), 3, 'X'),
                          [(0.03, -0.04), (0.16, -0.04), (0.16, 0.02), (0.19, 0.03), (0.19, 0.05), (0.03, 0.05)], 16)
        for k in range(14):
            off = side * self.rng.uniform(-0.28, 0.28) + fwd * self.rng.uniform(-0.5, 0.5)
            self.rock_blob(load, base + off + Vector((0, 0, 0.62 + self.rng.uniform(0, 0.12))), Vector((0, 0, 1)),
                           self.rng.uniform(0.1, 0.2), 0.7)

    # --- ores + crystals -----------------------------------------------------------
    def rock_blob(self, bm, center, normal, size, squash=0.6, subdiv=1):
        rot = normal.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        m = Matrix.Translation(center) @ rot @ Matrix.Diagonal((size, size * self.rng.uniform(0.7, 1.1), size * squash, 1))
        res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0, matrix=m)
        for v in res['verts']:
            v.co += (v.co - center).normalized() * self.rng.uniform(-0.28, 0.12) * size
        uvl, pl = _layers(bm)
        pv = self.rng.random()
        for f in _faces_of(res['verts']):
            f[pl] = pv
            for l in f.loops:
                l[uvl].uv = (l.vert.co.x + l.vert.co.z, l.vert.co.y)

    def crystal_cluster(self, bm, center, normal, count, scale):
        base_rot = normal.to_track_quat('Z', 'Y').to_matrix()
        for _ in range(count):
            tilt = Matrix.Rotation(self.rng.uniform(-0.6, 0.6), 3, 'X') @ Matrix.Rotation(self.rng.uniform(-0.6, 0.6), 3, 'Y')
            rot = (base_rot @ tilt).to_4x4()
            length = self.rng.uniform(0.3, 0.9) * scale
            radius = self.rng.uniform(0.09, 0.2) * scale
            offset = base_rot @ Vector((self.rng.uniform(-0.25, 0.25) * scale, self.rng.uniform(-0.25, 0.25) * scale, 0))
            m = Matrix.Translation(center + offset) @ rot
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=radius, radius2=radius * 0.85,
                                  depth=length, matrix=m @ Matrix.Translation((0, 0, length / 2)))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=radius * 0.85, radius2=0.0,
                                  depth=radius * 2.2, matrix=m @ Matrix.Translation((0, 0, length + radius * 1.1)))

    def add_glow(self, pos, kind, energy):
        colors = {'ruby': (1, 0.1, 0.1), 'emerald': (0.1, 1, 0.3), 'sapphire': (0.2, 0.4, 1), 'diamond': (0.8, 0.9, 1)}
        self.add_point_light('Crystal_Glow', pos, energy, colors[kind], 0.3, 'crystals')

    def build_ores(self):
        order = ['coal', 'copper', 'iron', 'coal', 'tin', 'copper', 'lead', 'iron', 'bauxite', 'gold']
        crystal_spots = {21: 'ruby', 22: 'emerald', 23: 'sapphire', 24: 'diamond', 25: 'ruby', 9: 'sapphire', 26: 'emerald'}
        per_type, crystals = {}, {}
        placed = 0
        for i, (x, y, z) in enumerate(ORE_SPOTS):
            p = local(x, y, z)
            d, q, _, dirv = nearest_edge_point(p)
            out = Vector((p.x - q.x, p.y - q.y, 0))
            if out.length < 0.6:
                out = Vector((-dirv.y, dirv.x, 0)) * (1 if i % 2 == 0 else -1)
            out.normalize()
            origin = Vector((p.x, p.y, p.z - 0.2))
            hit = n = None
            for direction in (out, out + Vector((0, 0, -0.3)), -out, Vector((0, 0, -1))):
                hit, n, dist = self.ray(origin, direction, 12)
                if hit:
                    break
            if not hit:
                continue
            placed += 1
            if i in crystal_spots:
                kind = crystal_spots[i]
                bm = crystals.setdefault(kind, bmesh.new())
                self.crystal_cluster(bm, hit - n * 0.1, n, self.rng.randint(6, 10), 1.0)
                self.add_glow(hit + n * 0.5, kind, 40)
            else:
                kind = order[i % len(order)]
                bm = per_type.setdefault(kind, bmesh.new())
                for k in range(self.rng.randint(5, 8)):
                    off = Vector((self.rng.uniform(-0.6, 0.6), self.rng.uniform(-0.6, 0.6), self.rng.uniform(-0.45, 0.45)))
                    off -= n * off.dot(n)
                    self.rock_blob(bm, hit + off - n * 0.05, n, self.rng.uniform(0.28, 0.55), 0.55, subdiv=2)
        for kind, bm in per_type.items():
            finish_object('Ore_' + kind, bm, self.mats['ore_' + kind], self.cols['ores'], smooth_angle=50)
        self.crystal_bms = crystals
        print(f'[cave] {placed}/{len(ORE_SPOTS)} ore veins placed on the walls')

    def build_crystal_chamber(self):
        c, f, r = node_center('crystal')
        kinds = ['ruby', 'emerald', 'sapphire', 'sapphire', 'emerald', 'ruby', 'diamond']
        for i in range(34):
            ang = self.rng.uniform(0, 2 * math.pi)
            el = self.rng.uniform(-0.35, 0.9)
            d = Vector((math.cos(ang) * math.cos(el), math.sin(ang) * math.cos(el), math.sin(el)))
            hit, n, dist = self.ray(c, d, 20)
            if not hit:
                continue
            kind = kinds[i % len(kinds)]
            bm = self.crystal_bms.setdefault(kind, bmesh.new())
            self.crystal_cluster(bm, hit - n * 0.1, n, self.rng.randint(5, 12), self.rng.uniform(0.8, 1.9))
            if i % 3 == 0:
                self.add_glow(hit + n * 0.8, kind, 130)
        for kind, bm in self.crystal_bms.items():
            finish_object('Crystals_' + kind, bm, self.mats['crystal_' + kind], self.cols['crystals'], smooth_angle=20)
        self.crystal_bms = {}

    # --- scatter: pebbles, scree, quarry gravel ----------------------------------
    def make_instances(self, prefix, count, squash=(0.4, 0.8)):
        objs = []
        for k in range(count):
            bm = bmesh.new()
            self.rock_blob(bm, Vector(), Vector((0, 0, 1)), 1.0, self.rng.uniform(*squash), subdiv=2)
            obj = finish_object(f'{prefix}_{k}', bm, self.mats['stone'], self.cols['instances'], smooth_angle=45)
            objs.append(obj)
        return objs

    def particles(self, name, group, count, size, size_random, instances):
        mod = self.shell.modifiers.new(name, 'PARTICLE_SYSTEM')
        psys = mod.particle_system
        ps = psys.settings
        ps.name = name
        ps.type = 'EMITTER'
        ps.count = count
        ps.frame_start = 1
        ps.frame_end = 1
        ps.lifetime = 100000
        ps.emit_from = 'FACE'
        ps.distribution = 'RAND'
        ps.use_emit_random = True
        ps.physics_type = 'NO'
        ps.render_type = 'COLLECTION'
        ps.instance_collection = instances
        ps.use_collection_pick_random = True
        ps.particle_size = size
        ps.size_random = size_random
        ps.use_rotations = True
        ps.rotation_mode = 'NOR'
        ps.rotation_factor_random = 0.25
        ps.phase_factor_random = 2.0
        ps.display_percentage = 2
        psys.vertex_group_density = group
        psys.seed = sum(map(ord, name)) % 997

    def build_scatter(self):
        pebbles = collection('Pebbles', self.cols['instances'], link=True)
        for o in self.make_instances('Pebble', 8, (0.35, 0.7)):
            self.cols['instances'].objects.unlink(o)
            pebbles.objects.link(o)
        stones = collection('Scree', self.cols['instances'], link=True)
        for o in self.make_instances('Scree', 6, (0.5, 0.9)):
            self.cols['instances'].objects.unlink(o)
            stones.objects.link(o)
        scale = 0.25 if self.fast else 1.0
        self.particles('Sand_Pebbles', 'sand', int(260000 * scale), 0.016, 0.85, pebbles)
        self.particles('Sand_Gravel', 'sand', int(26000 * scale), 0.05, 0.7, stones)
        self.particles('Wall_Scree', 'scree', int(24000 * scale), 0.1, 0.75, stones)
        self.particles('Quarry_Gravel', 'quarry_floor', int(60000 * scale), 0.04, 0.8, stones)
        self.particles('Quarry_Rocks', 'quarry_floor', int(1500 * scale), 0.25, 0.7, stones)

    # --- footprints in the sand ------------------------------------------------------
    def build_footprints(self):
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.verify()
        count = 0

        def stamp(p, n, fwd, left):
            nonlocal count
            fwd = (fwd - n * fwd.dot(n)).normalized()
            side = n.cross(fwd).normalized()
            c = p + n * 0.006 + side * (0.1 if left else -0.1)
            yaw = Matrix.Rotation(self.rng.uniform(-0.12, 0.12) + (0.08 if left else -0.08), 3, n)
            fw = yaw @ fwd
            sd = yaw @ side
            L, W = 0.31, 0.12
            corners = [c - fw * L / 2 - sd * W / 2, c - fw * L / 2 + sd * W / 2, c + fw * L / 2 + sd * W / 2, c + fw * L / 2 - sd * W / 2]
            vs = [bm.verts.new(q) for q in corners]
            f = bm.faces.new(vs)
            for l, uv in zip(f.loops, ((1, 0), (0, 0), (0, 1), (1, 1)) if left else ((0, 0), (1, 0), (1, 1), (0, 1))):
                l[uvl].uv = uv
            count += 1

        def trail(path, offset, stride=0.74, jitter=0.12):
            fr = frames_along(path)
            dist, left = 0.0, True
            for i in range(1, len(fr)):
                dist += (fr[i][0] - fr[i - 1][0]).length
                if dist < stride:
                    continue
                dist = 0.0
                p, t, side, u = fr[i]
                q = p + side * (offset + self.rng.uniform(-jitter, jitter))
                hit, n = self.floor_n(Vector((q.x, q.y, q.z + 1.0)))
                if not hit or n.z < 0.8:
                    continue
                stamp(hit, n, Vector((t.x, t.y, 0)), left)
                left = not left

        for path in getattr(self, 'rail_paths', []):
            trail(path, 1.05)
            trail(list(reversed(path)), -0.95)
        # footprints around the workshop stations
        c, f, r = node_center('shop')
        for k in range(10):
            a0 = self.rng.uniform(0, 6.28)
            pts = [Vector((c.x + math.cos(a0 + t * 0.35) * (r * 0.5 - t * 0.2), c.y + math.sin(a0 + t * 0.35) * (r * 0.5 - t * 0.2), f)) for t in range(12)]
            trail(pts, 0.0, 0.7, 0.05)
        me_obj = finish_object('Sand_Footprints', bm, self.mats['footprint'], self.cols['decals'])
        me_obj.visible_shadow = False
        print(f'[cave] {count} footprints')

    # --- workshop ------------------------------------------------------------------
    def ground(self, x, y):
        p = local(x, y, NODES['shop'][2] + 1.2)
        hit = self.floor_at(p, up=1.0)
        return hit if hit else Vector((p.x, p.y, local(0, 0, NODES['shop'][2]).z))

    def crate(self, bm, pos, size, yaw):
        rot = Matrix.Rotation(yaw, 3, 'Z')
        c = pos + Vector((0, 0, size / 2))
        planks = 3
        pw = size / planks
        for k in range(planks):
            for axis, sgn in ((0, -1), (0, 1), (1, -1), (1, 1)):
                off = Vector((0, 0, 0))
                off[axis] = sgn * (size / 2 - 0.01)
                along = 1 - axis
                off[along] = -size / 2 + pw * (k + 0.5)
                sz = [0, 0, 0]
                sz[axis] = 0.02
                sz[along] = pw - 0.012
                sz[2] = size - 0.04
                add_box(bm, c + rot @ off, tuple(sz), rot)
            add_box(bm, c + rot @ Vector((-size / 2 + pw * (k + 0.5), 0, size / 2 - 0.01)), (pw - 0.012, size - 0.02, 0.02), rot)
            add_box(bm, c + rot @ Vector((-size / 2 + pw * (k + 0.5), 0, -size / 2 + 0.01)), (pw - 0.012, size - 0.02, 0.02), rot)
        for x in (-1, 1):
            for y in (-1, 1):
                add_box(bm, c + rot @ Vector((x * (size / 2 + 0.005), y * (size / 2 + 0.005), 0)), (0.05, 0.05, size), rot)

    def build_workshop(self):
        wood = bmesh.new(); iron = bmesh.new(); green = bmesh.new(); brick = bmesh.new(); glow = bmesh.new()
        crates = bmesh.new(); gold = bmesh.new(); drums = bmesh.new(); coal = bmesh.new(); stones = bmesh.new()
        cages = bmesh.new(); glass = bmesh.new(); bulbs = bmesh.new()

        # plank deck under the stations (on joists)
        deck_c = self.ground(2915.5, 2650.5)
        rot = Matrix.Rotation(math.radians(230), 3, 'Z')
        for i in range(-14, 15):
            off = rot @ Vector((i * 0.26, 0, 0))
            add_box(wood, deck_c + off + Vector((0, 0, 0.13)), (0.245, 7.5 + self.rng.uniform(-0.3, 0.3), 0.045),
                    rot @ Matrix.Rotation(self.rng.uniform(-0.006, 0.006), 3, 'Z'))
        for j in (-3.2, -1.1, 1.1, 3.2):
            add_box(wood, deck_c + rot @ Vector((0, j, 0)) + Vector((0, 0, 0.06)), (7.6, 0.14, 0.12), rot)

        # smelter: brick furnace with arched opening, iron door, bands, chimney
        s = self.ground(SMELTER[0], SMELTER[1])
        face = (self.ground(2917.5, 2650.5) - s)
        face.z = 0
        face.normalize()
        fr = look_rot(face)
        side = Vector((-face.y, face.x, 0))
        for sgn in (-1, 1):
            add_box(brick, s + side * (0.62 * sgn) + Vector((0, 0, 0.75)), (0.56, 1.8, 1.5), fr)
        add_box(brick, s - face * 0.62 + Vector((0, 0, 0.75)), (0.7, 0.56, 1.5), fr)
        add_box(brick, s + Vector((0, 0, 1.25)), (0.7, 1.8, 0.5), fr)
        add_box(brick, s + Vector((0, 0, 0.18)), (0.7, 1.8, 0.36), fr)
        add_box(brick, s + Vector((0, 0, 1.72)), (1.3, 1.3, 0.45), fr)
        add_box(glow, s + face * 0.1 + Vector((0, 0, 0.72)), (0.66, 1.2, 0.7), fr)
        top, _, _ = self.ray(s + Vector((0, 0, 2.0)), Vector((0, 0, 1)), 15)
        chimney_top = top if top else s + Vector((0, 0, 6))
        add_cylinder(iron, s + Vector((0, 0, 1.9)), chimney_top + Vector((0, 0, 0.3)), 0.26, 20)
        for k in range(int((chimney_top.z - s.z - 2) / 1.2)):
            add_cylinder(iron, s + Vector((0, 0, 2.3 + k * 1.2)), s + Vector((0, 0, 2.36 + k * 1.2)), 0.29, 20)
        for z in (0.35, 1.05, 1.5):
            add_box(iron, s + Vector((0, 0, z)), (1.84, 1.84, 0.06), fr)
        # door hanging open
        hinge = s + face * 0.92 + side * 0.36 + Vector((0, 0, 0.72))
        add_box(iron, hinge + (fr @ Matrix.Rotation(math.radians(-60), 3, 'Z') @ Vector((0.34, 0, 0))), (0.68, 0.04, 0.6),
                fr @ Matrix.Rotation(math.radians(-60), 3, 'Z'))
        self.add_point_light('Smelter_Fire', s + face * 1.1 + Vector((0, 0, 0.75)), 380.0, (1.0, 0.36, 0.07), 0.35, 'workshop')
        self.add_point_light('Smelter_Inside', s + Vector((0, 0, 0.75)), 250.0, (1.0, 0.3, 0.05), 0.3, 'workshop')
        # coal heap + crucible + moulds + tools
        for k in range(40):
            p = s + face * 1.3 - side * 1.3 + Vector((self.rng.gauss(0, 0.25), self.rng.gauss(0, 0.25), 0))
            fl = self.floor_at(p + Vector((0, 0, 1))) or p
            self.rock_blob(coal, fl + Vector((0, 0, 0.05 + max(0, 0.3 - (p - (s + face * 1.3 - side * 1.3)).length) * 0.6)),
                           Vector((0, 0, 1)), self.rng.uniform(0.05, 0.11), 0.7)
        add_box(wood, s + face * 1.35 + side * 1.6 + Vector((0, 0, 0.42)), (1.2, 0.7, 0.05), fr)
        for sx in (-0.5, 0.5):
            for sy in (-0.28, 0.28):
                add_box(wood, s + face * 1.35 + side * 1.6 + (fr @ Vector((sx, sy, 0))) + Vector((0, 0, 0.2)), (0.06, 0.06, 0.4), fr)
        for k in range(4):
            add_box(gold, s + face * 1.35 + side * (1.25 + k * 0.22) + Vector((0, 0, 0.48)), (0.16, 0.3, 0.06), fr)
        add_lathe(iron, s + face * 1.2 + side * 0.9, None, [(0.05, 0.0), (0.12, 0.02), (0.15, 0.2), (0.14, 0.22), (0.02, 0.22)], 16, (True, False))

        # stone cracking benches: industrial drill presses
        for x, y, hdg in CRACK_BENCHES:
            g = self.ground(x, y)
            r = Matrix.Rotation(math.radians(hdg), 3, 'Z')
            fwd = r @ Vector((0, 1, 0))
            c = g + fwd * 0.65
            add_box(green, c + Vector((0, 0, 0.04)), (0.7, 0.55, 0.08), r)
            add_cylinder(iron, c - fwd * 0.12 + Vector((0, 0, 0.08)), c - fwd * 0.12 + Vector((0, 0, 1.75)), 0.055, 16)
            add_lathe(green, c + fwd * 0.08 + Vector((0, 0, 0.78)), None, [(0.02, 0.0), (0.2, 0.0), (0.21, 0.02), (0.21, 0.05), (0.02, 0.05)], 20)
            add_box(green, c + fwd * 0.02 + Vector((0, 0, 1.55)), (0.34, 0.5, 0.34), r)
            add_cylinder(green, c - fwd * 0.3 + Vector((0, 0, 1.62)), c - fwd * 0.3 + Vector((0, 0, 1.95)), 0.13, 16)
            add_cylinder(iron, c + fwd * 0.12 + Vector((0, 0, 1.38)), c + fwd * 0.12 + Vector((0, 0, 1.1)), 0.035, 12)
            add_cylinder(iron, c + fwd * 0.12 + Vector((0, 0, 1.1)), c + fwd * 0.12 + Vector((0, 0, 0.92)), 0.008, 8, radius2=0.002)
            hub = c + fwd * 0.02 + Vector((0, 0, 1.5)) + (r @ Vector((0.19, 0, 0)))
            for k in range(3):
                a = k * 2 * math.pi / 3
                tip = hub + (r @ Vector((0.03, math.cos(a) * 0.28, math.sin(a) * 0.28)))
                add_cylinder(iron, hub, tip, 0.01, 6)
                bmesh.ops.create_uvsphere(iron, u_segments=10, v_segments=6, radius=0.025, matrix=Matrix.Translation(tip))
            self.rock_blob(stones, c + fwd * 0.08 + Vector((0, 0, 0.92)), Vector((0, 0, 1)), 0.12, 0.7)

        # jewel benches
        for x, y, hdg in JEWEL_BENCHES:
            g = self.ground(x, y)
            r = Matrix.Rotation(math.radians(hdg), 3, 'Z')
            fwd = r @ Vector((0, 1, 0))
            c = g + fwd * 0.65
            for k in range(4):
                add_box(wood, c + (r @ Vector((0, -0.27 + k * 0.18, 0))) + Vector((0, 0, 0.9)), (1.5, 0.175, 0.06), r)
            for sx in (-0.66, 0.66):
                for sy in (-0.28, 0.28):
                    add_box(wood, c + (r @ Vector((sx, sy, 0))) + Vector((0, 0, 0.435)), (0.08, 0.08, 0.87), r)
            add_box(wood, c + Vector((0, 0, 0.2)), (1.35, 0.55, 0.03), r)
            add_box(iron, c + (r @ Vector((-0.5, 0.18, 0))) + Vector((0, 0, 0.99)), (0.18, 0.14, 0.12), r)
            add_cylinder(green, c + (r @ Vector((0.4, 0.1, 0))) + Vector((0, 0, 0.93)), c + (r @ Vector((0.4, 0.1, 0))) + Vector((0, 0, 1.05)), 0.07, 16)
            add_lathe(stones, c + (r @ Vector((0.4, -0.12, 0))) + Vector((0, 0, 1.1)), r @ Matrix.Rotation(math.radians(90), 3, 'Y'),
                      [(0.02, -0.02), (0.1, -0.02), (0.1, 0.02), (0.02, 0.02)], 20)
            arm0 = c + (r @ Vector((0.62, 0.22, 0))) + Vector((0, 0, 0.93))
            arm1 = arm0 + Vector((0, 0, 0.55))
            arm2 = c + (r @ Vector((0.15, 0.05, 0))) + Vector((0, 0, 1.35))
            add_cylinder(iron, arm0, arm1, 0.012, 8)
            add_cylinder(iron, arm1, arm2, 0.012, 8)
            self.lamp_fixture(cages, glass, bulbs, arm2 - Vector((0, 0, 0.05)))
            self.add_point_light('Bench_Lamp', arm2 - Vector((0, 0, 0.1)), 35.0, (1.0, 0.85, 0.65), 0.03, 'workshop')
            for kind in ('ruby', 'emerald', 'sapphire'):
                bmg = self.crystal_bms.setdefault(kind, bmesh.new())
                self.crystal_cluster(bmg, c + (r @ Vector((self.rng.uniform(-0.4, 0.1), self.rng.uniform(-0.15, 0.15), 0))) + Vector((0, 0, 0.935)), Vector((0, 0, 1)), 1, 0.22)

        # shop counter + shelves + tools
        g = self.ground(SHOP_PED[0], SHOP_PED[1])
        r = Matrix.Rotation(math.radians(SHOP_PED[2]), 3, 'Z')
        fwd = r @ Vector((0, 1, 0))
        for k in range(5):
            add_box(wood, g + fwd * 0.9 + (r @ Vector((0, 0, 0))) + Vector((0, 0, 0.12 + k * 0.2)), (2.6, 0.62, 0.19), r)
        add_box(wood, g + fwd * 0.9 + Vector((0, 0, 1.05)), (2.8, 0.75, 0.06), r)
        for k in range(4):
            add_box(wood, g - fwd * 0.85 + Vector((0, 0, 0.35 + k * 0.55)), (2.4, 0.45, 0.04), r)
        for sx in (-1.18, 1.18):
            add_box(wood, g - fwd * 0.85 + (r @ Vector((sx, 0, 0))) + Vector((0, 0, 1.1)), (0.07, 0.45, 2.2), r)
        for k in range(6):
            self.crate(crates, g - fwd * 0.85 + (r @ Vector((-0.85 + (k % 3) * 0.85, 0, 0))) + Vector((0, 0, 0.37 + (k // 3) * 0.55)), 0.4, math.radians(SHOP_PED[2]) + self.rng.uniform(-0.1, 0.1))
        for k in range(3):
            base = g + fwd * 0.9 + (r @ Vector((-0.8 + k * 0.6, 0, 0))) + Vector((0, 0, 1.09))
            self.pickaxe(wood, iron, base, r @ Matrix.Rotation(math.radians(90), 3, 'Y') @ Matrix.Rotation(self.rng.uniform(-0.3, 0.3), 3, 'X'))
        for k in range(4):
            self.pickaxe(wood, iron, g - fwd * 1.2 + (r @ Vector((1.6 + k * 0.18, 0, 0.0))) + Vector((0, 0, 0.45)),
                         r @ Matrix.Rotation(math.radians(-12), 3, 'X'))

        # buyer table with scale + gold bars
        g = self.ground(BUYER_PED[0], BUYER_PED[1])
        r = Matrix.Rotation(math.radians(BUYER_PED[2]), 3, 'Z')
        fwd = r @ Vector((0, 1, 0))
        t = g + fwd * 0.85
        for k in range(4):
            add_box(wood, t + (r @ Vector((0, -0.3 + k * 0.2, 0))) + Vector((0, 0, 0.88)), (1.6, 0.19, 0.06), r)
        for sx in (-0.7, 0.7):
            for sy in (-0.33, 0.33):
                add_box(wood, t + (r @ Vector((sx, sy, 0))) + Vector((0, 0, 0.44)), (0.08, 0.08, 0.88), r)
        add_box(iron, t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 0.95)), (0.34, 0.26, 0.08), r)
        add_cylinder(iron, t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 0.99)), t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 1.28)), 0.015, 8)
        add_lathe(iron, t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 1.28)), None, [(0.02, 0.0), (0.14, 0.02), (0.15, 0.04)], 20, (True, False))
        for k in range(9):
            add_box(gold, t + (r @ Vector((0.2 + (k % 3) * 0.16, -0.15 + (k // 3 % 2) * 0.16, 0))) + Vector((0, 0, 0.945 + (k // 6) * 0.06)), (0.14, 0.07, 0.055), r)

        # crates + drums around the chamber walls
        c, f, rad = node_center('shop')
        for k in range(24):
            ang = self.rng.uniform(0, 2 * math.pi)
            dirv = Vector((math.cos(ang), math.sin(ang), 0))
            hit, n, dist = self.ray(Vector((c.x, c.y, f + 0.8)), dirv, 20)
            if not hit:
                continue
            pos = hit - dirv * self.rng.uniform(0.6, 1.0)
            flo = self.floor_at(pos)
            if not flo:
                continue
            if k % 3 == 0:
                self.steel_drum(drums, flo)
            else:
                size = self.rng.uniform(0.5, 0.75)
                self.crate(crates, flo, size, ang)
                if self.rng.random() < 0.4:
                    self.crate(crates, flo + Vector((0, 0, size)), 0.45, ang + 0.3)

        finish_object('Workshop_Wood', wood, self.mats['wood'], self.cols['workshop'], bevel=0.008)
        finish_object('Workshop_Iron', iron, self.mats['iron'], self.cols['workshop'], bevel=0.004)
        finish_object('Workshop_Machines', green, self.mats['green'], self.cols['workshop'], bevel=0.01)
        finish_object('Smelter_Brick', brick, self.mats['brick'], self.cols['workshop'], bevel=0.015)
        finish_object('Smelter_Glow', glow, self.mats['molten'], self.cols['workshop'])
        finish_object('Crates', crates, self.mats['wood_new'], self.cols['workshop'], bevel=0.004)
        finish_object('Gold_Bars', gold, self.mats['gold'], self.cols['workshop'], bevel=0.004)
        finish_object('Workshop_Drums', drums, self.mats['drum_black'], self.cols['workshop'])
        finish_object('Coal_Heap', coal, self.mats['coal'], self.cols['workshop'], smooth_angle=30)
        finish_object('Workshop_Stones', stones, self.mats['stone'], self.cols['workshop'])
        finish_object('Bench_Lamp_Cages', cages, self.mats['iron'], self.cols['workshop'])
        finish_object('Bench_Lamp_Glass', glass, self.mats['glass'], self.cols['workshop'])
        finish_object('Bench_Lamp_Bulbs', bulbs, self.mats['bulb'], self.cols['workshop'])

    def pickaxe(self, wood, iron, base, rot):
        """Hickory handle + forged double head"""
        add_cylinder(wood, base, base + rot @ Vector((0, 0, 0.9)), 0.018, 10, radius2=0.022)
        head = base + rot @ Vector((0, 0, 0.86))
        path = [head + rot @ Vector((math.sin(a) * 0.32, 0, (math.cos(a) - 1) * 0.12 + 0.0)) for a in np.linspace(-1.2, 1.2, 13)]
        add_sweep(iron, path, [(-0.018, -0.02), (0.018, -0.02), (0.022, 0.02), (-0.022, 0.02)], True)

    # --- cave dressing ----------------------------------------------------------------
    def build_speleothems(self):
        bm = bmesh.new()
        boulders = bmesh.new()
        count = 0
        for name in NODES:
            if name in ('apron', 'portal'):
                continue
            c, f, r = node_center(name)
            for _ in range(int(r * 5)):
                off = Vector((self.rng.uniform(-r, r), self.rng.uniform(-r, r), 0)) * 0.85
                p = Vector((c.x + off.x, c.y + off.y, f + 1.2))
                top, _, _ = self.ray(p, Vector((0, 0, 1)), 14)
                flo = self.floor_at(p)
                if not top or not flo or top.z - flo.z < 2.8:
                    continue
                if self.rng.random() < 0.7:
                    length = self.rng.uniform(0.25, min(1.4, (top.z - flo.z) * 0.3))
                    rad = length * self.rng.uniform(0.12, 0.2)
                    prof = [(rad, 0.0), (rad * 0.8, -length * 0.3), (rad * 0.45, -length * 0.7), (0.004, -length)]
                    add_lathe(bm, top + Vector((0, 0, 0.12)), Matrix.Rotation(self.rng.uniform(-0.1, 0.1), 3, 'X'), prof, 9, (False, False))
                elif abs(off.x) > r * 0.45 or abs(off.y) > r * 0.45:
                    if self.rng.random() < 0.5:
                        length = self.rng.uniform(0.3, 1.1)
                        rad = length * self.rng.uniform(0.2, 0.32)
                        prof = [(rad, 0.0), (rad * 0.75, length * 0.35), (rad * 0.4, length * 0.75), (0.01, length)]
                        add_lathe(bm, flo - Vector((0, 0, 0.05)), None, prof, 9, (False, False))
                    else:
                        self.rock_blob(boulders, flo + Vector((0, 0, 0.25)), Vector((0, 0, 1)), self.rng.uniform(0.5, 1.2), 0.55, subdiv=2)
                count += 1
        finish_object('Speleothems', bm, self.mats['stone'], self.cols['props'], smooth_angle=70)
        finish_object('Boulders', boulders, self.mats['stone'], self.cols['props'], smooth_angle=45)
        print(f'[cave] {count} stalactites / stalagmites / boulders')

    def build_chamber_lamps(self):
        cages = bmesh.new(); glass = bmesh.new(); bulbs = bmesh.new()
        curve = bpy.data.curves.new('Chamber_Cables', 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = 0.011
        for name in ('main', 'main_w', 'main_e', 'shop', 'ledge', 'south1', 'west1'):
            c, f, r = node_center(name)
            anchors = []
            for k in range(7):
                ang = k / 7 * 2 * math.pi + self.rng.uniform(-0.2, 0.2)
                p = Vector((c.x + math.cos(ang) * r * 0.55, c.y + math.sin(ang) * r * 0.55, f + 1.5))
                top, _, _ = self.ray(p, Vector((0, 0, 1)), 14)
                if top:
                    anchors.append(top - Vector((0, 0, 0.1)))
            if len(anchors) > 2:
                anchors.append(anchors[0])
            for a0, a1 in zip(anchors, anchors[1:]):
                sp = curve.splines.new('POLY')
                pts = []
                for i in range(21):
                    t = i / 20
                    q = a0.lerp(a1, t)
                    q.z -= math.sin(t * math.pi) * 0.9 + 0.2
                    pts.append(q)
                sp.points.add(len(pts) - 1)
                for i, q in enumerate(pts):
                    sp.points[i].co = (q.x, q.y, q.z, 1)
                bulb = pts[10] - Vector((0, 0, 0.17))
                self.lamp_fixture(cages, glass, bulbs, bulb)
                self.add_point_light('Chamber_Lamp', bulb - Vector((0, 0, 0.03)), 150.0, (1.0, 0.68, 0.38))
        obj = bpy.data.objects.new('Chamber_Cables', curve)
        curve.materials.append(self.mats['cable'])
        self.cols['lights'].objects.link(obj)
        finish_object('Chamber_Lamp_Cages', cages, self.mats['iron'], self.cols['lights'])
        finish_object('Chamber_Lamp_Glass', glass, self.mats['glass'], self.cols['lights'])
        finish_object('Chamber_Lamp_Bulbs', bulbs, self.mats['bulb'], self.cols['lights'])

    def build_vent_duct(self):
        path = self.rail_paths[0][int(len(self.rail_paths[0]) * 0.03):]
        duct = bmesh.new()
        hangers = bmesh.new()
        pts = []
        for i in range(0, len(path), 3):
            p = path[i]
            nxt = path[min(i + 3, len(path) - 1)]
            d = Vector((nxt.x - p.x, nxt.y - p.y, 0))
            if d.length < 1e-3:
                continue
            side = Vector((-d.y, d.x, 0)).normalized()
            base = p + Vector((0, 0, 1.6))
            wall, _, wd = self.ray(base, side, 8)
            top, _, _ = self.ray(base, Vector((0, 0, 1)), 8)
            if not wall or not top:
                continue
            q = base + side * max(0.0, wd - 0.75)
            q.z = min(top.z - 0.6, p.z + 3.0)
            pts.append((q, top))
        runs, cur = [], []
        for item in pts:
            if cur and (item[0] - cur[-1][0]).length > 3.0:
                runs.append(cur)
                cur = []
            cur.append(item)
        runs.append(cur)
        ring = [(math.cos(a) * 0.3, math.sin(a) * 0.3) for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
        for run in runs:
            if len(run) < 3:
                continue
            dense = []
            for (a, _), (b, _) in zip(run, run[1:]):
                for k in range(6):
                    q = a.lerp(b, k / 6)
                    q.z -= math.sin(k / 6 * math.pi) * 0.08
                    dense.append(q)
            dense.append(run[-1][0])
            add_sweep(duct, dense, ring, True)
            for k, (q, top) in enumerate(run):
                if k % 3 == 0:
                    add_cylinder(hangers, q + Vector((0, 0, 0.3)), Vector((q.x, q.y, top.z)), 0.006, 5)
        finish_object('Vent_Duct', duct, self.mats['duct'], self.cols['props'])
        finish_object('Vent_Hangers', hangers, self.mats['iron'], self.cols['props'])

    def build_scaffold(self):
        wood = bmesh.new()
        c_main, f_main, _ = node_center('main')
        c_ledge, f_ledge, _ = node_center('ledge')
        a = Vector((c_main.x, c_main.y, 0)).lerp(Vector((c_ledge.x, c_ledge.y, 0)), 0.55)
        base = self.floor_at(Vector((a.x, a.y, f_main + 2.5)), up=4.0)
        if not base:
            return
        d = Vector((c_ledge.x - c_main.x, c_ledge.y - c_main.y, 0)).normalized()
        side = Vector((-d.y, d.x, 0))
        rot = look_rot(d)
        h = max(1.5, f_ledge - base.z + 0.9)
        for sx in (-0.9, 0.9):
            for sy in (-0.9, 0.9):
                add_box(wood, base + side * sx + d * sy + Vector((0, 0, h / 2)), (0.14, 0.14, h), rot)
        for level in (h * 0.5, h - 0.9):
            for k in range(-3, 4):
                add_box(wood, base + d * (k * 0.27) + Vector((0, 0, level)), (2.0, 0.24, 0.05), rot)
            for sgn in (-1, 1):
                add_box(wood, base + side * 0.9 * sgn + Vector((0, 0, level + 1.0)), (0.08, 1.9, 0.08), rot)
        lp = base - d * 1.2
        for sx in (-0.25, 0.25):
            add_box(wood, lp + side * sx + Vector((0, 0, h * 0.25 + 0.3)) + d * 0.35, (0.06, 0.06, h * 0.6 + 0.8),
                    rot @ Matrix.Rotation(math.radians(-18), 3, 'X'))
        for k in range(int(h * 0.6 / 0.3)):
            add_box(wood, lp + Vector((0, 0, 0.3 + k * 0.3)) + d * (0.1 + k * 0.1), (0.5, 0.04, 0.04), rot)
        finish_object('Scaffold_Ladder', wood, self.mats['wood'], self.cols['timber'], bevel=0.008)

    # --- validation -------------------------------------------------------------------
    def validate(self):
        points = [('ore %d' % (i + 1), x, y, z) for i, (x, y, z) in enumerate(ORE_SPOTS)]
        points += [('smelter', SMELTER[0], SMELTER[1], 43.15), ('shop ped', SHOP_PED[0], SHOP_PED[1], 43.26),
                   ('buyer ped', BUYER_PED[0], BUYER_PED[1], 43.17)]
        points += [('crack bench %d' % (i + 1), x, y, 43.1) for i, (x, y, _) in enumerate(CRACK_BENCHES)]
        points += [('jewel bench %d' % (i + 1), x, y, 43.1) for i, (x, y, _) in enumerate(JEWEL_BENCHES)]
        E, into, _ = entrance_frame()
        inside = E + into * 1.5 + ORIGIN
        points.append(('entrance', inside.x, inside.y, ENTRANCE[2] + 1.0))
        bad = []
        for label, x, y, z in points:
            p = local(x, y, z)
            down, _, dd = self.ray(p, Vector((0, 0, -1)), 6)
            up, _, du = self.ray(p, Vector((0, 0, 1)), 30)
            if not down or not up or dd > 3.5 or du < 0.8:
                bad.append(label)
        ok = len(points) - len(bad)
        print(f'[cave] validation: {ok}/{len(points)} FiveM points stand in open cave' + (f' - check: {", ".join(bad)}' if bad else ''))
        self.validation = (ok, len(points), bad)
        return bad

    # --- world, lights, render ------------------------------------------------------
    def setup_world(self):
        scene = bpy.context.scene
        world = bpy.data.worlds.get('Quarry_Sky') or bpy.data.worlds.new('Quarry_Sky')
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputWorld')
        bg = nt.nodes.new('ShaderNodeBackground')
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'NISHITA'
        sky.sun_disc = False
        sky.sun_elevation = math.radians(38)
        sky.sun_rotation = math.radians(130)
        sky.altitude = 300
        sky.air_density = 1.0
        sky.dust_density = 2.5
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.35
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        scene.world = world
        self.sky_bg = bg

        E, into, along = entrance_frame()
        sun_dir = (-into * 0.55 + along * 0.55 + Vector((0, 0, 0.62))).normalized()   # light towards the wall
        sun = bpy.data.lights.new('Sun', 'SUN')
        sun.energy = 5.0
        sun.angle = math.radians(0.6)
        sun.color = (1.0, 0.95, 0.88)
        so = bpy.data.objects.new('Sun', sun)
        so.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()
        self.cols['lights'].objects.link(so)

        # mine dust: homogeneous (cheap) volume box around the cave
        if DUST_DENSITY > 0:
            bm = bmesh.new()
            lo, hi = grid_bounds()
            add_box(bm, (lo + hi) / 2, tuple(hi - lo))
            nb = NB('Mine_Dust')
            vol = nb.node('ShaderNodeVolumePrincipled')
            vol.inputs['Color'].default_value = rgb(0.9, 0.82, 0.7)
            vol.inputs['Density'].default_value = DUST_DENSITY
            vol.inputs['Anisotropy'].default_value = 0.45
            nb.set(nb.out.inputs['Volume'], vol.outputs[0])
            dust = finish_object('Mine_Dust_Volume', bm, nb.mat, self.cols['lights'])
            dust.visible_shadow = False
            dust.display_type = 'BOUNDS'

        scene.render.engine = 'CYCLES'
        c = scene.cycles
        c.device = 'CPU'
        c.samples = 96
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.02
        c.use_denoising = True
        try:
            c.denoiser = 'OPENIMAGEDENOISE'
        except TypeError:
            pass
        c.max_bounces = 6
        c.diffuse_bounces = 3
        c.glossy_bounces = 3
        c.transmission_bounces = 6
        c.transparent_max_bounces = 12
        c.volume_bounces = 0
        c.caustics_reflective = False
        c.caustics_refractive = False
        c.blur_glossy = 1.0
        c.dicing_rate = 1.5
        c.offscreen_dicing_scale = 6.0
        c.max_subdivisions = 8
        scene.render.resolution_x = 3840
        scene.render.resolution_y = 2160
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_depth = '8'
        try:
            scene.view_settings.view_transform = 'AgX'
            scene.view_settings.look = 'AgX - Medium High Contrast'
        except TypeError:
            pass

    def camera(self, name, pos, target, lens=24.0, exposure=0.0, focus=None, fstop=None, ortho=None):
        cam = bpy.data.cameras.new(name)
        cam.lens = lens
        cam.sensor_width = 36.0
        cam.clip_start = 0.02
        cam.clip_end = 600
        if ortho:
            cam.type = 'ORTHO'
            cam.ortho_scale = ortho
        if focus is not None:
            cam.dof.use_dof = True
            cam.dof.focus_distance = focus
            cam.dof.aperture_fstop = fstop or 4.0
        obj = bpy.data.objects.new(name, cam)
        obj.location = pos
        obj.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        obj['exposure'] = exposure
        self.cols['cameras'].objects.link(obj)
        return obj

    def eye(self, node, off=Vector(), height=1.7):
        c, f, r = node_center(node)
        p = Vector((c.x + off.x, c.y + off.y, f + 2.0))
        hit = self.floor_at(p)
        return Vector((p.x, p.y, (hit.z if hit else f) + height))

    def build_cameras(self):
        E, into, along = entrance_frame()
        cams = {}
        portal_mid = E + Vector((0, 0, 2.2))
        cams['00_quarry_entrance'] = self.camera('Cam_Quarry', self.quarry_point(19.0, -5.0, 10.5), portal_mid + into * 1.0, 26, 0.0)
        cams['01_portal_from_inside'] = self.camera('Cam_Portal_Inside', (self.floor_at(E + into * 14 + Vector((0, 0, 1))) or E) + Vector((0, 0, 1.65)) + along * 0.6,
                                                    E - into * 6 + Vector((0, 0, 1.2)), 22, 1.8)
        fl = self.floor_at(E + into * 7.0 + along * 0.95 + Vector((0, 0, 1))) or E
        cams['02_sand_closeup'] = self.camera('Cam_Sand', fl + Vector((0, 0, 0.32)) - into * 0.0,
                                              fl + into * 3.0 + Vector((0, 0, 0.05)), 32, 2.2, focus=1.6, fstop=2.8)
        cams['03_main_chamber'] = self.camera('Cam_Main', self.eye('main_e', Vector((2, 1, 0)), 2.4), self.eye('main_w', height=1.0), 16, 2.0)
        cams['04_workshop'] = self.camera('Cam_Workshop', self.eye('shop', Vector((-6.0, -3.5, 0)), 2.0),
                                          self.ground(2919.0, 2653.5) + Vector((0, 0, 0.9)), 18, 1.6)
        cams['05_crystal_chamber'] = self.camera('Cam_Crystal', self.eye('crystal', Vector((6.0, -1.0, 0)), 1.6),
                                                 self.eye('crystal', Vector((-4.0, 1.5, 0)), 2.2), 16, 2.2)
        cams['06_deep_shaft'] = self.camera('Cam_Shaft', self.eye('low2', Vector((0, 0, 0)), 1.7), self.eye('south1', height=0.8), 18, 2.2)
        lo, hi = grid_bounds()
        center = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z + 20))
        cams['07_overview'] = self.camera('Cam_Overview', center, center - Vector((0, 0, 1)), ortho=max(hi.x - lo.x, hi.y - lo.y) + 4)
        self.cams = cams

    def cutaway(self):
        obj = bpy.data.objects.new('Cave_Cutaway', self.shell.data.copy())
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.2], context='FACES')
        bm.to_mesh(obj.data)
        bm.free()
        self.cols['shell'].objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
        return obj

    def render(self, out_dir, only=None):
        os.makedirs(out_dir, exist_ok=True)
        scene = bpy.context.scene
        res = (scene.render.resolution_x, scene.render.resolution_y)
        cut = None
        dust = bpy.data.objects.get('Mine_Dust_Volume')
        for name, cam in self.cams.items():
            if only and not any(o in name for o in only):
                continue
            overview = name.endswith('overview')
            if overview and cut is None:
                cut = self.cutaway()
            self.shell.hide_render = overview
            if cut:
                cut.hide_render = not overview
            if dust:
                dust.hide_render = overview
            self.sky_bg.inputs['Strength'].default_value = 1.2 if overview else 0.35
            scene.render.film_transparent = overview
            scene.view_settings.exposure = cam.get('exposure', 0.0)
            scene.camera = cam
            scene.render.resolution_x, scene.render.resolution_y = (res[1], res[1]) if overview else res
            scene.render.filepath = os.path.join(out_dir, name + '.png')
            t0 = time.time()
            print(f'[cave] rendering {name} at {scene.render.resolution_x}x{scene.render.resolution_y}...', flush=True)
            bpy.ops.render.render(write_still=True)
            print(f'[cave] {name} done in {time.time() - t0:.0f}s', flush=True)
        self.shell.hide_render = False
        if cut:
            cut.hide_render = True
        if dust:
            dust.hide_render = False
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.film_transparent = False

    # --- main ---------------------------------------------------------------------------
    def build(self):
        t0 = time.time()
        self.reset_scene()
        self.make_materials()
        self.build_shell()
        self.build_portal()
        self.build_quarry_props()
        self.build_supports()
        self.build_lamps()
        self.build_floodlights()
        self.build_rails()
        self.build_ores()
        self.build_crystal_chamber()
        self.build_speleothems()
        self.build_chamber_lamps()
        self.build_vent_duct()
        self.build_scaffold()
        self.build_workshop()
        for kind, bm in list(self.crystal_bms.items()):
            if bm.is_valid and len(bm.verts):
                finish_object('Workshop_Gems_' + kind, bm, self.mats['crystal_' + kind], self.cols['workshop'], smooth_angle=20)
        self.build_footprints()
        self.build_scatter()
        self.add_displacement()
        self.setup_world()
        self.build_cameras()
        self.validate()
        print(f'[cave] scene built in {time.time() - t0:.0f}s')


# ─────────────────────────────────────────────────────────────────────────────
#  4K SEAMLESS TEXTURE BAKE  (for the fast scene shader + GTA texture dictionaries)
# ─────────────────────────────────────────────────────────────────────────────
def bake_textures(out_dir, size=4096, samples=2):
    """Bake every terrain layer into a tileable PBR set:
    <layer>_albedo.png (sRGB), _roughness.png, _height.png, _normal.png (OpenGL, +Y up).
    The layer is evaluated on a 4D torus, so each map repeats with no seam."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.render.bake.margin = 0
    try:
        scene.view_settings.view_transform = 'Standard'
    except TypeError:
        pass
    me = bpy.data.meshes.new('Bake_Plane')
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    plane = bpy.data.objects.new('Bake_Plane', me)
    scene.collection.objects.link(plane)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    plane.select_set(True)
    bpy.context.view_layer.objects.active = plane

    for name, (fn, tile) in TERRAIN_LAYERS.items():
        for channel in ('albedo', 'roughness', 'height'):
            t0 = time.time()
            nb = NB(f'Bake_{name}_{channel}')
            col, rough, height, _ = fn(nb, Coord(nb, 'tile', tile))
            emit = nb.node('ShaderNodeEmission')
            nb.set(emit.inputs['Color'], col if channel == 'albedo' else (rough if channel == 'roughness' else height))
            nb.output(emit.outputs[0])
            img = bpy.data.images.new(f'bake_{name}_{channel}', size, size, float_buffer=True)
            if channel != 'albedo':
                img.colorspace_settings.name = 'Non-Color'
            tex = nb.node('ShaderNodeTexImage', image=img)
            nb.N.active = tex
            me.materials.clear()
            me.materials.append(nb.mat)
            bpy.ops.object.bake(type='EMIT', margin=0, use_clear=True)
            buf = np.empty(size * size * 4, dtype=np.float32)
            img.pixels.foreach_get(buf)
            _save_png(buf, size, os.path.join(out_dir, f'{name}_{channel}.png'), srgb=(channel == 'albedo'))
            if channel == 'height':
                _save_png(_normal_from_height(buf, size, tile / size), size,
                          os.path.join(out_dir, f'{name}_normal.png'), srgb=False)
            bpy.data.images.remove(img)
            print(f'[bake] {name}_{channel} {size}px in {time.time() - t0:.0f}s', flush=True)
    bpy.data.objects.remove(plane, do_unlink=True)
    bpy.data.meshes.remove(me)


def _save_png(buf, size, path, srgb):
    img = bpy.data.images.new(os.path.basename(path), size, size, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    img.pixels.foreach_set(buf)
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def _normal_from_height(buf, size, texel, depth=0.05):
    """OpenGL normal map from the float height (height 0..1 spans `depth` metres)"""
    h = buf.reshape(size, size, 4)[:, :, 0] * depth
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * texel)
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * texel)
    n = np.stack([-dx, -dy, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.concatenate([n * 0.5 + 0.5, np.ones((size, size, 1), np.float32)], axis=-1).astype(np.float32).ravel()


def default_texture_dir():
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')
    except NameError:
        return None


def parse_args():
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    elif argv and argv[0].endswith('.py'):
        argv = argv[1:]
    else:
        argv = []
    opts = {'render': None, 'save': None, 'res': None, 'samples': None, 'only': None, 'bake': None,
            'bake-size': '4096', 'textures': None, 'fast': False}
    i = 0
    while i < len(argv):
        key = argv[i][2:] if argv[i].startswith('--') else None
        if key == 'fast':
            opts['fast'] = True
            i += 1
        elif key in opts and i + 1 < len(argv):
            opts[key] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts


def main():
    opts = parse_args()
    tex_dir = opts['textures'] or opts['bake'] or default_texture_dir()
    if opts['bake']:
        bake_textures(opts['bake'], int(opts['bake-size']))
    cave = Cave(fast=opts['fast'], tex_dir=tex_dir)
    cave.build()
    scene = bpy.context.scene
    if opts['res']:
        w, h = opts['res'].lower().split('x')
        scene.render.resolution_x, scene.render.resolution_y = int(w), int(h)
    if opts['samples']:
        scene.cycles.samples = int(opts['samples'])
    if opts['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(opts['save']))
        print('[cave] saved', opts['save'])
    if opts['render']:
        cave.render(opts['render'], opts['only'].split(',') if opts['only'] else None)
    print('[cave] done')


if __name__ == '__main__':
    main()
