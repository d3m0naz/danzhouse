"""Verstärkt im Druckset 1:60 die Raumspartreppe (OG) und die Traufkästen (Dach).

Beides kommt als zusätzlicher, überlappender Körper zum Teil – so sind die
1:60-Teile ohnehin aufgebaut, der Slicer vereinigt die Körper. Die vorhandene
Geometrie bleibt unverändert.

- OG: Material in der Treppe, das dünner als 1,2 mm ist, wächst um R_TREPPE pro
  Seite. Nur im Treppenraum und unterhalb der Wandkrone, auf der das Dach sitzt.
- Dach: Der hohle Traufkasten (Boden 0,34 mm, 0,45 mm über der Platte) wird an
  beiden Traufen ausgefüllt und bis auf die Druckplatte geführt; dadurch sind
  auch seine offenen Enden an den Dachecken geschlossen.

Eingabe sind die Teile vor der Verstärkung (Stand von Commit a937eba). Aufruf
aus dem Hauptordner des Repos:

    mkdir -p /tmp/alt
    git show a937eba:3D/Bambu_Lab_P1S_ohne_Terrasse/Haus_M1-60_2_OG.stl > /tmp/alt/Haus_M1-60_2_OG.stl
    git show a937eba:3D/Bambu_Lab_P1S_ohne_Terrasse/Haus_M1-60_3_Dach.stl > /tmp/alt/Haus_M1-60_3_Dach.stl
    git show a937eba:3D/Bambu_Lab_P1S_ohne_Terrasse/Haus_M1-60_Druckteile.blend > /tmp/alt/Haus_M1-60_Druckteile.blend

    # 1. Verstärkungen berechnen, neue STL schreiben (Blender reduziert die Treppe)
    python3 3D/Bambu_Lab_P1S_ohne_Terrasse/verstaerke_1-60.py /tmp/alt 3D/Bambu_Lab_P1S_ohne_Terrasse
    # 2. Verstärkungen in die Blender-Datei übernehmen
    blender -b /tmp/alt/Haus_M1-60_Druckteile.blend --python 3D/Bambu_Lab_P1S_ohne_Terrasse/verstaerke_1-60.py \\
        -- /tmp/alt 3D/Bambu_Lab_P1S_ohne_Terrasse

Schritt 1 benötigt numpy, scipy, scikit-image, trimesh, rtree (getestet mit
Python 3.14) und `blender` im Pfad.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

PITCH = 0.1
R_TREPPE = 0.55                                       # 0,2 mm -> 1,3 mm; 0,68 mm -> 1,78 mm
TREPPE = ((-47.95, 23.5, 0.0), (-34.55, 60.0, 44.99))  # Treppenraum; z bis knapp unter die Wandkrone (45,0)
DUENN = 1.2
ZUSATZ = {"Haus_M1-60_2_OG": "Verstaerkung_OG.stl", "Haus_M1-60_3_Dach": "Verstaerkung_Dach.stl"}

# Blender: ebene Bereiche verlustfrei zusammenfassen, dann reduzieren (Abweichung < 0,02 mm)
REDUZIEREN = """
import bpy, math, sys
src, dst = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.stl_import(filepath=src)
o = bpy.context.selected_objects[0]; bpy.context.view_layer.objects.active = o
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(3), delimit={"NORMAL"})
bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
bpy.ops.object.mode_set(mode="OBJECT")
m = o.modifiers.new("d", "DECIMATE"); m.decimate_type = "COLLAPSE"; m.ratio = 40000 / len(o.data.polygons)
bpy.ops.object.modifier_apply(modifier="d")
bpy.ops.wm.stl_export(filepath=dst, export_selected_objects=True)
"""


def voxelize(mesh, lo, hi):
    """Belegung im Kasten lo..hi per Strahl-Parität entlang z, Körper für Körper."""
    import numpy as np
    n = np.ceil((hi - lo) / PITCH).astype(int)
    occ = np.zeros(n, dtype=bool)
    xs = lo[0] + (np.arange(n[0]) + 0.5) * PITCH + 1e-4
    ys = lo[1] + (np.arange(n[1]) + 0.5) * PITCH + 1.3e-4
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    origins = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, lo[2] - 1.0)])
    dirs = np.tile([0.0, 0.0, 1.0], (len(origins), 1))
    for body in mesh.split(only_watertight=False):
        (bx0, by0, _), (bx1, by1, _) = body.bounds
        if bx1 < lo[0] or bx0 > hi[0] or by1 < lo[1] or by0 > hi[1]:
            continue
        locs, ri, _ = body.ray.intersects_location(origins, dirs, multiple_hits=True)
        if len(locs) == 0:
            continue
        locs = np.asarray(locs).reshape(-1, 3)
        even = np.bincount(ri, minlength=len(origins)) % 2 == 0
        locs, ri = locs[even[ri]], ri[even[ri]]
        flip = np.zeros((len(origins), n[2] + 1), dtype=np.uint8)
        k0 = np.ceil((locs[:, 2] - lo[2]) / PITCH - 0.5).astype(int)
        np.bitwise_xor.at(flip, (ri, np.clip(k0, 0, n[2])), 1)
        occ |= (np.cumsum(flip, axis=1)[:, :n[2]] % 2).astype(bool).reshape(n)
    return occ


def treppe(mesh):
    import numpy as np
    import trimesh
    from scipy import ndimage
    from skimage import measure

    lo, hi = np.array(TREPPE[0]), np.array(TREPPE[1])
    glo, ghi = lo - 1.0, hi + 1.0
    occ = voxelize(mesh, glo, ghi)
    # dünnes Material: die größte Innendistanz in der Umgebung bleibt unter DUENN/2
    inner = ndimage.distance_transform_edt(occ, sampling=PITCH)
    size = int(round(DUENN / PITCH)) | 1
    duenn = occ & (ndimage.maximum_filter(inner, size=size) < DUENN / 2)
    g = (R_TREPPE - ndimage.distance_transform_edt(~duenn, sampling=PITCH)).astype(np.float32)
    # auf den Treppenraum begrenzen (ebene Schnitte)
    for k in range(3):
        shape = [1, 1, 1]
        shape[k] = -1
        ck = (glo[k] + (np.arange(g.shape[k]) + 0.5) * PITCH).reshape(shape)
        g = np.minimum(g, np.minimum(ck - lo[k], hi[k] - ck).astype(np.float32))
    print(f"Treppe: dünnes Material {duenn.sum() * PITCH ** 3:.1f} mm³")
    v, f, _, _ = measure.marching_cubes(g, level=0.0, spacing=(PITCH,) * 3)
    voll = trimesh.Trimesh(v + glo + 0.5 * PITCH, f, process=True)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "voll.stl", Path(tmp) / "reduziert.stl"
        voll.export(src)
        subprocess.run(["blender", "-b", "--factory-startup", "--python-expr", REDUZIEREN, "--", src, dst],
                       check=True, capture_output=True)
        shell = trimesh.load(dst, force="mesh")
    shell.fix_normals()
    return [shell]


def traufen():
    """Füllkörper je Traufe: Hohlraum zu, Unterseite auf die Druckplatte."""
    import numpy as np
    import trimesh

    # Profil (y, z) der Südtraufe, aus dem Querschnitt bei x = 0 gemessen; die Schräge
    # ist die Unterseite der Dachhaut
    profil = [(-84.75, 0.0), (-78.42, 0.0), (-78.42, 5.34), (-84.24, 0.79), (-84.75, 0.79)]
    x0, x1 = -104.0, 104.0   # Traufboden und Stirnbrett enden bei x = ±104,0; der Hohlraum ist dort offen
    koerper = []
    for s in (1, -1):      # Süd, Nord (gespiegelt)
        # konvexe Hülle des Prismas; sie schließt über der Schräge einen kleinen Keil
        # ein, der in der Dachhaut liegt, also ohnehin Material ist
        ecken = [(x, y * s, z) for x in (x0, x1) for y, z in profil]
        koerper.append(trimesh.convex.convex_hull(np.array(ecken)))
    return koerper


def stl_schreiben(alt, quelle, ziel):
    import trimesh
    mesh = trimesh.load(Path(alt) / f"{quelle}.stl", force="mesh", process=False)   # bleibt unverändert
    extra = treppe(trimesh.load(Path(alt) / f"{quelle}.stl", force="mesh")) if quelle.endswith("OG") else traufen()
    for e in extra:
        print(f"  Zusatzkörper: {len(e.faces)} Dreiecke, wasserdicht {e.is_watertight}, Volumen {e.volume:.1f} mm³, "
              f"x {e.bounds[0][0]:.2f}..{e.bounds[1][0]:.2f} y {e.bounds[0][1]:.2f}..{e.bounds[1][1]:.2f} "
              f"z {e.bounds[0][2]:.2f}..{e.bounds[1][2]:.2f}")
    trimesh.util.concatenate([mesh] + extra).export(Path(ziel) / f"{quelle}.stl")
    trimesh.util.concatenate(extra).export(Path(alt) / ZUSATZ[quelle])   # für Schritt 2


def blend_uebernehmen(alt, ziel):
    """In Blender: Zusatzkörper in die Druckteile einfügen und die Datei speichern."""
    import bpy
    for name, datei in ZUSATZ.items():
        teil = bpy.data.objects[name]
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.wm.stl_import(filepath=str(Path(alt) / datei))
        neu = bpy.context.selected_objects[0]
        neu.matrix_world = teil.matrix_world        # STL-Koordinaten = lokale Koordinaten des Teils
        neu.data.materials.append(teil.data.materials[0])
        teil.select_set(True)
        bpy.context.view_layer.objects.active = teil
        bpy.ops.object.join()
        print(f"{name}: {len(teil.data.vertices)} Ecken nach dem Einfügen")
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(ziel) / "Haus_M1-60_Druckteile.blend"))


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
    except ImportError:
        alt, ziel = sys.argv[1:3]
        for quelle in ZUSATZ:
            stl_schreiben(alt, quelle, ziel)
    else:
        blend_uebernehmen(*sys.argv[sys.argv.index("--") + 1:][:2])
