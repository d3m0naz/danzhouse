"""Erzeugt die Druckanleitung (PDF, A4, 4 Seiten) für ein Druckset.

Maße, Druckzeiten und Material kommen aus den STL-Dateien und der geslicten
Projektdatei des Sets, die Bilder rendert Blender aus den STL-Dateien.

Aufruf aus dem Hauptordner des Repos:
    python3 3D/druckanleitung.py 1-60
    python3 3D/druckanleitung.py 1-90

Benötigt: reportlab, pillow, trimesh (getestet mit Python 3.14), `blender` im
Pfad und die Schrift Arial (macOS).
"""
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import trimesh
from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

HIER = Path(__file__).resolve().parent

SETS = {
    "1-60": {
        "ordner": HIER / "Bambu_Lab_P1S_ohne_Terrasse",
        "kuerzel": "M1-60",
        "massstab": "1:60",
        "stift_hoehe": 3.0,      # Stifte stehen so weit über die Wandkrone
        "einleitung2": "Treppe und Traufkästen sind seit dem 19.10.2026 verstärkt – mehr dazu auf Seite 4.",
        "teile": [
            ("1  Erdgeschoss", "1_EG",
             "Ab Geländeoberkante mit Eingangspodest (ohne Terrasse, Terrassenstufe und Kellerabgang). Nach oben "
             "offen: Küche, Wohn-/Esszimmer, Bad, Kamin, Treppen. Sockel hohl und unten offen. 4 Zentrierstifte "
             "(Ø 3 mm) auf der Mauerkrone."),
            ("2  Obergeschoss", "2_OG",
             "Mit Fußboden und Treppenöffnung, Zimmer 13–19, Bad mit Abstellraum, Raumspar-Bodentreppe, "
             "Einbauschrank mit Waschtischnische. Unten 4 Löcher (Ø 3,4 mm), oben 4 Stifte (Ø 3 mm)."),
            ("3  Dach", "3_Dach",
             "Satteldach 38° mit Giebeln, Giebelfenstern, Schornsteinen, Rinnen und Ortgang. Innen hohl und unten "
             "offen, mit 3 Querstegen und einem Firststeg ausgesteift. Unten 4 Löcher (Ø 3,4 mm)."),
        ],
        "einstellungen": [
            ("Düse", "0,4 mm", "Standard; feine Details sind ca. 0,7–0,8 mm stark"),
            ("Schichthöhe", "0,16 mm (feiner: 0,12 mm)", "saubere Fensterrahmen, Gesimse, Ortgang"),
            ("Wände", "3 Perimeter", "stabile Innenwände (1,2–4 mm Modellstärke)"),
            ("Wandgenerator", "Arachne", "druckt auch Stege unter 2 Düsenbreiten (Zargen, Rahmen)"),
            ("Füllung", "15 %, Gyroid", "nur dickere Stellen: Mauerecken, Schornsteine, Sockelstege"),
            ("Stützen", "Tree (auto), nur auf Druckplatte; EG ohne", "EG: nur kurze Brücken, hohler Sockel bleibt frei"),
            ("Überhangwinkel", "35–40°", "Dachuntersicht 38° braucht unten Stützen"),
            ("Brim", "aus (EG: optional 3 mm)", "große, plane Auflageflächen"),
            ("Druckplatte", "Textured PEI Plate", "im Projekt voreingestellt – bei anderer Platte umstellen"),
            ("Material", "PLA / PLA Matte", "geringer Verzug, gut nachzubearbeiten"),
            ("Gehäuse", "Fronttür offen oder Deckel ab", "PLA im geschlossenen P1S wird zu warm"),
            ("Loch-Kompensation", "XY +0,05 bis +0,10 mm", "falls die Zentrierstifte zu stramm sitzen"),
        ],
        "pruefung": "Jedes Teil besteht aus mehreren geschlossenen Körpern, die sich überlappen; Bambu Studio "
                    "vereinigt sie beim Slicen ohne Reparatur. Wandstärken, Stifte und Löcher sind mit "
                    "<font name='Menlo'>3D/pruefe_druckteile.py</font> geprüft. Beim EG meldet Bambu Studio frei "
                    "hängende Bereiche – das ist der hohle Sockel, der ohne Stützen gedruckt wird.",
        "schritte": [
            ("Stützen entfernen", "besonders in Fensternischen, unter Treppen und an der Traufe."),
            ("Stifte prüfen", "die 4 Stifte (Ø 3 mm, 3 mm hoch) auf EG und OG sauber entgraten."),
            ("Probe stecken", "OG auf EG setzen. Klemmt es, Löcher mit 3,5-mm-Bohrer von Hand nachbohren."),
            ("Dach aufsetzen", "die Giebel stehen über der West- und Ostwand."),
            ("Nicht kleben", "die Teile bleiben abnehmbar, sonst sieht man die Grundrisse nicht mehr."),
        ],
        "liste_titel": "Weggelassen und verstärkt",
        "liste": [
            ("Glasscheiben", "bei 1:60 nur 0,07 mm – Fenster sind offene Nischen mit Rahmen"),
            ("Türblätter", "0,7-mm-Platten wären zu bruchempfindlich – Zargen zeigen die Öffnungen"),
            ("Geländer & Handläufe", "Stäbe unter 0,5 mm sind nicht druckbar"),
            ("Keller & Lichtschächte", "liegen unterhalb der Geländeoberkante"),
            ("Terrasse & Kellerabgang", "in dieser Variante entfernt – EG und OG sind gleich breit"),
            ("Sockel & Dachboden", "hohl und unten offen: Bodenplatte 1,2 mm auf Stegraster; Dachhaut innen 2 mm"),
            ("Treppe verstärkt", "Raumspar-Bodentreppe im OG: Wangen und Stufen jetzt mind. 1,2 mm statt 0,2–0,7 mm"),
            ("Traufkästen verstärkt", "ausgefüllt und bis auf die Druckplatte geführt, Enden an den Dachecken geschlossen"),
        ],
        "tipps_extra": [
            ("Dach-Optik", "Dach in Terrakotta drucken – „Fuzzy Skin“ (nur äußere Wand) gibt der Dachfläche eine "
                           "raue Ziegel-Anmutung."),
        ],
    },
    "1-90": {
        "ordner": HIER / "Bambu_Lab_P1S_ohne_Terrasse_1-90",
        "kuerzel": "M1-90",
        "massstab": "1:90",
        "stift_hoehe": 2.07,
        "einleitung2": "Diese Fassung ist das Druckset 1:60 (ohne Terrasse), auf 67 % verkleinert. Damit es im "
                       "kleineren Maßstab stabil bleibt, sind Wände, Böden, Stifte und Löcher verstärkt – mehr "
                       "dazu auf Seite 4.",
        "teile": [
            ("1  Erdgeschoss", "1_EG",
             "Ab Geländeoberkante mit Eingangspodest (ohne Terrasse, Terrassenstufe und Kellerabgang). Nach oben "
             "offen: Küche, Wohn-/Esszimmer, Bad, Kamin, Treppen. Sockel hohl und unten offen. 4 Zentrierstifte "
             "(Ø 2,6 mm) auf der Mauerkrone."),
            ("2  Obergeschoss", "2_OG",
             "Mit Fußboden und Treppenöffnung, Zimmer 13–19, Bad mit Abstellraum, Raumspar-Bodentreppe, "
             "Einbauschrank mit Waschtischnische. Unten 4 Löcher (Ø 3,0 mm), oben 4 Stifte (Ø 2,6 mm)."),
            ("3  Dach", "3_Dach",
             "Satteldach 38° mit Giebeln, Giebelfenstern, Schornsteinen, Rinnen und Ortgang. Innen hohl und "
             "unten offen, mit Querstegen und einem Firststeg ausgesteift. Unten 4 Löcher (Ø 3,0 mm)."),
        ],
        "einstellungen": [
            ("Düse", "0,4 mm", "alle Wände sind mind. 1,2 mm stark (3 Bahnen)"),
            ("Schichthöhe", "0,12 mm", "saubere Fensterrahmen, Gesimse, Ortgang im kleinen Maßstab"),
            ("Wände", "3 Perimeter", "Wände bis ca. 1,2 mm werden voll aus Bahnen gedruckt"),
            ("Wandgenerator", "Arachne", "gleicht Stärken zwischen den Düsenbreiten aus"),
            ("Füllung", "15 %, Gyroid", "nur dickere Stellen: Schornsteine, Mauerecken, Stege"),
            ("Stützen", "Tree (auto), nur auf Druckplatte; EG ohne", "EG: nur kurze Brücken, hohler Sockel bleibt frei"),
            ("Überhangwinkel", "35–40°", "Dachuntersicht 38° braucht unten Stützen"),
            ("Brim", "aus (EG: optional 3 mm)", "große, plane Auflageflächen"),
            ("Druckplatte", "Textured PEI Plate", "bei anderer Platte in Bambu Studio umstellen"),
            ("Material", "PLA / PLA Matte", "geringer Verzug, gut nachzubearbeiten"),
            ("Gehäuse", "Fronttür offen oder Deckel ab", "PLA im geschlossenen P1S wird zu warm"),
            ("Loch-Kompensation", "XY +0,05 bis +0,10 mm", "falls die Zentrierstifte zu stramm sitzen"),
        ],
        "pruefung": "Jedes Teil ist <b>ein geschlossener, wasserdichter Körper</b>: keine offenen oder mehrfach "
                    "genutzten Kanten, keine losen Teile. Die Teile werden mit <font name='Menlo'>erzeuge_1-90.py</font> "
                    "aus dem Druckset 1:60 erzeugt und lassen sich in Bambu Studio ohne Reparatur slicen. Beim EG "
                    "meldet Bambu Studio frei hängende Bereiche – das ist der hohle Sockel, der ohne Stützen gedruckt wird.",
        "schritte": [
            ("Stützen entfernen", "besonders in Fensternischen, unter Treppen und an der Traufe."),
            ("Stifte prüfen", "die 4 Stifte (Ø 2,6 mm, 2 mm hoch) auf EG und OG sauber entgraten."),
            ("Probe stecken", "OG auf EG setzen. Klemmt es, Löcher mit 3-mm-Bohrer von Hand nachbohren."),
            ("Dach aufsetzen", "die Giebel stehen über der West- und Ostwand."),
            ("Nicht kleben", "die Teile bleiben abnehmbar, sonst sieht man die Grundrisse nicht mehr."),
        ],
        "liste_titel": "Unterschiede zur Fassung 1:60",
        "liste": [
            ("Maßstab", "67 % der Fassung 1:60, entspricht etwa 1:90"),
            ("Wände verstärkt", "jede Fläche um 0,6 mm nach außen versetzt – Wände und Böden 1,2 mm stärker, überall mind. 1,2 mm"),
            ("Innenmaße", "Räume, Fenster- und Türöffnungen je Seite 0,6 mm kleiner; außen 1,2 mm größer"),
            ("Kanten", "Außenkanten durch den Versatz leicht gerundet"),
            ("Stifte & Löcher", "Stifte Ø 2,6 mm statt verkleinert 2,0 mm; Löcher Ø 3,0 mm, 3,4 mm tief"),
            ("Dachrinnen", "massiv statt hohl"),
            ("Wie bei 1:60", "Glasscheiben, Türblätter, Geländer, Keller, Terrasse und Kellerabgang weggelassen"),
        ],
        "tipps_extra": [
            ("Dach-Optik", "Dach in Terrakotta drucken. „Fuzzy Skin“ (nur äußere Wand) gibt eine raue Ziegel-Anmutung – "
                           "im kleinen Maßstab nur schwach einstellen."),
        ],
    },
}

