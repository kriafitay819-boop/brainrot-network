"""
URBAN RP - Cave Mining interior generator for Blender 4.x
==========================================================

Builds a complete mining cave in the style of the K4MB1 "Cave Mining" MLO:
natural rock tunnels and chambers (layered stone types), timber support sets,
mine-cart rails with carts, hanging work lamps with cables, flood-light towers,
ore veins on the walls, glowing crystal clusters, and the workshop
(smelter, stone-cracking benches, jewel benches, shop counter, buyer table).

The tunnel network is laid out in the SAME space as the FiveM resource
(fivem/urban_cavemining): local (0,0,0) = MLO origin 2889.014, 2664.655, 41.72483,
and every tunnel passes through the 35 ore spots the script uses, so the ore veins
in this model sit exactly where the server spawns ores.

Usage
-----
Inside Blender:  Scripting tab -> Open -> this file -> Run Script   (takes ~1-2 min)

Headless:
    blender -b -P cave_mine_generator.py -- --save cave_mine.blend --render previews/
or with the bpy module:
    python cave_mine_generator.py --save cave_mine.blend --render previews/

Only numpy (bundled with Blender) is needed - no add-ons.
"""

import math
import os
import random
import sys

import bpy      # must come first when running with the stand-alone bpy module
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# ─────────────────────────────────────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
ORIGIN = Vector((2889.014, 2664.655, 41.72483))   # K4MB1 MLO origin (GTA world)
VOXEL = 0.4              # cave mesh resolution in metres (0.3 = finer, slower)
Z_SCALE = 1.18           # >1 = tunnels wider than tall
CENTER_FRAC = 0.55       # tube centre height above the floor, in radii
SMOOTH_K = 2.2           # how softly tunnels blend into chambers
NOISE_LARGE = 1.35       # big lumps (m)
NOISE_MED = 0.7
NOISE_SMALL = 0.28
NOISE_RIDGE = 0.45       # sharp ledges / fractured faces
SEED = 1337

# Tunnel graph in GTA world coords: name -> (x, y, floor_z, radius)
NODES = {
    'mouth':   (2952.0, 2749.0, 42.4, 4.4),
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
    ('mouth', 'e1'), ('e1', 'e2'), ('e2', 'e3'), ('e3', 'e4'), ('e4', 'main'),
    ('main', 'main_e'), ('main', 'main_w'), ('main', 'ledge'), ('ledge', 'ledge_w'),
    ('main_w', 'west1'), ('west1', 'west2'), ('main_w', 'link1'), ('link1', 'link2'),
    ('link2', 'shop'), ('link2', 'low1'), ('low1', 'low2'), ('low2', 'low3'),
    ('low3', 'south1'), ('south1', 'south2'), ('south1', 'south3'), ('south3', 'fw1'),
    ('low3', 'fw1'), ('fw1', 'fw2'), ('fw2', 'crystal'),
]

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
    ['e1', 'e2', 'e3', 'e4', 'main', 'main_w', 'link1', 'link2', 'shop'],
    ['link2', 'low1', 'low2', 'low3', 'south1', 'south2'],
]


def local(x, y, z=0.0):
    return Vector((x - ORIGIN.x, y - ORIGIN.y, z - ORIGIN.z))


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
    # domain warp so the walls do not follow the tube shape
    wx = x + 2.5 * value_noise(x * 0.05, y * 0.05, z * 0.05, SEED + 7)
    wy = y + 2.5 * value_noise(x * 0.05, y * 0.05, z * 0.05, SEED + 8)
    n = NOISE_LARGE * value_noise(wx * 0.06, wy * 0.06, z * 0.08, SEED)
    n += NOISE_MED * value_noise(wx * 0.17, wy * 0.17, z * 0.22, SEED + 1)
    n += NOISE_SMALL * value_noise(wx * 0.5, wy * 0.5, z * 0.55, SEED + 2)
    n += NOISE_RIDGE * (1.0 - 2.0 * np.abs(value_noise(wx * 0.33, wy * 0.33, z * 0.45, SEED + 3)))
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  CAVE SDF + SURFACE NETS
# ─────────────────────────────────────────────────────────────────────────────
def node_center(name):
    x, y, f, r = NODES[name]
    p = local(x, y, f)
    return Vector((p.x, p.y, p.z + CENTER_FRAC * r)), p.z, r


def nearest_edge_point(p):
    """Closest point (in plan view) on the tunnel graph: (distance, point, floor, direction)"""
    best = None
    for a, b in EDGES:
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


def build_field():
    pts = []
    for name in NODES:
        c, f, r = node_center(name)
        pts.append((c, r))
    lo = Vector((min(c.x - r for c, r in pts) - 3, min(c.y - r for c, r in pts) - 3, min(c.z - r for c, r in pts) - 3))
    hi = Vector((max(c.x + r for c, r in pts) + 3, max(c.y + r for c, r in pts) + 3, max(c.z + r for c, r in pts) + 3))
    # open the entrance: the grid stops inside the mouth tunnel
    mouth_c, _, mouth_r = node_center('mouth')
    hi.x = mouth_c.x - 2.0

    nx = int((hi.x - lo.x) / VOXEL) + 1
    ny = int((hi.y - lo.y) / VOXEL) + 1
    nz = int((hi.z - lo.z) / VOXEL) + 1
    print(f'[cave] grid {nx} x {ny} x {nz} = {nx * ny * nz / 1e6:.1f}M samples')

    F = np.full((nx, ny, nz), 50.0, dtype=np.float32)
    floor_at = np.full((nx, ny, nz), -1000.0, dtype=np.float32)

    for A, fa, ra, B, fb, rb in segments():
        rmax = max(ra, rb) + SMOOTH_K + 2.5
        bmin = Vector((min(A.x, B.x) - rmax, min(A.y, B.y) - rmax, min(A.z, B.z) - rmax))
        bmax = Vector((max(A.x, B.x) + rmax, max(A.y, B.y) + rmax, max(A.z, B.z) + rmax))
        i0 = max(0, int((bmin.x - lo.x) / VOXEL)); i1 = min(nx, int((bmax.x - lo.x) / VOXEL) + 2)
        j0 = max(0, int((bmin.y - lo.y) / VOXEL)); j1 = min(ny, int((bmax.y - lo.y) / VOXEL) + 2)
        k0 = max(0, int((bmin.z - lo.z) / VOXEL)); k1 = min(nz, int((bmax.z - lo.z) / VOXEL) + 2)
        if i0 >= i1 or j0 >= j1 or k0 >= k1:
            continue
        X, Y, Z = np.meshgrid(
            (lo.x + np.arange(i0, i1) * VOXEL).astype(np.float32),
            (lo.y + np.arange(j0, j1) * VOXEL).astype(np.float32),
            (lo.z + np.arange(k0, k1) * VOXEL).astype(np.float32),
            indexing='ij')
        ba = B - A
        bb = ba.dot(ba)
        t = np.clip(((X - A.x) * ba.x + (Y - A.y) * ba.y + (Z - A.z) * ba.z) / bb, 0.0, 1.0)
        r = ra + (rb - ra) * t
        cx, cy, cz = A.x + ba.x * t, A.y + ba.y * t, A.z + ba.z * t
        fl = fa + (fb - fa) * t
        d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + ((Z - cz) * Z_SCALE) ** 2) - r
        seg = np.maximum(d, fl - Z)

        cur = F[i0:i1, j0:j1, k0:k1]
        h = np.clip(SMOOTH_K - np.abs(cur - seg), 0.0, None) / SMOOTH_K
        blended = np.minimum(cur, seg) - h * h * SMOOTH_K * 0.25
        closer = seg < cur
        fcur = floor_at[i0:i1, j0:j1, k0:k1]
        fcur[closer] = fl[closer]
        F[i0:i1, j0:j1, k0:k1] = blended

    # rock shelves under ore spots that sit high above the tunnel floor
    for x, y, z in ORE_SPOTS:
        spot = local(x, y, z)
        d, q, fq, _ = nearest_edge_point(spot)
        shelf = spot.z - 1.05
        if shelf - fq < 1.0:
            continue
        rad = 1.7
        i0 = max(0, int((spot.x - 4 - lo.x) / VOXEL)); i1 = min(nx, int((spot.x + 4 - lo.x) / VOXEL) + 2)
        j0 = max(0, int((spot.y - 4 - lo.y) / VOXEL)); j1 = min(ny, int((spot.y + 4 - lo.y) / VOXEL) + 2)
        k0 = max(0, int((fq - 2 - lo.z) / VOXEL)); k1 = min(nz, int((shelf + 1 - lo.z) / VOXEL) + 2)
        X, Y, Z = np.meshgrid(
            (lo.x + np.arange(i0, i1) * VOXEL).astype(np.float32),
            (lo.y + np.arange(j0, j1) * VOXEL).astype(np.float32),
            (lo.z + np.arange(k0, k1) * VOXEL).astype(np.float32),
            indexing='ij')
        top = shelf - rad
        zc = np.clip(Z, fq - 2.0, top)
        mound = np.sqrt((X - spot.x) ** 2 + (Y - spot.y) ** 2 + (Z - zc) ** 2) - rad
        cur = F[i0:i1, j0:j1, k0:k1]
        F[i0:i1, j0:j1, k0:k1] = np.maximum(cur, -mound)
        fcur = floor_at[i0:i1, j0:j1, k0:k1]
        np.maximum(fcur, np.where(mound < 0.5, shelf, -1000.0).astype(np.float32), out=fcur)

    # rock noise only near the surface (saves time)
    band = np.abs(F) < 3.4
    idx = np.nonzero(band)
    X = lo.x + idx[0].astype(np.float32) * VOXEL
    Y = lo.y + idx[1].astype(np.float32) * VOXEL
    Z = lo.z + idx[2].astype(np.float32) * VOXEL
    n = rock_noise(X, Y, Z)
    # floors stay walkable: much less noise close to the floor
    above = np.clip((Z - floor_at[idx]) / 1.6, 0.1, 1.0)

    # FiveM interaction points (ore spots, stations) stay in open cave:
    # calmer rock around them + a guaranteed pocket of air where the player stands
    dmin = np.full(X.shape, 1e9, dtype=np.float32)
    for q in interaction_points():
        d = np.sqrt((X - q.x) ** 2 + (Y - q.y) ** 2 + ((Z - q.z) * 0.8) ** 2)
        np.minimum(dmin, d, out=dmin)
    calm = np.clip((dmin - 1.2) / 3.0, 0.15, 1.0)
    vals = F[idx] + n * above * calm
    F[idx] = np.minimum(vals, dmin - 0.75)
    return F, lo


