# Dokumentation Hausmodell

Stand: 12.10.2026

## Überblick

Das Projekt bildet ein Einfamilienhaus aus der Zeit um 1950 als 3D-Modell nach: Erdgeschoss, Obergeschoss und Dach, innen mit Wänden, Türen, Treppen und Einbauten. Aus dem Modell sind Druckdaten für ein stapelbares Modell entstanden, bei dem sich Dach und Obergeschoss abheben lassen.

Das Haus misst außen 11,98 × 9,41 m, die Außenwände sind 0,38 m stark.

## Blender-Dateien

Alle Dateien wurden mit Blender 5.2.2 LTS erstellt.

| Datei | Inhalt | Wofür |
|---|---|---|
| `haus.blend` | Haus mit Umgebung: Straße, Zaun, Bäume, Nachbarhäuser, Hügel | Außenansichten und Kameraflüge |
| `haus_light.blend` | Haus ohne Umgebung | Grundlage für das Druckset mit Terrasse |
| `haus_light_ohne_terrasse.blend` | Haus ohne Umgebung, Terrasse, Terrassenstufe und Kelleraußentreppe | Grundlage für das aktuelle Druckset |
| `haus_eg.blend` | nur das Erdgeschoss, ohne Decke | Blick in die Räume |
| `haus_og.blend` | nur das Obergeschoss, ohne Decke | Blick in die Räume |

`haus.blend` enthält vier Szenen: `Scene` für Außenansichten sowie `Drohnenflug`, `Drohnenflug_2` und `Rundflug` für die Kamerafahrten. `Drohnenflug_2` ist der neueste Flug: einmal ums Haus, durch die Terrassentür, durch beide Geschosse und zum Südfenster wieder hinaus (54 Sekunden).

Das Haus ist in allen fünf Dateien auf demselben Stand. Wer etwas am Haus ändert, sollte die Änderung in allen fünf Dateien nachziehen.

## Aufbau des Modells

### Außen

- Putz hell-blaugrau, Faschen und Gesims grau, Dach mit roten Ziegeln
- Fenster ohne Sprossen; acht Fenster haben ein festes Unterlicht von 30 cm
- Haustür basaltgrau (RAL 7012) mit Glasstreifen, Sandsteingewände

### Erdgeschoss

- Windfang mit Tür zur Diele, von dort die Kellertreppe
- Wohnen und Essen durch einen Sturz verbunden
- Durchreiche zwischen Küche und Essen (76 × 62,5 cm, Brüstung 1,00 m)
- Treppe ins Obergeschoss, unten und oben gewendelt

### Obergeschoss

- Zimmer 15, 16, 17 und 19; Zimmer 17 hat Türen zum Flur und zu Zimmer 16
- Raumspartreppe aus Holz zum Dachboden, darunter Stauraum
- Einbauschrank mit Waschtischnische in Zimmer 17
- Wandschränke in Zimmer 15 und 16

### Farben innen

| Bereich | Farbe |
|---|---|
| Flur, Treppenhaus, Diele | `#FFD39B` |
| Zimmer und Windfang | `#CAE1FF` |
| Zimmer 16 | `#CAFF70` |
| Boden Obergeschoss | `#FFA54F` |
| Boden Erdgeschoss | `#8B7355` |
| Innentüren und Zargen | `#F3EFE2` (Altweiß) |

Die Farben erscheinen nur mit der Farbdarstellung „Standard“ so wie angegeben. Für Außenansichten ist „AgX“ eingestellt.

## Maße und Koordinaten

- Einheit ist Meter. X zeigt nach Osten, Y nach Norden, Z nach oben.
- Höhen der Fußböden: Keller −2,35 · Erdgeschoss 0,00 · Obergeschoss 3,00 · Dachgeschoss 6,00
- Das Gelände liegt bei −0,60.

## 3D-Druck

Das Modell besteht aus drei Teilen, die übereinander gesteckt werden: Erdgeschoss, Obergeschoss und Dach. Stifte mit 3 mm Durchmesser an den Ecken halten die Teile in Position.

| Ordner | Maßstab | Drucker | Stand |
|---|---|---|---|
| `3D/Bambu_Lab_P1S_ohne_Terrasse/` | 1:60 | Bambu Lab P1S | aktuell |
| `3D/Bambu_Lab_P1S_ohne_Terrasse_1-90/` | 1:90 | Bambu Lab P1S | 67 % des Sets 1:60, Wände verstärkt (mind. 1,2 mm), Stifte Ø 2,6 mm, Löcher Ø 3,0 mm; STL und Druckanleitung, noch nicht gesliced |
| `3D/Bambu_Lab_P1S/` | 1:60 | Bambu Lab P1S | mit Terrasse, Dach und Sockel noch massiv |
| `3D/Bambu_Lab_A2L/` | 1:50 | Bambu Lab A2L | Altstand vom 10.10.2026 |

Jeder Ordner enthält die drei Teile als STL, eine Blender-Datei mit den Druckteilen und eine Druckanleitung als PDF. `Haus_M1-50_A2L.stl` im Hauptordner gehört zum Altstand.

### Aktuelles Druckset

Im Ordner `3D/Bambu_Lab_P1S_ohne_Terrasse/` liegt zusätzlich `Haus_M1-60_P1S_Projekt.3mf`. Die Datei lässt sich direkt in Bambu Studio öffnen: Sie enthält alle drei Teile auf je einer Druckplatte, fertig eingestellt und gesliced.

| Teil | Größe | Druckzeit | Material |
|---|---|---|---|
| Erdgeschoss | 201 × 177 × 60 mm | 8 h 55 min | 294 g |
| Obergeschoss | 201 × 160 × 48 mm | 8 h 56 min | 275 g |
| Dach | 209 × 174 × 81 mm | 9 h 37 min | 251 g |
| Zusammen | Höhe ca. 19 cm | ca. 27,5 h | ca. 820 g |

Einstellungen der Projektdatei:

- Düse 0,4 mm, Schichthöhe 0,16 mm, 3 Wände
- Füllung 15 % Gyroid
- Baumstützen nur auf der Druckplatte, beim Erdgeschoss ausgeschaltet
- kein Brim, Druckplatte Textured PEI
- Material Bambu PLA Basic

Dach und Sockel des Erdgeschosses sind bei diesem Set hohl, das spart Material und Druckzeit. Die Stützen sind beim Erdgeschoss ausgeschaltet, weil der Slicer sonst den hohlen Sockel füllt.

Weitere Hinweise zum Drucken und Zusammenstecken stehen in der Druckanleitung im jeweiligen Ordner.

## Bekannte Einschränkungen

- Das Bild im README stammt vom 04.10.2026 und zeigt noch die alte Haustür.
- Das Druckset mit Terrasse hat keine Projektdatei für Bambu Studio.
- Die Wandschränke im Obergeschoss sind im Text der Druckanleitungen nicht erwähnt.