RENDER = r"""
import bpy, math, sys
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
out, eg, og, dach, eg_top, og_top, s = args[0], args[1], args[2], args[3], float(args[4]), float(args[5]), float(args[6])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.scale_length = 0.001
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1600, 1100
sc.view_settings.view_transform = "Standard"
def mat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = 0.6
    return m
weiss, terra, boden = mat("w", (0.82, 0.82, 0.83)), mat("t", (0.80, 0.42, 0.33)), mat("b", (0.32, 0.32, 0.34))
teile = {}
for key, fn, m in [("EG", eg, weiss), ("OG", og, weiss), ("Dach", dach, terra)]:
    bpy.ops.wm.stl_import(filepath=fn)
    o = bpy.context.selected_objects[0]; o.data.materials.append(m); teile[key] = o
bpy.ops.mesh.primitive_plane_add(size=5000); bpy.context.object.data.materials.append(boden)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.07, 0.10, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.2
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.5; sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(-35)); sc.collection.objects.link(sun)
fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA")); fill.data.energy = 4e6 * s * s; fill.data.size = 600 * s
fill.location = (-500 * s, -400 * s, 600 * s); fill.rotation_euler = (math.radians(45), 0, math.radians(-50)); sc.collection.objects.link(fill)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); cam.data.lens = 70; cam.data.clip_end = 20000
sc.collection.objects.link(cam); sc.camera = cam
def shot(name, sichtbar, zs, ziel, dist, elev=32, azim=-50):
    for k, o in teile.items():
        o.hide_render = k not in sichtbar; o.location = (0, 0, zs.get(k, 0))
    t = Vector([v * s for v in ziel])
    d = Vector((math.cos(math.radians(elev)) * math.cos(math.radians(azim)),
                math.cos(math.radians(elev)) * math.sin(math.radians(azim)), math.sin(math.radians(elev))))
    cam.location = t + d * dist * s
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{out}/{name}.png"; bpy.ops.render.render(write_still=True)
shot("explosion", {"EG", "OG", "Dach"}, {"OG": eg_top + 22 * s, "Dach": og_top + 50 * s}, (0, 0, 70), 780)
shot("eg", {"EG"}, {}, (0, 3, 14), 400, elev=42)
shot("og", {"OG"}, {}, (0, 0, 12), 400, elev=42)
shot("dach", {"Dach"}, {}, (0, 0, 18), 500, elev=28)
shot("zusammen", {"EG", "OG", "Dach"}, {"OG": eg_top, "Dach": og_top}, (0, 0, 55), 600, elev=22, azim=-40)
"""