CORNERS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]])
CUBE_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def surface_nets(F, lo):
    """Naive surface nets. Quads face the negative side of F (the open cave),
    every edge is shared by exactly two quads, winding is consistent."""
    nx, ny, nz = F.shape
    n = np.array([nx, ny, nz])
    inside = F < 0
    cs = [inside[c[0]:nx - 1 + c[0], c[1]:ny - 1 + c[1], c[2]:nz - 1 + c[2]] for c in CORNERS]
    any_in = np.zeros_like(cs[0])
    all_in = np.ones_like(cs[0])
    for c in cs:
        any_in |= c
        all_in &= c
    active = any_in & ~all_in
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
#  SCENE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in (parent or bpy.context.scene.collection).children:
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def mesh_object(name, bm, material, col):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    if material:
        mesh.materials.append(material)
    col.objects.link(obj)
    return obj


def add_box(bm, center, size, rot=None):
    """Box into bmesh. rot = Matrix (3x3) or None"""
    m = Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    if rot is not None:
        m = rot.to_4x4() @ m
    m = Matrix.Translation(center) @ m
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def add_cylinder(bm, start, end, radius, segments=8, cap=True):
    d = end - start
    length = d.length
    if length < 1e-4:
        return
    rot = d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
    m = Matrix.Translation((start + end) * 0.5) @ rot
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=segments, radius1=radius, radius2=radius, depth=length, matrix=m)


def look_rot(forward, up=Vector((0, 0, 1))):
    f = forward.normalized()
    r = f.cross(up)
    if r.length < 1e-4:
        r = Vector((1, 0, 0))
    r.normalize()
    u = r.cross(f)
    return Matrix((r, f, u)).transposed()


# ─────────────────────────────────────────────────────────────────────────────
#  MATERIALS
# ─────────────────────────────────────────────────────────────────────────────
def new_material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat, nt, bsdf


