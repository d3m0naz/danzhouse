"""Prüft die Druckteile eines Sets: Topologie, Wandstärke, Stifte und Löcher.

Aufruf aus dem Hauptordner des Repos, z. B.:
    python3 3D/pruefe_druckteile.py 3D/Bambu_Lab_P1S_ohne_Terrasse_1-90/*.stl
    python3 3D/pruefe_druckteile.py 3D/Bambu_Lab_P1S_ohne_Terrasse/Haus_M1-60_*.stl

Die Stiftmitten werden aus den Teilen selbst bestimmt: vier kleine Inseln an
der höchsten Stelle eines Teils sind Stifte. An denselben Mitten wird in den
anderen Teilen von unten nach Löchern gesucht.

Benötigt: numpy, trimesh, rtree (getestet mit Python 3.14).
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh

warnings.filterwarnings("ignore")


def topologie(m):
    _, n = np.unique(m.edges_sorted, axis=0, return_counts=True)
    return (f"wasserdicht {'ja' if m.is_watertight else 'nein'}, offene Kanten {int((n == 1).sum())}, "
            f"nicht-mannigfaltige Kanten {int((n > 2).sum())}, Körper {len(m.split(only_watertight=False))}, "
            f"Volumen {m.volume:.0f} mm³")


def wandstaerke(m):
    """Strahl von jeder Fläche nach innen; zählt nur Treffer auf eine zurückblickende Fläche."""
    c = m.triangles_center - m.face_normals * 0.01
    locs, ri, ti = m.ray.intersects_location(c, -m.face_normals, multiple_hits=False)
    d = np.full(len(m.faces), np.nan)
    ok = (m.face_normals[ti] * -m.face_normals[ri]).sum(1) > 0.7
    d[ri[ok]] = np.linalg.norm(locs[ok] - c[ri[ok]], axis=1) + 0.01
    a, v = m.area_faces, ~np.isnan(d)
    tot = a[v].sum()
    anteil = lambda t: 100 * a[v & (d < t)].sum() / tot
    return (f"gemessen {100 * tot / a.sum():.0f} % der Fläche; unter 1,0 mm {anteil(1.0):.2f} %, "
            f"unter 1,2 mm {anteil(1.2):.2f} %, unter 1,6 mm {anteil(1.6):.2f} %; "
            f"1. Perzentil {np.percentile(d[v], 1):.2f} mm")


def stiftmitten(m):
    """Vier kleine Inseln an der höchsten Stelle -> Mitten, sonst None."""
    top = m.vertices[m.vertices[:, 2] > m.bounds[1][2] - 0.05]
    inseln = []
    for p in top:
        for g in inseln:
            if np.hypot(*(p[:2] - g[0][:2])) < 5:
                g.append(p)
                break
        else:
            inseln.append([p])
    mitten = []
    for g in inseln:
        g = np.array(g)
        lo, hi = g[:, :2].min(0), g[:, :2].max(0)
        if (hi - lo).max() < 5:
            mitten.append((lo + hi) / 2)
    if len(mitten) != 4:
        return None
    # grobe Mitte aus dem Deckel nachschärfen: Schwerpunkt der Treffer auf dem Stiftmantel
    z = m.bounds[1][2] - 1.0
    for i, (cx, cy) in enumerate(mitten):
        for _ in range(3):
            pts = [strahl(m, [cx, cy, z], [np.cos(w), np.sin(w), 0.0]) for w in np.linspace(0, 2 * np.pi, 36, endpoint=False)]
            pts = np.array([p[np.argmin(np.hypot(p[:, 0] - cx, p[:, 1] - cy))][:2] for p in pts if len(p)])
            cx, cy = pts.mean(0)
        mitten[i] = (cx, cy)
    return np.array(mitten)


def strahl(m, o, d):
    locs, _, _ = m.ray.intersects_location(np.array([o]), np.array([d]), multiple_hits=True)
    return np.asarray(locs).reshape(-1, 3)


def radial(m, cx, cy, z, n=24):
    """erster und zweiter Treffer waagerechter Strahlen aus (cx, cy, z)"""
    r1, r2 = [], []
    for w in np.linspace(0, 2 * np.pi, n, endpoint=False):
        locs = strahl(m, [cx, cy, z], [np.cos(w), np.sin(w), 0.0])
        r = np.sort(np.hypot(locs[:, 0] - cx, locs[:, 1] - cy))
        r = r[r > 1e-3]
        r1.append(r[0] if len(r) else np.inf)
        r2.append(r[1] if len(r) > 1 else np.inf)
    return np.array(r1), np.array(r2)


def stifte(m, mitten):
    for cx, cy in mitten:
        oben = strahl(m, [cx, cy, m.bounds[1][2] + 10], [0, 0, -1.0])[:, 2].max()
        daneben = [strahl(m, [cx + dx, cy + dy, m.bounds[1][2] + 10], [0, 0, -1.0])
                   for dx, dy in [(3, 0), (-3, 0), (0, 3), (0, -3)]]
        krone = max(h[:, 2].max() for h in daneben if len(h))
        r1, _ = radial(m, cx, cy, oben - 1.0)
        print(f"    Stift ({cx:+.2f}, {cy:+.2f}): Ø {2 * r1.min():.2f}–{2 * r1.max():.2f} mm, "
              f"steht {oben - krone:.2f} mm über")


def loecher(m, mitten):
    for cx, cy in mitten:
        hits = strahl(m, [cx, cy, m.bounds[0][2] - 5], [0, 0, 1.0])
        decke = hits[:, 2].min() - m.bounds[0][2] if len(hits) else np.inf
        if decke < 0.5:
            continue  # kein Loch an dieser Stelle
        r1, r2 = radial(m, cx, cy, m.bounds[0][2] + min(1.0, decke / 2))
        print(f"    Loch  ({cx:+.2f}, {cy:+.2f}): Ø {2 * r1.min():.2f}–{2 * r1.max():.2f} mm, "
              f"{decke:.2f} mm tief, Wand ums Loch mind. {(r2 - r1).min():.2f} mm")


if __name__ == "__main__":
    teile = {Path(f).name: trimesh.load(f, force="mesh") for f in sys.argv[1:]}
    alle_mitten = [mt for mt in map(stiftmitten, teile.values()) if mt is not None]
    for name, m in teile.items():
        print(name)
        print("  Topologie:  ", topologie(m))
        print("  Wandstärke: ", wandstaerke(m))
        mt = stiftmitten(m)
        if mt is not None:
            stifte(m, mt)
        if alle_mitten:
            loecher(m, alle_mitten[0])