DARK, CARD_DARK, ACCENT = HexColor("#313b46"), HexColor("#3d4855"), HexColor("#b9533d")
TEXT, MUTED, SAND, GREEN = HexColor("#2f3a45"), HexColor("#66727e"), HexColor("#f2ede6"), HexColor("#3f7f52")
W, H = A4
M = 54


def druckwerte(projekt):
    """Druckzeit (s), Gewicht (g), Länge (m) je Teil aus der geslicten Projektdatei."""
    s = zipfile.ZipFile(projekt).read("Metadata/slice_info.config").decode()
    werte = {}
    for pl in re.findall(r"<plate>.*?</plate>", s, re.S):
        name = re.search(r'<object identify_id="\d+" name="([^"]+)"', pl).group(1)
        zeit = int(re.search(r'key="prediction" value="(\d+)"', pl).group(1))
        m, g = re.search(r'used_m="([\d.]+)" used_g="([\d.]+)"', pl).groups()
        werte[name] = (zeit, float(g), float(m))
    return werte


def hm(sek):
    m = round(sek / 60)
    return f"{m // 60} h {m % 60:02d} min"


def zahl(x, nachkomma=0):
    return f"{x:.{nachkomma}f}".replace(".", ",")


def gramm(g):
    return f"{int(g + 0.5)}\u00a0g"   # kaufmännisch gerundet (276,5 -> 277), Einheit nicht abtrennen


