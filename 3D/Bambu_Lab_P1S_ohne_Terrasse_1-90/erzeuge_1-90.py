"""Erzeugt das Druckset 1:90 aus dem Druckset 1:60 (ohne Terrasse).

Die drei Teile werden auf 67 % skaliert, jede Fläche wird um R nach außen
versetzt (Wände wachsen um 2R), dann werden Stifte und Löcher als exakte
Zylinder neu gebaut, damit sie weder vom Versatz zugehen noch treppig werden.

Aufruf aus dem Hauptordner des Repos:
    python3 3D/Bambu_Lab_P1S_ohne_Terrasse_1-90/erzeuge_1-90.py

Benötigt: numpy, scipy, scikit-image, trimesh, rtree, fast-simplification
(getestet mit Python 3.14).
"""
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "Bambu_Lab_P1S_ohne_Terrasse"

SCALE = 0.67                   # 1:60 -> ca. 1:90
PITCH = 0.25                   # Voxelgröße, mm
R = 0.6                        # Versatz nach außen pro Seite, mm
PIN_X, PIN_Y = 57.955, 50.417  # Mitten der Stifte und Löcher (±x, ±y), aus den Originalteilen gemessen
PIN_D, PIN_H = 2.6, 2.0        # Stift: Durchmesser und Höhe über der Wandkrone
HOLE_D, HOLE_DEPTH = 3.0, 3.5  # Loch: 0,2 mm Spiel pro Seite, tiefer als der Stift hoch ist
TARGET_FACES = 60000

PARTS = [  # Quelle, Ziel, Stifte oben, Löcher unten
    ("Haus_M1-60_1_EG.stl", "Haus_M1-90_1_EG.stl", True, False),
    ("Haus_M1-60_2_OG.stl", "Haus_M1-90_2_OG.stl", True, True),
    ("Haus_M1-60_3_Dach.stl", "Haus_M1-90_3_Dach.stl", False, True),
]


def voxelize(mesh):
    """Belegung per Strahl-Parität entlang z, Körper für Körper.

    Die Teile bestehen aus vielen überlappenden Körpern; Parität über alle auf
    einmal würde jede Überlappung aushöhlen.
    """
    pad = int(np.ceil((R + 2 * PITCH) / PITCH)) + 2
    lo, hi = mesh.bounds
    lo = lo - pad * PITCH
    nx, ny, nz = np.ceil((hi + pad * PITCH - lo) / PITCH).astype(int)
    occ = np.zeros((nx, ny, nz), dtype=bool)
    for body in mesh.split(only_watertight=False):
        (bx0, by0, _), (bx1, by1, _) = body.bounds
        i0, i1 = max(int((bx0 - lo[0]) / PITCH) - 1, 0), min(int((bx1 - lo[0]) / PITCH) + 2, nx)
        j0, j1 = max(int((by0 - lo[1]) / PITCH) - 1, 0), min(int((by1 - lo[1]) / PITCH) + 2, ny)
        xs = lo[0] + (np.arange(i0, i1) + 0.5) * PITCH + 1e-4
        ys = lo[1] + (np.arange(j0, j1) + 0.5) * PITCH + 1.3e-4
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        origins = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, lo[2] - 1.0)])
        dirs = np.tile([0.0, 0.0, 1.0], (len(origins), 1))
        locs, ray_idx, _ = body.ray.intersects_location(origins, dirs, multiple_hits=True)
        if len(locs) == 0:  # Körper dünner als das Raster
            continue
        locs = np.asarray(locs).reshape(-1, 3)
        # ungerade Trefferzahl: Kante gestreift oder Körper offen; Parität würde
        # die Spalte bis zum Rasterrand füllen, also Spalte auslassen
        even = np.bincount(ray_idx, minlength=len(origins)) % 2 == 0
        locs, ray_idx = locs[even[ray_idx]], ray_idx[even[ray_idx]]
        flip = np.zeros((gx.size, nz + 1), dtype=np.uint8)
        k0 = np.ceil((locs[:, 2] - lo[2]) / PITCH - 0.5).astype(int)  # erste Voxelmitte über dem Treffer
        np.bitwise_xor.at(flip, (ray_idx, np.clip(k0, 0, nz)), 1)
        inside = (np.cumsum(flip, axis=1)[:, :nz] % 2).astype(bool).reshape(i1 - i0, j1 - j0, nz)
        occ[i0:i1, j0:j1] |= inside
    return occ, lo + 0.5 * PITCH  # Belegung, Weltposition der Voxelmitte [0,0,0]