def rock_material():
    """Layered stone types: sandstone, limestone, granite, basalt and slate strata"""
    mat, nt, bsdf = new_material('Cave_Rock_Strata')
    N, L = nt.nodes, nt.links
    geo = N.new('ShaderNodeNewGeometry'); geo.location = (-1400, 0)
    sep = N.new('ShaderNodeSeparateXYZ'); sep.location = (-1200, 100)
    L.new(geo.outputs['Position'], sep.inputs[0])

    warp = N.new('ShaderNodeTexNoise'); warp.location = (-1200, -150)
    warp.inputs['Scale'].default_value = 0.08
    warp.inputs['Detail'].default_value = 3.0
    L.new(geo.outputs['Position'], warp.inputs['Vector'])
    warp_mul = N.new('ShaderNodeMath'); warp_mul.operation = 'MULTIPLY'; warp_mul.location = (-1000, -150)
    warp_mul.inputs[1].default_value = 6.0
    L.new(warp.outputs['Fac'], warp_mul.inputs[0])
    strata = N.new('ShaderNodeMath'); strata.operation = 'ADD'; strata.location = (-850, 50)
    L.new(sep.outputs['Z'], strata.inputs[0]); L.new(warp_mul.outputs[0], strata.inputs[1])
    scale = N.new('ShaderNodeMath'); scale.operation = 'MULTIPLY'; scale.location = (-700, 50)
    scale.inputs[1].default_value = 0.055
    L.new(strata.outputs[0], scale.inputs[0])
    frac = N.new('ShaderNodeMath'); frac.operation = 'FRACT'; frac.location = (-550, 50)
    L.new(scale.outputs[0], frac.inputs[0])

    ramp = N.new('ShaderNodeValToRGB'); ramp.location = (-400, 50)
    el = ramp.color_ramp.elements
    stones = [
        (0.00, (0.23, 0.18, 0.13, 1)),   # sandstone
        (0.18, (0.27, 0.25, 0.21, 1)),   # limestone
        (0.36, (0.19, 0.17, 0.16, 1)),   # granite
        (0.55, (0.07, 0.07, 0.075, 1)),  # basalt
        (0.74, (0.11, 0.12, 0.14, 1)),   # slate
        (0.90, (0.21, 0.16, 0.12, 1)),   # sandstone again
    ]
    el[0].position, el[0].color = stones[0]
    el[1].position, el[1].color = stones[1]
    for pos, col in stones[2:]:
        e = el.new(pos); e.color = col
    ramp.color_ramp.interpolation = 'EASE'
    L.new(frac.outputs[0], ramp.inputs['Fac'])

    # granite speckles
    speck = N.new('ShaderNodeTexVoronoi'); speck.location = (-400, -250)
    speck.inputs['Scale'].default_value = 38.0
    L.new(geo.outputs['Position'], speck.inputs['Vector'])
    speck_ramp = N.new('ShaderNodeValToRGB'); speck_ramp.location = (-200, -250)
    speck_ramp.color_ramp.elements[0].position = 0.05
    speck_ramp.color_ramp.elements[1].position = 0.12
    L.new(speck.outputs['Distance'], speck_ramp.inputs['Fac'])
    mix_speck = N.new('ShaderNodeMix'); mix_speck.data_type = 'RGBA'; mix_speck.blend_type = 'MULTIPLY'
    mix_speck.location = (-50, 50)
    mix_speck.inputs['Factor'].default_value = 0.35
    L.new(ramp.outputs['Color'], mix_speck.inputs[6])
    L.new(speck_ramp.outputs['Color'], mix_speck.inputs[7])

    # gravel / dust on floors (normal pointing up)
    nsep = N.new('ShaderNodeSeparateXYZ'); nsep.location = (-400, 300)
    L.new(geo.outputs['Normal'], nsep.inputs[0])
    floor_ramp = N.new('ShaderNodeMapRange'); floor_ramp.location = (-200, 300)
    floor_ramp.inputs['From Min'].default_value = 0.55
    floor_ramp.inputs['From Max'].default_value = 0.85
    L.new(nsep.outputs['Z'], floor_ramp.inputs['Value'])
    mix_floor = N.new('ShaderNodeMix'); mix_floor.data_type = 'RGBA'; mix_floor.location = (100, 150)
    mix_floor.inputs[7].default_value = (0.11, 0.09, 0.07, 1)
    L.new(floor_ramp.outputs['Result'], mix_floor.inputs['Factor'])
    L.new(mix_speck.outputs[2], mix_floor.inputs[6])
    L.new(mix_floor.outputs[2], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.88

    # cracks + bumps
    crack = N.new('ShaderNodeTexVoronoi'); crack.location = (-400, -500)
    crack.feature = 'DISTANCE_TO_EDGE'
    crack.inputs['Scale'].default_value = 0.9
    L.new(geo.outputs['Position'], crack.inputs['Vector'])
    bumpn = N.new('ShaderNodeTexNoise'); bumpn.location = (-400, -700)
    bumpn.inputs['Scale'].default_value = 2.6
    bumpn.inputs['Detail'].default_value = 8.0
    L.new(geo.outputs['Position'], bumpn.inputs['Vector'])
    addh = N.new('ShaderNodeMath'); addh.operation = 'ADD'; addh.location = (-150, -600)
    L.new(crack.outputs['Distance'], addh.inputs[0]); L.new(bumpn.outputs['Fac'], addh.inputs[1])
    bump = N.new('ShaderNodeBump'); bump.location = (100, -500)
    bump.inputs['Strength'].default_value = 0.9
    bump.inputs['Distance'].default_value = 0.35
    L.new(addh.outputs[0], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def simple_material(name, color, metallic=0.0, roughness=0.6, emission=None, strength=0.0, transmission=0.0, ior=1.45):
    mat, nt, bsdf = new_material(name)
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['IOR'].default_value = ior
    if transmission:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    return mat


def wood_material():
    """Weathered timber - position based so joined meshes do not stripe"""
    mat, nt, bsdf = new_material('Mine_Timber')
    N, L = nt.nodes, nt.links
    geo = N.new('ShaderNodeNewGeometry'); geo.location = (-900, 0)
    grain = N.new('ShaderNodeTexNoise'); grain.location = (-650, 0)
    grain.inputs['Scale'].default_value = 7.0
    grain.inputs['Detail'].default_value = 9.0
    grain.inputs['Roughness'].default_value = 0.65
    L.new(geo.outputs['Position'], grain.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.location = (-400, 0)
    ramp.color_ramp.elements[0].color = (0.07, 0.04, 0.02, 1)
    ramp.color_ramp.elements[1].color = (0.26, 0.16, 0.08, 1)
    L.new(grain.outputs['Fac'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bump = N.new('ShaderNodeBump'); bump.location = (0, -250)
    bump.inputs['Strength'].default_value = 0.4
    L.new(grain.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.85
    return mat


def ore_material(name, fleck, metallic, density):
    """Rock with metallic ore flecks"""
    mat, nt, bsdf = new_material(name)
    N, L = nt.nodes, nt.links
    geo = N.new('ShaderNodeNewGeometry'); geo.location = (-900, 0)
    vor = N.new('ShaderNodeTexVoronoi'); vor.location = (-700, 0)
    vor.inputs['Scale'].default_value = density
    L.new(geo.outputs['Position'], vor.inputs['Vector'])
    noise = N.new('ShaderNodeTexNoise'); noise.location = (-700, -250)
    noise.inputs['Scale'].default_value = 3.0
    L.new(geo.outputs['Position'], noise.inputs['Vector'])
    mask = N.new('ShaderNodeMath'); mask.operation = 'MULTIPLY'; mask.location = (-500, 0)
    L.new(vor.outputs['Distance'], mask.inputs[0]); L.new(noise.outputs['Fac'], mask.inputs[1])
    ramp = N.new('ShaderNodeValToRGB'); ramp.location = (-350, 0)
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[1].position = 0.2
    L.new(mask.outputs[0], ramp.inputs['Fac'])
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.location = (-150, -100)
    inv.inputs[0].default_value = 1.0
    L.new(ramp.outputs['Color'], inv.inputs[1])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.location = (50, 100)
    mix.inputs[6].default_value = (0.16, 0.15, 0.14, 1)
    mix.inputs[7].default_value = (*fleck, 1)
    L.new(inv.outputs[0], mix.inputs['Factor'])
    L.new(mix.outputs[2], bsdf.inputs['Base Color'])
    met = N.new('ShaderNodeMath'); met.operation = 'MULTIPLY'; met.location = (50, -150)
    met.inputs[1].default_value = metallic
    L.new(inv.outputs[0], met.inputs[0])
    L.new(met.outputs[0], bsdf.inputs['Metallic'])
    rough = N.new('ShaderNodeMapRange'); rough.location = (50, -350)
    rough.inputs['To Min'].default_value = 0.85
    rough.inputs['To Max'].default_value = 0.28
    L.new(inv.outputs[0], rough.inputs['Value'])
    L.new(rough.outputs['Result'], bsdf.inputs['Roughness'])
    bump = N.new('ShaderNodeBump'); bump.location = (100, -550)
    bump.inputs['Strength'].default_value = 0.6
    L.new(noise.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def brick_material():
    mat, nt, bsdf = new_material('Furnace_Brick')
    N, L = nt.nodes, nt.links
    coord = N.new('ShaderNodeTexCoord'); coord.location = (-700, 0)
    brick = N.new('ShaderNodeTexBrick'); brick.location = (-450, 0)
    brick.inputs['Color1'].default_value = (0.32, 0.11, 0.06, 1)
    brick.inputs['Color2'].default_value = (0.22, 0.08, 0.05, 1)
    brick.inputs['Mortar'].default_value = (0.12, 0.11, 0.1, 1)
    brick.inputs['Scale'].default_value = 3.0
    L.new(coord.outputs['Object'], brick.inputs['Vector'])
    L.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    return mat


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD
# ─────────────────────────────────────────────────────────────────────────────
class Cave:
    def __init__(self):
        self.rng = random.Random(SEED)
        self.mats = {}
        self.lamps = []          # (position, tunnel-id) for cables

    # --- setup -----------------------------------------------------------------
    def reset_scene(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.materials):
            for item in list(block):
                block.remove(item)
        for col in list(bpy.data.collections):
            bpy.data.collections.remove(col)
        root = collection('CaveMining')
        self.cols = {
            'shell': collection('Cave_Shell', root),
            'timber': collection('Timber_Supports', root),
            'rails': collection('Rails_Carts', root),
            'lights': collection('Lights', root),
            'ores': collection('Ore_Veins', root),
            'crystals': collection('Crystals', root),
            'workshop': collection('Workshop', root),
            'props': collection('Rubble_Props', root),
            'cameras': collection('Cameras', root),
        }

    def make_materials(self):
        m = self.mats
        m['rock'] = rock_material()
        m['wood'] = wood_material()
        m['steel'] = simple_material('Rail_Steel', (0.20, 0.20, 0.21), metallic=1.0, roughness=0.42)
        m['rust'] = simple_material('Cart_Rust', (0.25, 0.11, 0.05), metallic=0.6, roughness=0.75)
        m['bulb'] = simple_material('Lamp_Bulb', (1.0, 0.8, 0.5), emission=(1.0, 0.72, 0.42), strength=60.0)
        m['cage'] = simple_material('Lamp_Cage', (0.05, 0.05, 0.05), metallic=0.8, roughness=0.5)
        m['cable'] = simple_material('Cable_Rubber', (0.02, 0.02, 0.02), roughness=0.55)
        m['flood'] = simple_material('Flood_Lens', (1.0, 1.0, 0.95), emission=(1.0, 0.95, 0.85), strength=40.0)
        m['yellow'] = simple_material('Paint_Yellow', (0.75, 0.52, 0.03), metallic=0.3, roughness=0.5)
        m['brick'] = brick_material()
        m['molten'] = simple_material('Molten_Glow', (1.0, 0.35, 0.05), emission=(1.0, 0.33, 0.04), strength=35.0)
        m['iron_dark'] = simple_material('Iron_Dark', (0.06, 0.06, 0.065), metallic=0.9, roughness=0.55)
        m['canvas'] = simple_material('Crate_Wood', (0.36, 0.25, 0.14), roughness=0.85)
        m['duct'] = simple_material('Vent_Duct', (0.8, 0.55, 0.05), roughness=0.7)
        m['gold'] = simple_material('Gold_Bar', (1.0, 0.72, 0.28), metallic=1.0, roughness=0.22)
        ores = {
            'coal':    ((0.03, 0.03, 0.03), 0.2, 9.0),
            'copper':  ((0.78, 0.40, 0.18), 1.0, 7.0),
            'iron':    ((0.42, 0.18, 0.10), 0.6, 8.0),
            'tin':     ((0.62, 0.63, 0.66), 1.0, 7.0),
            'lead':    ((0.24, 0.27, 0.33), 0.9, 7.0),
            'bauxite': ((0.55, 0.22, 0.10), 0.1, 6.0),
            'gold':    ((1.00, 0.74, 0.25), 1.0, 8.0),
        }
        for name, (col, met, dens) in ores.items():
            m['ore_' + name] = ore_material('Ore_' + name.capitalize(), col, met, dens)
        crystals = {
            'ruby': (1.0, 0.06, 0.08), 'emerald': (0.08, 1.0, 0.3),
            'sapphire': (0.12, 0.3, 1.0), 'diamond': (0.85, 0.95, 1.0),
        }
        for name, col in crystals.items():
            m['crystal_' + name] = simple_material('Crystal_' + name.capitalize(), tuple(c * 0.5 for c in col), roughness=0.04,
                                                   emission=col, strength=0.35, ior=1.76)
            m['crystal_' + name].node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 1.0

    # --- cave shell --------------------------------------------------------------
    def build_shell(self):
        F, lo = build_field()
        verts, faces = surface_nets(F, lo)
        del F
        verts, faces = keep_big_components(verts, faces)

        mesh = bpy.data.meshes.new('Cave_Shell')
        mesh.from_pydata(verts.tolist(), [], faces.tolist())
        mesh.validate(clean_customdata=False)
        mesh.update()
        # surface nets winds every quad towards the open cave, so normals already face the player
        try:
            mesh.shade_smooth()
        except AttributeError:      # Blender < 4.1
            mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
        normals = np.zeros(len(mesh.polygons) * 3)
        mesh.polygons.foreach_get('normal', normals)
        normals = normals.reshape(-1, 3)
        mesh.materials.append(self.mats['rock'])
        obj = bpy.data.objects.new('Cave_Shell', mesh)
        self.cols['shell'].objects.link(obj)
        self.shell = obj
        self.bvh = BVHTree.FromPolygons([v.co for v in mesh.vertices], [p.vertices for p in mesh.polygons])
        print(f'[cave] shell: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces')

        # simple box-projection UVs so the shell exports cleanly (Sollumz / FBX)
        uv = mesh.uv_layers.new(name='UVMap')
        loops_uv = np.zeros(len(mesh.loops) * 2)
        co = np.zeros(len(mesh.vertices) * 3); mesh.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        vidx = np.zeros(len(mesh.loops), dtype=np.int64); mesh.loops.foreach_get('vertex_index', vidx)
        totals = np.zeros(len(mesh.polygons), dtype=np.int64); mesh.polygons.foreach_get('loop_total', totals)
        loop_face = np.repeat(np.arange(len(mesh.polygons)), totals)
        n = np.abs(normals[loop_face])
        p = co[vidx] / 4.0
        u = np.where(n[:, 2] >= np.maximum(n[:, 0], n[:, 1]), p[:, 0], np.where(n[:, 0] > n[:, 1], p[:, 1], p[:, 0]))
        v = np.where(n[:, 2] >= np.maximum(n[:, 0], n[:, 1]), p[:, 1], p[:, 2])
        loops_uv[0::2] = u; loops_uv[1::2] = v
        uv.data.foreach_set('uv', loops_uv)

        # collision proxy for GTA: decimated copy
        col_obj = obj.copy()
        col_obj.data = mesh.copy()
        col_obj.name = 'Cave_Collision'
        mod = col_obj.modifiers.new('Decimate', 'DECIMATE')
        mod.ratio = 0.35
        col_obj.hide_render = True
        col_obj.display_type = 'WIRE'
        self.cols['shell'].objects.link(col_obj)
        col_obj.hide_set(True)

    # --- raycasts ------------------------------------------------------------------
    def ray(self, origin, direction, dist=30.0):
        hit, normal, _, d = self.bvh.ray_cast(origin, direction.normalized(), dist)
        return hit, normal, d

    def floor_at(self, p, up=2.5):
        hit, n, d = self.ray(p + Vector((0, 0, up)), Vector((0, 0, -1)), 12.0)
        return hit

    # --- timber supports + lamps -----------------------------------------------
    def build_supports(self):
        bm = bmesh.new()
        lamp_index = 0
        for ei, (a, b) in enumerate(EDGES):
            if a in CHAMBERS and b in CHAMBERS:
                continue
            A, fa, ra = node_center(a); B, fb, rb = node_center(b)
            seg = B - A
            flat = Vector((seg.x, seg.y, 0))
            if flat.length < 3:
                continue
            fwd = flat.normalized()
            side = Vector((-fwd.y, fwd.x, 0))
            length = seg.length
            start = (ra + 1.0) if a in CHAMBERS else 1.5
            end = length - ((rb + 1.0) if b in CHAMBERS else 1.5)
            s = start
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
                pl = base + side * max(0.5, ld - 0.4)
                pr = base - side * max(0.5, rd - 0.4)
                top_l, _, tl = self.ray(pl, Vector((0, 0, 1)), 8)
                top_r, _, tr = self.ray(pr, Vector((0, 0, 1)), 8)
                zf = fl.z
                h = min(tl if top_l else 3.0, tr if top_r else 3.0) + (base.z - zf) - 0.15
                h = max(2.1, min(h, 3.4))
                pl.z = pr.z = zf
                rot = look_rot(fwd)
                for p in (pl, pr):
                    add_box(bm, p + Vector((0, 0, h / 2)), (0.24, 0.24, h), rot)
                cap_c = (pl + pr) / 2 + Vector((0, 0, h + 0.14))
                add_box(bm, cap_c, ((pl - pr).length + 0.5, 0.28, 0.28), rot)   # X of rot = across the tunnel
                # knee braces
                for p, sgn in ((pl, -1), (pr, 1)):
                    b0 = p + Vector((0, 0, h - 0.7)) + side * (sgn * 0.05)
                    b1 = p + Vector((0, 0, h)) + side * (sgn * 0.6)
                    add_cylinder(bm, b0, b1, 0.07, 6)
                if lamp_index % 2 == 0:
                    self.lamps.append((cap_c - Vector((0, 0, 0.55)), ei, cap_c - Vector((0, 0, 0.14))))
                lamp_index += 1
                s += 4.2
        obj = mesh_object('Timber_Sets', bm, self.mats['wood'], self.cols['timber'])
        return obj

    def build_lamps(self):
        bulbs = bmesh.new()
        cages = bmesh.new()
        by_edge = {}
        for pos, ei, anchor in self.lamps:
            bmesh.ops.create_uvsphere(bulbs, u_segments=10, v_segments=6, radius=0.07, matrix=Matrix.Translation(pos))
            add_cylinder(cages, pos + Vector((0, 0, 0.06)), pos + Vector((0, 0, 0.16)), 0.06, 8)
            light = bpy.data.lights.new('Work_Lamp', 'POINT')
            light.energy = 140.0
            light.color = (1.0, 0.72, 0.45)
            light.shadow_soft_size = 0.08
            lo = bpy.data.objects.new('Work_Lamp', light)
            lo.location = pos
            self.cols['lights'].objects.link(lo)
            by_edge.setdefault(ei, []).append((pos, anchor))
        mesh_object('Lamp_Bulbs', bulbs, self.mats['bulb'], self.cols['lights'])
        mesh_object('Lamp_Cages', cages, self.mats['cage'], self.cols['lights'])

        # sagging cables between consecutive lamps on the same tunnel
        curve = bpy.data.curves.new('Lamp_Cables', 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = 0.012
        curve.bevel_resolution = 1
        for ei, items in by_edge.items():
            for (p0, a0), (p1, a1) in zip(items, items[1:]):
                sp = curve.splines.new('POLY')
                pts = []
                for i in range(13):
                    t = i / 12
                    q = a0.lerp(a1, t)
                    q.z -= math.sin(t * math.pi) * 0.35 + 0.05
                    pts.append(q)
                sp.points.add(len(pts) - 1)
                for i, q in enumerate(pts):
                    sp.points[i].co = (q.x, q.y, q.z, 1)
            for p, a in items:
                sp = curve.splines.new('POLY')
                sp.points.add(1)
                sp.points[0].co = (a.x, a.y, a.z - 0.05, 1)
                sp.points[1].co = (p.x, p.y, p.z + 0.16, 1)
        obj = bpy.data.objects.new('Lamp_Cables', curve)
        curve.materials.append(self.mats['cable'])
        self.cols['lights'].objects.link(obj)

    def build_floodlights(self):
        spots = [('main', Vector((3.0, -2.0, 0))), ('main', Vector((-5.0, 4.0, 0))), ('main_w', Vector((0, -2, 0))),
                 ('shop', Vector((-4.0, 3.0, 0))), ('south1', Vector((0, 0, 0))),
                 ('west2', Vector((0, 0, 0))), ('ledge', Vector((0, 0, 0)))]
        steel = bmesh.new(); lens = bmesh.new()
        for name, off in spots:
            c, f, r = node_center(name)
            base = Vector((c.x + off.x, c.y + off.y, f + 1.0))
            fl = self.floor_at(base)
            if not fl:
                continue
            h = 3.2
            for k in range(3):
                ang = k * 2 * math.pi / 3
                foot = fl + Vector((math.cos(ang) * 0.6, math.sin(ang) * 0.6, 0))
                add_cylinder(steel, foot, fl + Vector((0, 0, 1.2)), 0.03, 6)
            add_cylinder(steel, fl, fl + Vector((0, 0, h)), 0.045, 8)
            target = Vector((c.x, c.y, f + 0.5))
            d = (target - (fl + Vector((0, 0, h)))).normalized()
            for side in (-0.35, 0.35):
                head = fl + Vector((0, 0, h)) + Vector((-d.y, d.x, 0)).normalized() * side
                rot = look_rot(d)
                add_box(steel, head, (0.4, 0.18, 0.3), rot)
                add_box(lens, head + d * 0.1, (0.34, 0.02, 0.24), rot)
                light = bpy.data.lights.new('Flood', 'SPOT')
                light.energy = 2200.0
                light.spot_size = math.radians(85)
                light.spot_blend = 0.6
                light.color = (1.0, 0.93, 0.82)
                light.shadow_soft_size = 0.15
                lo = bpy.data.objects.new('Flood', light)
                lo.location = head + d * 0.15
                lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
                self.cols['lights'].objects.link(lo)
        mesh_object('Flood_Towers', steel, self.mats['yellow'], self.cols['lights'])
        mesh_object('Flood_Lenses', lens, self.mats['flood'], self.cols['lights'])

    # --- rails + carts -------------------------------------------------------------
    def rail_path(self, names):
        pts = []
        for n in names:
            c, f, r = node_center(n)
            pts.append(Vector((c.x, c.y, f)))
        # Catmull-Rom
        out = []
        ext = [pts[0]] + pts + [pts[-1]]
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            seg_len = (p2 - p1).length
            steps = max(2, int(seg_len / 0.35))
            for s in range(steps):
                t = s / steps
                t2, t3 = t * t, t * t * t
                q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
                out.append(q)
        out.append(pts[-1])
        # drop onto the floor + smooth heights
        zs = []
        for q in out:
            hit = self.floor_at(Vector((q.x, q.y, q.z + 1.2)))
            zs.append(hit.z if hit else q.z)
        zs = np.convolve(np.pad(zs, 6, mode='edge'), np.ones(13) / 13, mode='valid')
        return [Vector((q.x, q.y, z + 0.03)) for q, z in zip(out, zs)]

    def build_rails(self):
        rails = bmesh.new(); sleepers = bmesh.new()
        carts_at = []
        for ri, route in enumerate(RAIL_ROUTES):
            path = self.rail_path(route)
            since = 0.0
            for i in range(len(path) - 1):
                p0, p1 = path[i], path[i + 1]
                d = p1 - p0
                if d.length < 1e-3:
                    continue
                fwd = Vector((d.x, d.y, 0)).normalized()
                side = Vector((-fwd.y, fwd.x, 0))
                for s in (-0.45, 0.45):
                    add_cylinder(rails, p0 + side * s + Vector((0, 0, 0.1)), p1 + side * s + Vector((0, 0, 0.1)), 0.035, 4)
                since += d.length
                if since > 0.7:
                    since = 0.0
                    add_box(sleepers, p0 + Vector((0, 0, 0.03)), (1.35, 0.2, 0.1), look_rot(fwd))
            for frac in ((0.18, 0.62) if ri == 0 else (0.45,)):
                k = int(len(path) * frac)
                carts_at.append((path[k], (path[k + 1] - path[k - 1])))
        mesh_object('Rails', rails, self.mats['steel'], self.cols['rails'])
        mesh_object('Rail_Sleepers', sleepers, self.mats['wood'], self.cols['rails'])

        body = bmesh.new(); wheels = bmesh.new(); load = bmesh.new()
        for pos, tangent in carts_at:
            fwd = Vector((tangent.x, tangent.y, 0)).normalized()
            rot = look_rot(fwd)
            c = pos + Vector((0, 0, 0.75))
            # tub: floor + 4 walls (flared)
            add_box(body, c + Vector((0, 0, -0.3)), (0.95, 1.5, 0.08), rot)
            side = Vector((-fwd.y, fwd.x, 0))
            for sgn in (-1, 1):
                add_box(body, c + side * sgn * 0.5, (0.07, 1.55, 0.7), rot @ Matrix.Rotation(math.radians(8 * sgn), 3, 'Y'))
                add_box(body, c + fwd * sgn * 0.78, (1.05, 0.07, 0.7), rot)
            for sx in (-0.45, 0.45):
                for sy in (-0.5, 0.5):
                    wc = pos + side * sx + fwd * sy + Vector((0, 0, 0.2))
                    add_cylinder(wheels, wc - side * 0.05, wc + side * 0.05, 0.18, 12)
            for k in range(9):
                off = side * self.rng.uniform(-0.3, 0.3) + fwd * self.rng.uniform(-0.55, 0.55)
                bmesh.ops.create_icosphere(load, subdivisions=1, radius=self.rng.uniform(0.14, 0.24),
                                           matrix=Matrix.Translation(c + off + Vector((0, 0, 0.18))))
        mesh_object('Mine_Carts', body, self.mats['rust'], self.cols['rails'])
        mesh_object('Mine_Cart_Wheels', wheels, self.mats['iron_dark'], self.cols['rails'])
        mesh_object('Mine_Cart_Ore', load, self.mats['ore_copper'], self.cols['rails'])

    # --- ores + crystals -----------------------------------------------------------
    def rock_blob(self, bm, center, normal, size, squash=0.6):
        rot = normal.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        m = Matrix.Translation(center) @ rot @ Matrix.Diagonal((size, size * self.rng.uniform(0.7, 1.1), size * squash, 1))
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=m)
        for v in res['verts']:
            v.co += (v.co - center).normalized() * self.rng.uniform(-0.3, 0.15) * size   # faceted (flat) rock

    def crystal_cluster(self, bm, center, normal, count, scale):
        """Hexagonal crystal prisms with pointed tips, fanning out of the rock"""
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

    def build_ores(self):
        order = ['coal', 'copper', 'iron', 'coal', 'tin', 'copper', 'lead', 'iron', 'bauxite', 'gold']
        crystal_spots = {21: 'ruby', 22: 'emerald', 23: 'sapphire', 24: 'diamond', 25: 'ruby', 9: 'sapphire', 26: 'emerald'}
        per_type = {}
        crystals = {}
        placed = 0
        for i, (x, y, z) in enumerate(ORE_SPOTS):
            p = local(x, y, z)
            d, q, _, dirv = nearest_edge_point(p)
            out = Vector((p.x - q.x, p.y - q.y, 0))
            if out.length < 0.6:
                out = Vector((-dirv.y, dirv.x, 0)) * (1 if i % 2 == 0 else -1)
            out.normalize()
            origin = Vector((p.x, p.y, p.z - 0.2))
            hit, n, dist = None, None, None
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
                self.add_glow(hit + n * 0.5, kind, 45)
            else:
                kind = order[i % len(order)]
                bm = per_type.setdefault(kind, bmesh.new())
                for k in range(self.rng.randint(4, 7)):
                    off = Vector((self.rng.uniform(-0.6, 0.6), self.rng.uniform(-0.6, 0.6), self.rng.uniform(-0.45, 0.45)))
                    off -= n * off.dot(n)
                    self.rock_blob(bm, hit + off, n, self.rng.uniform(0.3, 0.6))
        for kind, bm in per_type.items():
            mesh_object('Ore_' + kind, bm, self.mats['ore_' + kind], self.cols['ores'])
        self.crystal_bms = crystals
        print(f'[cave] {placed}/{len(ORE_SPOTS)} ore veins placed on the walls')

    def add_glow(self, pos, kind, energy):
        colors = {'ruby': (1, 0.1, 0.1), 'emerald': (0.1, 1, 0.3), 'sapphire': (0.2, 0.4, 1), 'diamond': (0.8, 0.9, 1)}
        light = bpy.data.lights.new('Crystal_Glow', 'POINT')
        light.energy = energy
        light.color = colors[kind]
        light.shadow_soft_size = 0.3
        lo = bpy.data.objects.new('Crystal_Glow', light)
        lo.location = pos
        self.cols['crystals'].objects.link(lo)

    def build_crystal_chamber(self):
        c, f, r = node_center('crystal')
        kinds = ['ruby', 'emerald', 'sapphire', 'sapphire', 'emerald', 'ruby', 'diamond']
        n_placed = 0
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
                self.add_glow(hit + n * 0.8, kind, 150)
            n_placed += 1
        for kind, bm in self.crystal_bms.items():
            mesh_object('Crystals_' + kind, bm, self.mats['crystal_' + kind], self.cols['crystals'])
        self.crystal_bms = {}

    # --- rubble ---------------------------------------------------------------------
    def build_rubble(self):
        bases = []
        for k in range(6):
            bm = bmesh.new()
            self.rock_blob(bm, Vector(), Vector((0, 0, 1)), 1.0, squash=self.rng.uniform(0.45, 0.8))
            me = bpy.data.meshes.new(f'Rubble_Base_{k}')
            bm.to_mesh(me); bm.free()
            me.materials.append(self.mats['rock'])
            bases.append(me)
        count = 0
        for a, b in EDGES:
            A, fa, ra = node_center(a); B, fb, rb = node_center(b)
            seg = B - A
            n = int(seg.length / 1.3)
            fwd = Vector((seg.x, seg.y, 0)).normalized()
            side = Vector((-fwd.y, fwd.x, 0))
            for _ in range(n):
                t = self.rng.random()
                axis = A + seg * t
                r = ra + (rb - ra) * t
                fz = fa + (fb - fa) * t
                p = Vector((axis.x, axis.y, fz + 1.0)) + side * self.rng.choice((-1, 1)) * self.rng.uniform(0.55, 0.95) * r * 0.75
                hit = self.floor_at(p)
                if not hit:
                    continue
                s = self.rng.uniform(0.08, 0.45) if self.rng.random() < 0.85 else self.rng.uniform(0.5, 1.1)
                obj = bpy.data.objects.new('Rubble', self.rng.choice(bases))
                obj.location = hit + Vector((0, 0, s * 0.2))
                obj.rotation_euler = (self.rng.uniform(-0.3, 0.3), self.rng.uniform(-0.3, 0.3), self.rng.uniform(0, 6.28))
                obj.scale = (s, s * self.rng.uniform(0.7, 1.2), s)
                self.cols['props'].objects.link(obj)
                count += 1
        print(f'[cave] {count} rubble rocks')

    # --- workshop -------------------------------------------------------------------
    def ground(self, x, y):
        p = local(x, y, NODES['shop'][2] + 1.2)
        hit = self.floor_at(p, up=1.0)
        return hit if hit else Vector((p.x, p.y, local(0, 0, NODES['shop'][2]).z))

    def build_workshop(self):
        wood = bmesh.new(); iron = bmesh.new(); brick = bmesh.new(); glow = bmesh.new(); crates = bmesh.new()
        gold = bmesh.new()

        # plank deck under the stations
        deck_c = self.ground(2915.5, 2650.5)
        rot = Matrix.Rotation(math.radians(230), 3, 'Z')
        for i in range(-14, 15):
            off = rot @ Vector((i * 0.26, 0, 0))
            add_box(wood, deck_c + off + Vector((0, 0, 0.06)), (0.24, 7.5, 0.06), rot)

        # smelter
        s = self.ground(SMELTER[0], SMELTER[1])
        add_box(brick, s + Vector((0, 0, 0.7)), (1.8, 1.8, 1.4))
        add_box(brick, s + Vector((0, 0, 1.75)), (1.3, 1.3, 0.7))
        top, _, dist = self.ray(s + Vector((0, 0, 2.0)), Vector((0, 0, 1)), 15)
        chimney_top = top if top else s + Vector((0, 0, 6))
        add_cylinder(iron, s + Vector((0, 0, 2.1)), chimney_top + Vector((0, 0, 0.3)), 0.28, 12)
        face = (self.ground(2917.5, 2650.5) - s)
        face.z = 0
        face.normalize()
        add_box(glow, s + face * 0.91 + Vector((0, 0, 0.75)), (0.7, 0.05, 0.55), look_rot(face))
        light = bpy.data.lights.new('Smelter_Fire', 'POINT')
        light.energy = 450.0
        light.color = (1.0, 0.38, 0.08)
        light.shadow_soft_size = 0.4
        lo = bpy.data.objects.new('Smelter_Fire', light)
        lo.location = s + face * 1.3 + Vector((0, 0, 0.8))
        self.cols['workshop'].objects.link(lo)
        # crucible + ingot moulds next to it
        side = Vector((-face.y, face.x, 0))
        add_cylinder(iron, s + face * 1.2 + side * 1.2, s + face * 1.2 + side * 1.2 + Vector((0, 0, 0.9)), 0.05, 6)
        for k in range(4):
            add_box(gold, s + face * 1.3 + side * (1.6 + k * 0.22) + Vector((0, 0, 0.85)), (0.16, 0.3, 0.07), look_rot(face))
        add_box(wood, s + face * 1.3 + side * 1.9 + Vector((0, 0, 0.4)), (1.2, 0.7, 0.8), look_rot(face))

        # stone cracking benches (vertical drills)
        for x, y, hdg in CRACK_BENCHES:
            g = self.ground(x, y)
            r = Matrix.Rotation(math.radians(hdg), 3, 'Z')
            fwd = r @ Vector((0, 1, 0))
            c = g + fwd * 0.6
            add_box(iron, c + Vector((0, 0, 0.45)), (0.9, 0.7, 0.9), r)
            add_cylinder(iron, c + Vector((0, 0, 0.9)), c + Vector((0, 0, 2.1)), 0.07, 10)
            add_box(iron, c + Vector((0, 0, 2.0)), (0.35, 0.5, 0.35), r)
            add_cylinder(iron, c + Vector((0, 0, 1.8)), c + Vector((0, 0, 1.25)), 0.03, 8)

        # jewel benches
        for x, y, hdg in JEWEL_BENCHES:
            g = self.ground(x, y)
            r = Matrix.Rotation(math.radians(hdg), 3, 'Z')
            fwd = r @ Vector((0, 1, 0))
            c = g + fwd * 0.65
            add_box(wood, c + Vector((0, 0, 0.9)), (1.4, 0.7, 0.07), r)
            for sx in (-0.62, 0.62):
                for sy in (-0.3, 0.3):
                    add_box(wood, c + (r @ Vector((sx, sy, 0))) + Vector((0, 0, 0.45)), (0.07, 0.07, 0.9), r)
            add_box(iron, c + Vector((0, 0, 1.0)), (0.2, 0.15, 0.14), r)
            add_cylinder(iron, c + (r @ Vector((0.45, 0.15, 0))) + Vector((0, 0, 0.94)), c + (r @ Vector((0.45, 0.15, 0))) + Vector((0, 0, 1.45)), 0.015, 6)
            bmesh.ops.create_uvsphere(glow, u_segments=8, v_segments=5, radius=0.05, matrix=Matrix.Translation(c + (r @ Vector((0.3, 0.1, 0))) + Vector((0, 0, 1.45))))
            lamp = bpy.data.lights.new('Bench_Lamp', 'POINT')
            lamp.energy = 40.0
            lamp.color = (1.0, 0.9, 0.75)
            lo = bpy.data.objects.new('Bench_Lamp', lamp)
            lo.location = c + (r @ Vector((0.3, 0.1, 0))) + Vector((0, 0, 1.35))
            self.cols['workshop'].objects.link(lo)
            # a few cut gems on the table
            for kind in ('ruby', 'emerald', 'sapphire'):
                bmg = self.crystal_bms.setdefault(kind, bmesh.new())
                self.crystal_cluster(bmg, c + (r @ Vector((self.rng.uniform(-0.5, 0.1), self.rng.uniform(-0.2, 0.2), 0))) + Vector((0, 0, 0.94)), Vector((0, 0, 1)), 1, 0.25)

        # shop counter + shelves (ped stands behind it)
        g = self.ground(SHOP_PED[0], SHOP_PED[1])
        r = Matrix.Rotation(math.radians(SHOP_PED[2]), 3, 'Z')
        fwd = r @ Vector((0, 1, 0))
        add_box(wood, g + fwd * 0.9 + Vector((0, 0, 0.5)), (2.6, 0.6, 1.0), r)
        for k in range(3):
            add_box(wood, g - fwd * 0.8 + Vector((0, 0, 0.5 + k * 0.6)), (2.4, 0.45, 0.05), r)
        for sx in (-1.15, 1.15):
            add_box(wood, g - fwd * 0.8 + (r @ Vector((sx, 0, 0))) + Vector((0, 0, 0.95)), (0.06, 0.45, 1.9), r)
        # tools on the counter / shelves
        for k in range(3):
            base = g + fwd * 0.9 + (r @ Vector((-0.8 + k * 0.6, 0, 0))) + Vector((0, 0, 1.02))
            add_cylinder(wood, base, base + (r @ Vector((0.0, 0.0, 0))) + (r @ Vector((0.45, 0, 0))), 0.02, 6)
            add_box(iron, base + (r @ Vector((0.45, 0, 0))), (0.06, 0.38, 0.05), r)
        for k in range(5):
            add_box(crates, g - fwd * 0.8 + (r @ Vector((-0.9 + k * 0.45, 0, 0))) + Vector((0, 0, 0.65 + (k % 2) * 0.6)), (0.35, 0.3, 0.25), r)

        # buyer table with scale + gold bars
        g = self.ground(BUYER_PED[0], BUYER_PED[1])
        r = Matrix.Rotation(math.radians(BUYER_PED[2]), 3, 'Z')
        fwd = r @ Vector((0, 1, 0))
        t = g + fwd * 0.85
        add_box(wood, t + Vector((0, 0, 0.88)), (1.6, 0.8, 0.07), r)
        for sx in (-0.7, 0.7):
            for sy in (-0.33, 0.33):
                add_box(wood, t + (r @ Vector((sx, sy, 0))) + Vector((0, 0, 0.44)), (0.08, 0.08, 0.88), r)
        add_box(iron, t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 0.96)), (0.3, 0.3, 0.1), r)
        add_cylinder(iron, t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 1.0)), t + (r @ Vector((-0.4, 0, 0))) + Vector((0, 0, 1.25)), 0.02, 6)
        for k in range(6):
            add_box(gold, t + (r @ Vector((0.25 + (k % 3) * 0.17, -0.1 + (k // 3) * 0.2, 0))) + Vector((0, 0, 0.95 + (k // 3) * 0.0)), (0.15, 0.08, 0.06), r)

        # crates + barrels around the chamber walls
        c, f, rad = node_center('shop')
        for k in range(22):
            ang = self.rng.uniform(0, 2 * math.pi)
            dirv = Vector((math.cos(ang), math.sin(ang), 0))
            hit, n, dist = self.ray(Vector((c.x, c.y, f + 0.8)), dirv, 20)
            if not hit:
                continue
            pos = hit - dirv * self.rng.uniform(0.5, 0.9)
            flo = self.floor_at(pos)
            if not flo:
                continue
            if k % 3 == 0:
                add_cylinder(iron, flo, flo + Vector((0, 0, 0.9)), 0.3, 14)
            else:
                size = self.rng.uniform(0.5, 0.8)
                add_box(crates, flo + Vector((0, 0, size / 2)), (size, size, size), Matrix.Rotation(ang, 3, 'Z'))
                if self.rng.random() < 0.4:
                    add_box(crates, flo + Vector((0, 0, size + 0.25)), (0.5, 0.5, 0.5), Matrix.Rotation(ang + 0.3, 3, 'Z'))

        mesh_object('Workshop_Wood', wood, self.mats['wood'], self.cols['workshop'])
        mesh_object('Workshop_Iron', iron, self.mats['iron_dark'], self.cols['workshop'])
        mesh_object('Smelter_Brick', brick, self.mats['brick'], self.cols['workshop'])
        mesh_object('Smelter_Glow', glow, self.mats['molten'], self.cols['workshop'])
        mesh_object('Crates', crates, self.mats['canvas'], self.cols['workshop'])
        mesh_object('Gold_Bars', gold, self.mats['gold'], self.cols['workshop'])

    # --- cave dressing ----------------------------------------------------------------
    def build_speleothems(self):
        """Stalactites from the chamber ceilings, stalagmites and boulders on the floors"""
        bm = bmesh.new()
        boulders = bmesh.new()
        count = 0
        for name in NODES:
            c, f, r = node_center(name)
            tries = int(r * 5)
            for _ in range(tries):
                off = Vector((self.rng.uniform(-r, r), self.rng.uniform(-r, r), 0)) * 0.85
                p = Vector((c.x + off.x, c.y + off.y, f + 1.2))
                top, n_top, dist_up = self.ray(p, Vector((0, 0, 1)), 14)
                flo = self.floor_at(p)
                if not top or not flo:
                    continue
                height = top.z - flo.z
                if height < 2.8:
                    continue
                if self.rng.random() < 0.7:
                    length = self.rng.uniform(0.3, min(1.6, height * 0.3))
                    rad = length * self.rng.uniform(0.12, 0.22)
                    m = Matrix.Translation(top + Vector((0, 0, -length / 2 + 0.1)))
                    bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.0, radius2=rad, depth=length, matrix=m)
                elif abs(off.x) > r * 0.45 or abs(off.y) > r * 0.45:
                    # stalagmites / boulders stay near the walls so paths stay clear
                    if self.rng.random() < 0.5:
                        length = self.rng.uniform(0.3, 1.2)
                        rad = length * self.rng.uniform(0.18, 0.3)
                        m = Matrix.Translation(flo + Vector((0, 0, length / 2 - 0.05)))
                        bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=rad, radius2=0.0, depth=length, matrix=m)
                    else:
                        self.rock_blob(boulders, flo + Vector((0, 0, 0.3)), Vector((0, 0, 1)), self.rng.uniform(0.6, 1.4), 0.55)
                count += 1
        mesh_object('Speleothems', bm, self.mats['rock'], self.cols['props'])
        mesh_object('Boulders', boulders, self.mats['rock'], self.cols['props'])
        print(f'[cave] {count} stalactites / stalagmites / boulders')

    def build_chamber_lamps(self):
        """Festoon strings of bulbs across the big chambers"""
        bulbs = bmesh.new()
        curve = bpy.data.curves.new('Chamber_Cables', 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = 0.012
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
                for i in range(15):
                    t = i / 14
                    q = a0.lerp(a1, t)
                    q.z -= math.sin(t * math.pi) * 0.9 + 0.2
                    pts.append(q)
                sp.points.add(len(pts) - 1)
                for i, q in enumerate(pts):
                    sp.points[i].co = (q.x, q.y, q.z, 1)
                bulb = pts[7] - Vector((0, 0, 0.12))
                bmesh.ops.create_uvsphere(bulbs, u_segments=10, v_segments=6, radius=0.08, matrix=Matrix.Translation(bulb))
                light = bpy.data.lights.new('Chamber_Lamp', 'POINT')
                light.energy = 160.0
                light.color = (1.0, 0.74, 0.46)
                light.shadow_soft_size = 0.1
                lo = bpy.data.objects.new('Chamber_Lamp', light)
                lo.location = bulb
                self.cols['lights'].objects.link(lo)
        obj = bpy.data.objects.new('Chamber_Cables', curve)
        curve.materials.append(self.mats['cable'])
        self.cols['lights'].objects.link(obj)
        mesh_object('Chamber_Bulbs', bulbs, self.mats['bulb'], self.cols['lights'])

    def build_vent_duct(self):
        """Flexible ventilation duct hanging along the entrance haulage"""
        path = self.rail_path(RAIL_ROUTES[0])
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
            top, _, td = self.ray(base, Vector((0, 0, 1)), 8)
            if not wall or not top:
                continue
            q = base + side * max(0.0, wd - 0.7)
            q.z = min(top.z - 0.55, p.z + 3.0)
            pts.append((q, top))
        for (a, ta), (b, tb) in zip(pts, pts[1:]):
            if (b - a).length > 3.0:
                continue
            add_cylinder(duct, a, b, 0.3, 12, cap=False)
        for k, (q, top) in enumerate(pts):
            if k % 4 == 0:
                add_cylinder(hangers, q + Vector((0, 0, 0.3)), Vector((q.x, q.y, top.z)), 0.01, 4)
                add_cylinder(duct, q - (pts[min(k + 1, len(pts) - 1)][0] - q).normalized() * 0.05,
                             q + (pts[min(k + 1, len(pts) - 1)][0] - q).normalized() * 0.05, 0.33, 12)
        mesh_object('Vent_Duct', duct, self.mats['duct'], self.cols['props'])
        mesh_object('Vent_Hangers', hangers, self.mats['iron_dark'], self.cols['props'])

    def build_scaffold(self):
        """Timber scaffold + ladder from the main chamber floor up to the west ledge"""
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
                p = base + side * sx + d * sy
                add_box(wood, p + Vector((0, 0, h / 2)), (0.14, 0.14, h), rot)
        for level in (h * 0.5, h - 0.9):
            for k in range(-3, 4):
                add_box(wood, base + d * (k * 0.27) + Vector((0, 0, level)), (2.0, 0.24, 0.05), rot)
        # ladder
        lp = base - d * 1.2
        for sx in (-0.25, 0.25):
            add_box(wood, lp + side * sx + Vector((0, 0, h * 0.25 + 0.3)) + d * 0.35, (0.06, 0.06, h * 0.6 + 0.8), rot @ Matrix.Rotation(math.radians(-18), 3, 'X'))
        for k in range(int(h * 0.6 / 0.3)):
            add_box(wood, lp + Vector((0, 0, 0.3 + k * 0.3)) + d * (0.1 + k * 0.1), (0.5, 0.04, 0.04), rot)
        mesh_object('Scaffold_Ladder', wood, self.mats['wood'], self.cols['timber'])

    # --- validation -------------------------------------------------------------------
    def validate(self):
        """Every FiveM interaction point must stand in open cave: floor below, roof above, walls around"""
        points = [('ore %d' % (i + 1), x, y, z) for i, (x, y, z) in enumerate(ORE_SPOTS)]
        points += [('smelter', SMELTER[0], SMELTER[1], 43.15), ('shop ped', SHOP_PED[0], SHOP_PED[1], 43.26),
                   ('buyer ped', BUYER_PED[0], BUYER_PED[1], 43.17)]
        points += [('crack bench %d' % (i + 1), x, y, 43.1) for i, (x, y, _) in enumerate(CRACK_BENCHES)]
        points += [('jewel bench %d' % (i + 1), x, y, 43.1) for i, (x, y, _) in enumerate(JEWEL_BENCHES)]
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

    # --- world + render -------------------------------------------------------------
    def setup_world(self):
        scene = bpy.context.scene
        world = bpy.data.worlds.get('Cave_World') or bpy.data.worlds.new('Cave_World')
        world.use_nodes = True
        bg = world.node_tree.nodes.get('Background')
        bg.inputs['Color'].default_value = (0.45, 0.55, 0.7, 1)   # daylight leaking in at the mouth
        bg.inputs['Strength'].default_value = 0.6
        scene.world = world
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 40
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 4
        scene.cycles.light_sampling_threshold = 0.02
        scene.render.resolution_x = 1280
        scene.render.resolution_y = 720
        try:
            scene.view_settings.view_transform = 'AgX'
            scene.view_settings.look = 'AgX - Medium High Contrast'
        except TypeError:
            pass
        scene.view_settings.exposure = 1.0

    def camera(self, name, pos, target, lens=18.0, ortho=None):
        cam = bpy.data.cameras.new(name)
        cam.lens = lens
        cam.clip_start = 0.05
        cam.clip_end = 500
        if ortho:
            cam.type = 'ORTHO'
            cam.ortho_scale = ortho
        obj = bpy.data.objects.new(name, cam)
        obj.location = pos
        obj.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        self.cols['cameras'].objects.link(obj)
        return obj

    def eye(self, node, off=Vector(), height=1.7):
        c, f, r = node_center(node)
        p = Vector((c.x + off.x, c.y + off.y, f + 2.0))
        hit = self.floor_at(p)
        z = (hit.z if hit else f) + height
        return Vector((p.x, p.y, z))

    def build_cameras(self):
        cams = {}
        cams['01_entrance'] = self.camera('Cam_Entrance', self.eye('e1'), self.eye('e3', height=1.2), 16)
        cams['02_main_chamber'] = self.camera('Cam_Main', self.eye('main_e', Vector((2, 1, 0)), 2.4), self.eye('main_w', height=1.0), 14)
        cams['03_workshop'] = self.camera('Cam_Workshop', self.eye('shop', Vector((-6.0, -3.5, 0)), 2.1), self.ground(2919.0, 2653.5) + Vector((0, 0, 0.9)), 16)
        cams['04_crystal_chamber'] = self.camera('Cam_Crystal', self.eye('crystal', Vector((6.0, -1.0, 0)), 1.6), self.eye('crystal', Vector((-4.0, 1.5, 0)), 2.2), 14)
        cams['05_deep_shaft'] = self.camera('Cam_Shaft', self.eye('low2', Vector((0, 0, 0)), 1.8), self.eye('south1', height=0.8), 16)
        center = Vector((local(2872, 2669, 0).x, local(2872, 2669, 0).y, 60))
        cams['06_overview'] = self.camera('Cam_Overview', center, center - Vector((0, 0, 1)), ortho=178)
        self.cams = cams

    def cutaway(self):
        """Roof-less copy of the shell for the top-down overview"""
        obj = self.shell.copy()
        obj.data = self.shell.data.copy()
        obj.name = 'Cave_Cutaway'
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.2], context='FACES')
        bm.to_mesh(obj.data)
        bm.free()
        self.cols['shell'].objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
        return obj

    def render(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        scene = bpy.context.scene
        res = (scene.render.resolution_x, scene.render.resolution_y)
        cut = self.cutaway()
        for name, cam in self.cams.items():
            overview = name.endswith('overview')
            self.shell.hide_render = overview
            cut.hide_render = not overview
            scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.4 if overview else 0.6
            scene.render.film_transparent = overview
            scene.camera = cam
            scene.render.resolution_x, scene.render.resolution_y = (res[1], res[1]) if overview else res
            scene.render.filepath = os.path.join(out_dir, name + '.png')
            print(f'[cave] rendering {name}...')
            bpy.ops.render.render(write_still=True)
        self.shell.hide_render = False
        cut.hide_render = True
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.film_transparent = False

    def build(self):
        self.reset_scene()
        self.make_materials()
        self.build_shell()
        self.build_supports()
        self.build_lamps()
        self.build_floodlights()
        self.build_rails()
        self.build_ores()
        self.build_crystal_chamber()
        self.build_rubble()
        self.build_speleothems()
        self.build_chamber_lamps()
        self.build_vent_duct()
        self.build_scaffold()
        self.build_workshop()
        for kind, bm in list(self.crystal_bms.items()):
            if bm.is_valid and len(bm.verts):
                mesh_object('Workshop_Gems_' + kind, bm, self.mats['crystal_' + kind], self.cols['workshop'])
        self.setup_world()
        self.build_cameras()
        self.validate()


def parse_args():
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    elif argv and argv[0].endswith('.py'):
        argv = argv[1:]
    else:
        argv = []
    opts = {'render': None, 'save': None}
    i = 0
    while i < len(argv):
        if argv[i] in ('--render', '--save') and i + 1 < len(argv):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts


def main():
    opts = parse_args()
    cave = Cave()
    cave.build()
    if opts['save']:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(opts['save']))
        print('[cave] saved', opts['save'])
    if opts['render']:
        cave.render(opts['render'])
    print('[cave] done')


if __name__ == '__main__':
    main()