def erzeuge(set_id):
    cfg = SETS[set_id]
    ordner, k = cfg["ordner"], cfg["kuerzel"]
    stl = {t: ordner / f"Haus_{k}_{t}.stl" for t in ("1_EG", "2_OG", "3_Dach")}
    groesse = {t: trimesh.load(p, force="mesh").extents for t, p in stl.items()}
    werte = druckwerte(ordner / f"Haus_{k}_P1S_Projekt.3mf")
    eg_top = groesse["1_EG"][2] - cfg["stift_hoehe"]
    og_top = eg_top + groesse["2_OG"][2] - cfg["stift_hoehe"]
    hoehe_cm = (og_top + groesse["3_Dach"][2]) / 10
    rand = int((256 - max(max(g[0], g[1]) for g in groesse.values())) / 2 // 5 * 5)
    skal = groesse["1_EG"][0] / 136.0          # Kamera: 1:90 ist der Bezug

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["blender", "-b", "--factory-startup", "--python-expr", RENDER, "--", tmp,
                        stl["1_EG"], stl["2_OG"], stl["3_Dach"], str(eg_top), str(og_top), str(skal)],
                       check=True, capture_output=True)
        for n in ("explosion", "eg", "og", "dach", "zusammen"):
            im = Image.open(f"{tmp}/{n}.png").convert("RGB")
            im.thumbnail((1200, 1200))
            im.save(f"{tmp}/{n}.jpg", quality=85)
        pdf = ordner / f"Druckanleitung_Haus_{k}_P1S.pdf"
        seiten(cfg, pdf, tmp, groesse, werte, hoehe_cm, rand)
    print(f"{pdf.name}: Höhe {hoehe_cm:.1f} cm, Rand {rand} mm")
    for name, (z, g, m) in werte.items():
        print(f"  {name}: {hm(z)}, {gramm(g)}, {m:.1f} m")