def build(src, dst, pins, holes):
    mesh = trimesh.load(src, force="mesh")
    mesh.apply_scale(SCALE)
    mesh.merge_vertices(digits_vertex=4)
    zmin_src, zmax_src = mesh.bounds[0][2], mesh.bounds[1][2]

    occ, (ox, oy, oz) = voxelize(mesh)

    # vorzeichenbehaftetes Feld, innen positiv: der Körper um R gewachsen
    g = (R - ndimage.distance_transform_edt(~occ, sampling=PITCH)).astype(np.float32)
    del occ
    # Lufttaschen füllen, die der Versatz eingeschlossen hat (z. B. Rinnen, schmale Schlitze)
    inside = g > 0
    g[ndimage.binary_fill_holes(inside) & ~inside] = PITCH
    del inside

    zbot = zmin_src - R              # Unterseite nach dem Versatz
    walltop = zmax_src - PIN_H + R   # Wandkrone unter den Stiften (Stifte sind die höchsten Punkte)

    def window(cx, cy, r):
        i0, i1 = int((cx - r - ox) / PITCH) - 1, int((cx + r - ox) / PITCH) + 2
        j0, j1 = int((cy - r - oy) / PITCH) - 1, int((cy + r - oy) / PITCH) + 2
        x = ox + np.arange(i0, i1) * PITCH
        y = oy + np.arange(j0, j1) * PITCH
        rxy = np.hypot(x[:, None] - cx, y[None, :] - cy)[:, :, None]
        z = (oz + np.arange(g.shape[2]) * PITCH)[None, None, :]
        return (slice(i0, i1), slice(j0, j1)), rxy, z

    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * PIN_X, sy * PIN_Y
            sl, rxy, z = window(cx, cy, 3.0)
            if pins:
                # mitgewachsenen Stift entfernen, alles bis zur Wandkrone behalten
                sub = np.minimum(g[sl], np.maximum(rxy - 2.4, walltop - z))
                pin = np.minimum(np.minimum(PIN_D / 2 - rxy, walltop + PIN_H - z), z - (walltop - 1.0))
                g[sl] = np.maximum(sub, pin)
            if holes:
                hole = np.minimum(np.minimum(HOLE_D / 2 - rxy, zbot + HOLE_DEPTH - z), z - (zbot - 1.0))
                g[sl] = np.minimum(g[sl], -hole)

    verts, faces, _, _ = measure.marching_cubes(g, level=0.0, spacing=(PITCH,) * 3)
    del g
    out = trimesh.Trimesh(verts + np.array([ox, oy, oz]), faces, process=True)
    if len(out.faces) > TARGET_FACES:
        v, f = fast_simplification.simplify(out.vertices, out.faces,
                                            target_reduction=1 - TARGET_FACES / len(out.faces))
        out = trimesh.Trimesh(v, f, process=True)
    # Splitter der Dezimierung entfernen (wenige Flächen, kein Volumen)
    out = trimesh.util.concatenate([p for p in out.split(only_watertight=False) if len(p.faces) > 50])
    out.merge_vertices()
    out.fix_normals()
    if out.volume < 0:
        out.invert()
    out.apply_translation([0, 0, -out.bounds[0][2]])  # auf die Druckplatte (z = 0)
    out.export(dst)
    size = out.bounds[1] - out.bounds[0]
    print(f"{dst.name}: {size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm, "
          f"{len(out.faces)} Dreiecke, wasserdicht: {out.is_watertight}")


if __name__ == "__main__":
    for src, dst, pins, holes in PARTS:
        build(SRC / src, HERE / dst, pins, holes)
