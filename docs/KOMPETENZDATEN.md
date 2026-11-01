# Kompetenzerwartungen: Datenbestand, Import und Export

Die App enthält die **927 Kompetenzerwartungen aller zehn Fächer der
Primarstufe in Nordrhein-Westfalen**. Quelle ist der amtliche Sammelband
*Lehrplan für die Primarstufe in Nordrhein-Westfalen* (RdErl. d. MSB v.
01.07.2021, Heft 2012), abrufbar über den
[Lehrplannavigator](https://www.schulentwicklung.nrw.de/lehrplaene/lehrplannavigator-grundschule/).

| Fach | Erwartungen | Bereiche | Progressionspaare | „u. a.“ |
| --- | --: | --: | --: | --: |
| Deutsch | 117 | 4 | 52 | 20 |
| Englisch | 40 | 6 | 0 | 19 |
| Kunst | 60 | 7 | 60 | 4 |
| Mathematik | 136 | 9 | 66 | 27 |
| Musik | 46 | 3 | 38 | 27 |
| Praktische Philosophie | 91 | 5 | 68 | 15 |
| Evangelische Religionslehre | 93 | 6 | 64 | 14 |
| Katholische Religionslehre | 122 | 6 | 88 | 19 |
| Sachunterricht | 98 | 6 | 74 | 25 |
| Sport | 124 | 9 | 84 | 24 |
| **Summe** | **927** | **61** | **594** | **194** |

Die Dateien liegen in `lehrplan/`, eine je Fach, dazu `faecher.json` mit
Fachnamen, Bereichskürzeln und Quelle. Das Format ist das aus
[JSON-IMPORT.md](../JSON-IMPORT.md).

## Einlesen

```bash
# alle zehn Fächer (idempotent – ein zweiter Lauf ändert nichts)
docker compose exec app python manage.py kompetenzen_importieren

# nur ein Fach, vorher prüfen
docker compose exec app python manage.py kompetenzen_importieren --fach sport --vorschau
```

## Export und Import in der App

**Kompetenzen** im Benutzermenü zeigt das Nachschlagewerk, gegliedert wie im
Lehrplan nach Bereich und Schwerpunkt. Über den Filter wird die Auswahl
eingeengt; die drei Schaltflächen laden **genau diese Auswahl** herunter:

* **Als Tabelle (XLSX)** – zum Arbeiten in der Fachkonferenz,
* **Als CSV** – für Tabellenprogramme ohne XLSX,
* **Als JSON** – die maschinenlesbare Fassung, identisch zum Importformat.

Alle drei enthalten die Spalte **Schulische Festlegung**. Das ist die einzige
Spalte, die der Schule gehört: Wo der Lehrplan „u. a.“ sagt, legt die Schule
mindestens einen weiteren verbindlichen Inhalt fest (SPEC.md §7.3).

Der **Import** (nur Administration) geht in zwei Schritten und in zwei
Betriebsarten:

| Betriebsart | schreibt | lässt unberührt |
| --- | --- | --- |
| Lehrplandaten (amtlich) | alle Lehrplanspalten | schulische Festlegungen |
| nur schulische Festlegungen | `Schulische Festlegung` | alle Lehrplanspalten |

Erst **Datei prüfen**, dann **Geprüfte Daten übernehmen**. Findet die Prüfung
einen Fehler, wird nichts geschrieben – Lehrplandaten sind amtlich und sollen
nie halb importiert sein. Gelesen werden JSON, XLSX und CSV; die
Spaltenüberschriften sind die des Exports.

Der übliche Weg für eine Schulleitung: Fach filtern → XLSX herunterladen →
Spalte „Schulische Festlegung“ in der Fachkonferenz ausfüllen → hochladen,
Betriebsart **nur schulische Festlegungen** → prüfen → übernehmen.

## Wie die Daten aus dem PDF gelesen wurden

Der Sammelband setzt die Kompetenzerwartungen als zweispaltige Tabellen:
links „am Ende der Schuleingangsphase“, rechts „am Ende der Klasse 4“. Gilt
eine Erwartung für beide, steht sie in einer **über beide Spalten verbundenen
Zeile** – im Datensatz ist das die Stufe `D` („durchgängig“).

Diese Verbindung ist im PDF an den Zellrahmen ablesbar: fehlt in einer
Tabellenzeile der Rahmen in der Mitte, ist die Zeile verbunden. Zusätzlich
sitzt der Aufzählungspunkt der rechten Spalte immer auf derselben Position.
Aus beiden Signalen zusammen ergibt sich die Stufe eindeutig.

Drei Fächer weichen in der Form ab und wurden entsprechend gelesen:

* **Englisch** hat keine Tabellen, weil es erst in Klasse 3 beginnt – alle
  Erwartungen gelten „am Ende der Klasse 4“ (Stufe `K`). Die Schwerpunkte
  stehen dort in Kapitälchen.
* **Kunst** und **Musik** haben keine Schwerpunkte unterhalb der Bereiche; der
  Schwerpunkt trägt deshalb den Bereichsnamen.
* **Mathematik** hat neben den vier inhaltsbezogenen Bereichen die fünf
  prozessbezogenen Kompetenzbereiche (Problemlösen, Modellieren,
  Kommunizieren, Argumentieren, Darstellen). Sie sind als eigene Bereiche
  geführt.

Eine Stelle musste zusammengesetzt werden: der Englisch-Schwerpunkt
**Grammatik** hat im Sammelband keine Aufzählung, sondern einen Satz und
darunter eine Strichliste der verbindlichen Formen. Daraus wurde eine
Kompetenzerwartung mit der Liste als Klammerzusatz (`EN-SM4.01K`).

### Zwei unabhängige Gegenproben

**Vollständigkeit.** Jede Kompetenzerwartung beginnt im Sammelband mit einem
Aufzählungszeichen. Zählt man die Aufzählungszeichen der
Kompetenzerwartungs-Kapitel aller zehn Fächer, kommen genau so viele heraus,
wie eingelesen wurden – mit der einen Ausnahme des Englisch-Schwerpunkts
Grammatik, der im PDF kein Aufzählungszeichen hat:

| Fach | Zeichen im PDF | eingelesen |
| --- | --: | --: |
| Deutsch | 117 | 117 |
| Englisch | 39 | 40 (Grammatik, siehe oben) |
| Kunst | 60 | 60 |
| Mathematik | 136 | 136 |
| Musik | 46 | 46 |
| Praktische Philosophie | 91 | 91 |
| Evangelische Religionslehre | 93 | 93 |
| Katholische Religionslehre | 122 | 122 |
| Sachunterricht | 98 | 98 |
| Sport | 124 | 124 |

**Richtigkeit.** Für Deutsch gab es bereits einen geprüften Datensatz aus der
Arbeitsmappe der Schule. Der Leser reproduziert dessen 117 Erwartungen mit
identischem Wortlaut, Bereich, Schwerpunkt, Klammerzusatz und
Progressionspartner. Die neun Abweichungen stehen unten – acht davon in genau
den Feldern, die der alte Datensatz selbst als ungeprüft markiert hatte.

## Kennungen

Die Kennung ist der Verweis, unter dem eine Kompetenzerwartung in Einträgen,
Verlinkungen, Exporten und in den Schnappschüssen beschlossener Fassungen
steht. Aufbau: Bereichskürzel + Schwerpunkt-Nummer + `.` + laufende Nummer +
Stufe, zum Beispiel `SZ1.03S`.

Für die neun später aufgenommenen Fächer steht ein Fachkürzel davor, damit
sich die Kennungen nicht überschneiden: `SU-DG1.01S`, `MA-ZO2.03D`,
`SP-SW1.01D`. **Deutsch behält seine Kennungen ohne Vorsatz**, weil der
Arbeitsplan Deutsch und die Arbeitsmappe darauf verweisen.

## Was gegenüber dem früheren Deutsch-Datensatz berichtigt wurde

Der frühere Datensatz (`kompetenzerwartungen_lp2021.json`) stammte aus der
Arbeitsmappe der Schule. Dort war bei **61 von 117** Erwartungen die Stufe
rekonstruiert und als „Stufe prüfen“ markiert. Am Sammelband geprüft, ergaben
sich zehn Berichtigungen:

| Kennung | vorher | nachher | Fundstelle |
| --- | --- | --- | --- |
| `SZ3.08K` | Klasse 4 | durchgängig | S. 21, verbundene Zeile |
| `SC2.05K` | Klasse 4 | durchgängig | S. 22, verbundene Zeile |
| `LE2.04K` | Klasse 4 | durchgängig | S. 24, verbundene Zeile |
| `LE2.05K` | Klasse 4 | durchgängig | S. 24, verbundene Zeile |
| `SP2.01S` | Schuleingangsphase | durchgängig | S. 27, verbundene Zeile |
| `SP2.04K` | Klasse 4 | durchgängig | S. 28, verbundene Zeile |
| `SP3.03K` | Klasse 4 | durchgängig | S. 29, verbundene Zeile |
| `SP2.09D` | durchgängig | Klasse 4 | S. 28, nur rechte Spalte |
| `LE4.01K` | Wortlaut mit Komma | Wortlaut mit „und“ | S. 26 |
| `SC2.07D` | Klammerzusatz „digitalen“ | kein Klammerzusatz | S. 22 |

Zum letzten Punkt: „(digitalen) Veröffentlichung/Präsentation“ ist ein Einschub
mitten im Satz und nennt keinen verbindlichen Inhalt. Ein Klammerzusatz steht
hinter dem Begriff, den er aufzählt. Auf `uaWeitererInhalt` wirkt sich das nicht
aus; die Erwartung war und bleibt ohne „u. a.“.

**Die Kennungen wurden dabei nicht umbenannt**, auch wenn der Stufenbuchstabe
nun nicht mehr zur Stufe passt. Eine beschlossene Fassung ist unveränderlich
(SPEC.md §2.4); eine Umbenennung würde die Verweise in ihren Schnappschüssen
ins Leere zeigen lassen. Maßgeblich ist das Feld **Stufe**, das die App
überall ausschreibt („durchgängig“, „Ende der Klasse 4“); der Buchstabe in der
Kennung ist historisch. Alle 117 Deutsch-Kennungen gelten unverändert weiter,
`stufePruefen` ist überall `false`.

## Neue Lehrplandaten einspielen

Erlässt das Land einen neuen Lehrplan, kommt er über die Betriebsart
**Lehrplandaten** herein – als JSON im Format aus JSON-IMPORT.md oder als
Tabelle mit denselben Spalten. Die schulischen Festlegungen bleiben dabei
erhalten. Kennungen, die es nicht mehr gibt, werden **nicht** gelöscht: Was
einmal beschlossen wurde, bleibt nachvollziehbar. Veraltete Erwartungen räumt
die Administration bewusst in der Verwaltung weg.