def seiten(cfg, pdf, bilder, groesse, werte, hoehe_cm, rand):
    pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Menlo", "/System/Library/Fonts/Menlo.ttc", subfontIndex=0))
    pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold")
    body = ParagraphStyle("body", fontName="Arial", fontSize=9.5, leading=13, textColor=TEXT)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11.5)
    muted = ParagraphStyle("muted", parent=small, textColor=MUTED, fontSize=8, leading=10.5)
    ms, k = cfg["massstab"], cfg["kuerzel"]

    def para(c, text, x, y_top, width, style=body):
        p = Paragraph(text, style)
        _, h = p.wrap(width, 1000)
        p.drawOn(c, x, y_top - h)
        return h

    def footer(c, n):
        c.setStrokeColor(ACCENT); c.setLineWidth(1); c.line(M, 40, W - M, 40)
        c.setFont("Arial", 8); c.setFillColor(MUTED)
        c.drawString(M, 28, f"Hausmodell M {ms}  ·  Bambu Lab P1S"); c.drawRightString(W - M, 28, f"Seite {n}")

    def heading(c, num, text, y):
        c.setFillColor(ACCENT); c.circle(M + 10, y + 5, 10, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("Arial-Bold", 10); c.drawCentredString(M + 10, y + 1.5, str(num))
        c.setFillColor(TEXT); c.setFont("Arial-Bold", 16); c.drawString(M + 30, y, text)

    def image(c, name, x, y, w, h):
        img = ImageReader(f"{bilder}/{name}.jpg")
        iw, ih = img.getSize()
        s = max(w / iw, h / ih)
        c.saveState(); p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0)
        c.drawImage(img, x + (w - iw * s) / 2, y + (h - ih * s) / 2, iw * s, ih * s); c.restoreState()

    def mm(t):
        g = groesse[t]
        return f"{g[0]:.0f} × {g[1]:.0f} × {g[2]:.0f} mm"

    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setTitle(f"Druckanleitung Hausmodell – M {ms} – Bambu Lab P1S")
    c.setAuthor("Hausmodell")

    # Seite 1
    c.setFillColor(DARK); c.rect(0, H - 340, W, 340, stroke=0, fill=1)
    c.setFillColor(ACCENT); c.rect(0, H - 352, W, 12, stroke=0, fill=1)
    c.setFillColor(HexColor("#dfe4e9")); c.setFont("Arial", 10); c.drawString(M, H - 70, "DRUCKANLEITUNG  ·  3D-MODELL")
    c.setFillColor(white); c.setFont("Arial-Bold", 34); c.drawString(M, H - 115, "Einfamilienhaus")
    c.setFont("Arial", 16); c.drawString(M, H - 142, f"Stapelbares Hausmodell im Maßstab {ms}")
    c.setFillColor(HexColor("#b8c1ca")); c.setFont("Arial", 10); c.drawString(M, H - 162, "Baujahr ca. 1950")
    cw = (W - 2 * M - 3 * 10) / 4
    for i, (v, l) in enumerate([("3", "Druckteile"), (ms, "Maßstab"), (f"≈ {hoehe_cm:.0f} cm", "Gesamthöhe"),
                                ("P1S", "Bambu Lab")]):
        x = M + i * (cw + 10)
        c.setFillColor(CARD_DARK); c.roundRect(x, H - 290, cw, 92, 8, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("Arial-Bold", 20); c.drawString(x + 14, H - 238, v)
        c.setFillColor(HexColor("#b8c1ca")); c.setFont("Arial", 9); c.drawString(x + 14, H - 270, l)
    image(c, "explosion", M, H - 652, W - 2 * M, 300)
    y = H - 686
    c.setFillColor(TEXT); c.setFont("Arial-Bold", 12); c.drawString(M, y, "Abheben statt Aufschneiden")
    h = para(c, "Das Modell besteht aus drei übereinander gesteckten Teilen: <b>Erdgeschoss</b>, <b>Obergeschoss</b> "
                "und <b>Dach</b>. Hebt man ein Teil ab, sieht man den Grundriss des Geschosses darunter mit allen "
                "Innenwänden, Türöffnungen, Treppen und Einbauten. Zentrierstifte halten die Teile exakt übereinander.",
             M, y - 10, W - 2 * M)
    para(c, cfg["einleitung2"], M, y - 22 - h, W - 2 * M)
    footer(c, 1); c.showPage()

    # Seite 2
    heading(c, 1, "Die drei Druckteile", H - 80)
    ch, gap = 196, 16
    for i, ((titel, t, text), img) in enumerate(zip(cfg["teile"], ("eg", "og", "dach"))):
        top = H - 105 - i * (ch + gap)
        c.setFillColor(SAND); c.roundRect(M, top - ch, W - 2 * M, ch, 10, stroke=0, fill=1)
        image(c, img, M + 10, top - ch + 10, 230, ch - 20)
        tx, tw = M + 258, W - 2 * M - 272
        c.setFillColor(ACCENT); c.setFont("Arial-Bold", 15); c.drawString(tx, top - 34, titel)
        c.setFillColor(TEXT); c.setFont("Arial-Bold", 10); c.drawString(tx, top - 54, mm(t))
        c.setFillColor(MUTED); c.setFont("Menlo", 8); c.drawString(tx, top - 70, f"Haus_{k}_{t}.stl")
        para(c, text, tx, top - 82, tw, small)
    by = H - 105 - 3 * (ch + gap) - 4
    c.setFillColor(GREEN); c.roundRect(M, by - 34, W - 2 * M, 34, 6, stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Arial-Bold", 9.5)
    c.drawString(M + 16, by - 21, f"Jedes Teil passt einzeln in den Bauraum des P1S (256 × 256 × 256 mm), "
                                  f"mind. {rand} mm Rand ringsum.")
    footer(c, 2); c.showPage()

    # Seite 3
    heading(c, 2, "Einstellungen in Bambu Studio", H - 80)
    cols = [M + 8, M + 140, M + 300]
    y = H - 112
    c.setFillColor(SAND); c.rect(M, y - 8, W - 2 * M, 24, stroke=0, fill=1)
    c.setFillColor(TEXT); c.setFont("Arial-Bold", 9)
    for x, t in zip(cols, ("Einstellung", "Empfehlung", "Warum")):
        c.drawString(x, y, t)
    c.setStrokeColor(ACCENT); c.line(M, y - 8, W - M, y - 8)
    y -= 8
    for i, (a, b, w) in enumerate(cfg["einstellungen"]):
        zellen = [(Paragraph(a, small), cols[0], 128), (Paragraph(b, small), cols[1], 152),
                  (Paragraph(w, muted), cols[2], W - M - cols[2] - 6)]
        rh = max(p.wrap(cw_, 1000)[1] for p, _, cw_ in zellen) + 14
        if i % 2:
            c.setFillColor(HexColor("#faf7f2")); c.rect(M, y - rh, W - 2 * M, rh, stroke=0, fill=1)
        for p, x, cw_ in zellen:
            _, h = p.wrap(cw_, 1000)
            p.drawOn(c, x, y - 7 - h)
        y -= rh
    y -= 34
    heading(c, 3, "Farben nach Bauteil", y)
    y -= 24
    sw = (W - 2 * M - 24) / 3
    for i, (t, d, col) in enumerate([("EG + OG", "Weiß oder Hellgrau –\nwirkt wie Putz", "#e4e2dd"),
                                     ("Dach", "Terrakotta / Ziegelrot –\nwie die Tonziegel", "#b9533d"),
                                     ("Alternative", "Ganz in Hellgrau –\nklassisches\nArchitekturmodell", "#9aa3ab")]):
        x = M + i * (sw + 12)
        c.setFillColor(SAND); c.roundRect(x, y - 82, sw, 82, 10, stroke=0, fill=1)
        c.setFillColor(HexColor(col)); c.roundRect(x + 12, y - 70, 26, 58, 4, stroke=0, fill=1)
        c.setFillColor(TEXT); c.setFont("Arial-Bold", 10); c.drawString(x + 50, y - 26, t)
        c.setFont("Arial", 8.5); c.setFillColor(MUTED)
        for n, line in enumerate(d.split("\n")):
            c.drawString(x + 50, y - 42 - n * 11, line)
    y -= 120
    heading(c, 4, "Geprüfte Druckdaten", y)
    y -= 18
    p = Paragraph(cfg["pruefung"], body)
    _, h = p.wrap(W - 2 * M - 32, 1000)
    c.setFillColor(SAND); c.roundRect(M, y - h - 28, W - 2 * M, h + 28, 10, stroke=0, fill=1)
    p.drawOn(c, M + 16, y - 14 - h)
    footer(c, 3); c.showPage()

    # Seite 4
    heading(c, 5, "Zusammenbau", H - 80)
    image(c, "zusammen", M, H - 300, 250, 190)
    sx, y = M + 270, H - 118
    for i, (t, d) in enumerate(cfg["schritte"], 1):
        c.setFillColor(ACCENT); c.circle(sx + 8, y - 6, 8, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("Arial-Bold", 8); c.drawCentredString(sx + 8, y - 9, str(i))
        h = para(c, f"<b>{t}</b> – {d}", sx + 24, y, W - M - sx - 24, small)
        y -= max(h, 16) + 12
    y = H - 335
    heading(c, 6, cfg["liste_titel"], y)
    y -= 22
    for a, b in cfg["liste"]:
        c.setFillColor(MUTED); c.setFont("Arial", 9); c.drawString(M, y - 9, "–")
        para(c, f"<b>{a}</b>", M + 14, y, 120, small)
        h = para(c, b, M + 140, y, W - 2 * M - 140, ParagraphStyle("d", parent=small, textColor=MUTED))
        y -= max(h, 12) + 6
    y -= 22
    heading(c, 7, "Profi-Tipps", y)
    y -= 16
    teile = [("Dach", "3_Dach"), ("EG", "1_EG"), ("OG", "2_OG")]
    zeiten = [(n, werte[f"Haus_{k}_{t}.stl"]) for n, t in teile]
    summe = [sum(w[i] for _, w in zeiten) for i in range(3)]
    tipps = [
        ("Projektdatei", f"<font name='Menlo'>Haus_{k}_P1S_Projekt.3mf</font> enthält alle drei Teile auf je einer "
                         "Platte (Dach, EG, OG) mit den Einstellungen dieser Anleitung, fertig gesliced."),
        ("Druckzeit", "Laut Bambu Studio: " + ", ".join(f"{n} {hm(w[0])} / {gramm(w[1])}" for n, w in zeiten)
                      + f" – zusammen ca. {zahl(summe[0] / 3600, 0)} h und {gramm(summe[1])} PLA "
                        f"({zahl(summe[2], 0)}\u00a0m Filament)."),
        ("Reihenfolge", "Erst das OG drucken: es ist ein kleines Teil und zeigt schnell, ob Stifte und Löcher passen."),
    ] + cfg["tipps_extra"] + [
        ("Nachbearbeitung", "Fensternischen mit Cutter oder Nadelfeile säubern; Fassaden mit Acryl-Hellgrau-Blau "
                            "(#BCC4CE) und Faschen in Dunkelgrau bemalen."),
    ]
    for t, d in tipps:
        p = Paragraph(d, small)
        _, h = p.wrap(W - 2 * M - 150, 1000)
        bh = max(h + 16, 30)
        c.setFillColor(SAND); c.roundRect(M, y - bh, W - 2 * M, bh, 6, stroke=0, fill=1)
        c.setFillColor(ACCENT); c.rect(M, y - bh, 4, bh, stroke=0, fill=1)
        c.setFillColor(TEXT); c.setFont("Arial-Bold", 9.5); c.drawString(M + 18, y - 17, t)
        p.drawOn(c, M + 136, y - 8 - h)
        y -= bh + 6
    if y < 50:
        print(f"WARNUNG: Seite 4 läuft in die Fußzeile (y = {y:.0f})")
    footer(c, 4); c.showPage()
    c.save()


if __name__ == "__main__":
    erzeuge(sys.argv[1])
