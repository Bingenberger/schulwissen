# Prüfung vom 1. November 2026

Drei Fragen: Sind die bisherigen Arbeitspakete sauber umgesetzt? Sind alle
Kompetenzerwartungen der Grundschule NRW da? Und hält die App einer Prüfung aus
der Sicht einer Schulleitung und einer Lehrkraft stand?

## 1. Zustand der bisherigen Umsetzung

| Prüfung | Ergebnis |
| --- | --- |
| Testlauf `pytest` | 666 Tests grün (vorher 646; 20 neue) |
| `ruff check` / `ruff format --check` | ohne Befund, 176 Dateien formatiert |
| `manage.py check` | ohne Befund |
| `manage.py makemigrations --check` | keine fehlende Migration |
| Markdown-Verweise in README, SPEC, ROADMAP, docs | alle Ziele vorhanden |
| `TODO`/`FIXME` im Code | keine |
| Gestaltungsprüfung (25 Ansichten × 4 Breiten × hell/dunkel) | keine Befunde |
| Barrierefreiheit (axe, WCAG 2.1 A/AA) | keine Verstöße |
| Seitlicher Überlauf bei 390 px | nirgends |

Drei stillschweigend abgefangene Ausnahmen (`kern/prozesseditor.py`,
`kern/prozesslesen.py`) sind jeweils eng begrenzt und fachlich begründet
(ungültiger Graph, nicht relative URL, ungültige Dienst-E-Mail). Kein Befund.

Die Warnungen aus `manage.py check --deploy` (HSTS, SSL-Weiterleitung,
Cookie-Flags) stammen aus dem Entwicklungscontainer mit `SW_DEBUG=true`. Im
Betrieb setzt `schulwissen/einstellungen.py` diese Werte abhängig von `DEBUG`;
`DEPLOYMENT.md` beschreibt den Reverse Proxy. Kein Befund.

**Zwei echte Befunde, beide behoben:**

1. **Überschriften brachen lange Zusammensetzungen nicht um.**
   „Kompetenzerwartungen“ ist in einer `h1` breiter als ein 390 px schmaler
   Bildschirm und schob die ganze Seite zur Seite. Behoben durch
   `h1, h2, h3, h4 { overflow-wrap: anywhere; }` in
   `dateien/schulwissen.css` – das wirkt für alle Seiten, nicht nur die neuen.
2. **Die Abdeckungsmatrix sortierte die Bereiche nach einer fest verdrahteten
   Deutsch-Liste** (`{"SZ": 1, "SC": 2, "LE": 3, "SP": 4}`). Für jedes andere
   Fach fiel jeder Bereich auf denselben Rang, und weil die Schwerpunktnummern
   in jedem Bereich wieder bei 1 beginnen, standen die Bereiche durcheinander –
   bei Mathematik also „Zahlverständnis, Raumorientierung, Größenvorstellung,
   Daten …“ gemischt. Jetzt gilt die Reihenfolge, die am Fach hinterlegt ist.
   Dabei zeigte die Spalte außerdem nur das Kürzel; bei neun neuen Fächern mit
   Kürzeln wie `GF` oder `TA` ist das keine Information mehr – jetzt steht der
   Bereichsname darunter.

Der zweite Befund kam erst durch den neuen Abnahmetest
`test_arbeitsplan_fuer_ein_zweites_fach_anlegen` ans Licht. Er wäre im Betrieb
erst der ersten Fachkonferenz aufgefallen, die mit einem anderen Fach arbeitet.

## 2. Kompetenzerwartungen aller zehn Fächer

Aus dem amtlichen Sammelband sind **927 Kompetenzerwartungen in zehn Fächern**
eingelesen; Herkunft, Lesart und Kennungen stehen in
[KOMPETENZDATEN.md](KOMPETENZDATEN.md). Bisher waren es 117 in einem Fach.

Zwei Gegenproben stützen den Datenbestand:

* **Vollständigkeit.** Jede Kompetenzerwartung beginnt im Sammelband mit einem
  Aufzählungszeichen. Die Zahl der Aufzählungszeichen in den
  Kompetenzerwartungs-Kapiteln stimmt Fach für Fach mit der Zahl der
  eingelesenen Erwartungen überein – mit der einen dokumentierten Ausnahme des
  Englisch-Schwerpunkts Grammatik, der im PDF keines hat.
* **Richtigkeit.** Für Deutsch gab es bereits einen geprüften Datensatz. Der
  Leser reproduziert dessen 117 Erwartungen mit identischem Wortlaut, Bereich,
  Schwerpunkt, Klammerzusatz und Progressionspartner. Es blieben **zehn**
  Abweichungen: acht Stufen (sieben davon hatte der alte Datensatz selbst als
  „zu prüfen“ markiert), ein Wortlaut und ein Klammerzusatz. Alle zehn sind in
  [KOMPETENZDATEN.md](KOMPETENZDATEN.md) mit Fundstelle aufgeführt.

Die 61 Markierungen „Stufe prüfen“ sind damit abgearbeitet; der Datensatz trägt
keine mehr. Das Einlesen selbst ist wiederholbar: die Werkzeuge in
`werkzeuge/lehrplan/` erzeugen die elf Dateien aus dem PDF Byte für Byte neu.

Import und Export sind beidseitig: Was die App ausgibt, liest sie unverändert
wieder ein. Der Weg für eine Fachkonferenz ist **Fach filtern → XLSX
herunterladen → Spalte „Schulische Festlegung“ ausfüllen → hochladen, prüfen,
übernehmen**. Die Betriebsart trennt sauber, was wem gehört: Lehrplandaten sind
amtlich, die Festlegung gehört der Schule.

## 3. Aus Sicht einer Schulleitung

### Was trägt

* **Der Einstieg stimmt.** Die Startseite stellt eine Frage („Was suchst du?“)
  und bietet ein großes Suchfeld mit Beispielen. Darunter stehen die drei
  Nachschlagewege (Schulhandbuch nach Aufgaben, Formulare, Abläufe) – jetzt
  ergänzt um die Kompetenzerwartungen, die sonst nur im Benutzermenü standen.
* **Beschlusslage ist überall sichtbar.** Jeder Eintrag trägt oben ein
  Gültigkeitsbanner, die Beschlussliste ist chronologisch, die
  Beschlussvorlage lässt sich für die nächste Konferenz zusammenstellen.
  Beschlossene Fassungen sind unveränderlich – das ist im Modell erzwungen,
  nicht nur in der Oberfläche.
* **Zuständigkeiten und Abläufe** sind vorhanden und mit Personen besetzbar;
  Vertretung und Personalwechsel sind gedacht.
* **Die Auswertungen beantworten Leitungsfragen**: Abdeckungsmatrix mit Anteil
  je Schwerpunkt, Zeitbudget, Leistungsübersicht, Prüfliste.
* **Rechte sind streng.** Eine Lehrkraft bekommt auf den Kompetenzimport eine
  403-Antwort, nicht nur einen fehlenden Knopf.

### Was fehlt

1. **Ein zweites Fach startet bei null.** Ein Arbeitsplan für ein anderes Fach
   lässt sich anlegen – der Dokumenttyp „Arbeitsplan“ verlangt dabei ein Fach,
   und Kompetenzauswahl, Abdeckungsmatrix, Suche und Planung rechnen danach mit
   diesem Fach. Das ist geprüft (`test_arbeitsplan_fuer_ein_zweites_fach_anlegen`).
   Was fehlt, ist die **Gliederung**: `deutsch/gliederung.py` baut die Kapitel
   („2 Entscheidungen zum Unterricht“, „2.1 Unterrichtsvorhaben“,
   „2.4 Leistungsbewertung“) nur für `arbeitsplan_deutsch`. Eine
   Fachkonferenz Mathematik bekommt ein leeres Dokument und muss jedes Kapitel
   von Hand anlegen. Die Kapitel sind nicht deutschspezifisch – sie je Fach
   anzubieten wäre ein kleiner Schritt mit großer Wirkung.

2. **Die schulische Festlegung lässt sich einzeln nur in der
   Django-Verwaltung ändern.** Für „wir legen bei dieser einen Erwartung jetzt
   Fabeln fest“ ist der Weg über die Verwaltung ein Bruch. Der neue Import über
   die Tabelle deckt den Konferenzfall ab, der Einzelfall bleibt umständlich.
3. **Kein fachübergreifender Überblick über offene Festlegungen.** Die
   Prüfliste hängt an einem Dokument und zeigt nur dessen Fach. 194 Erwartungen
   mit „u. a.“ verteilen sich über alle zehn Fächer; die Kompetenzübersicht
   zählt sie jetzt je Fach, eine Gesamtliste gibt es nicht.

## 4. Aus Sicht einer Lehrkraft

### Was trägt

* **Suchen funktioniert wie erwartet.** „Zuhörstrategien“ findet 14
  Kompetenzerwartungen und zusätzlich ähnlich geschriebene Einträge; Treffer
  sind gruppiert, mit Pfad, markierten Suchwörtern und Status.
* **Einträge lesen ist ruhig.** Blöcke mit Sprungleiste, Kompetenzen im
  Klartext nach Bereich gruppiert, der Leistungsblock farblich abgesetzt,
  leere Felder ausgeblendet, Anhänge als Kacheln.
* **Die Kompetenzauswahl bleibt übersichtlich.** Im Arbeitsplan Deutsch werden
  trotz 927 Erwartungen im System nur die 117 des Fachs angeboten, in der
  Reihenfolge des Lehrplans. Kein Fach läuft in ein anderes über.
* **Auf dem iPad bedienbar.** Bei 768 px und 390 px kein seitliches Scrollen
  außer in den ausdrücklich gekennzeichneten Tabellen; Klickflächen groß genug.
* **Nachschlagen ist neu möglich.** „Kompetenzerwartungen des Lehrplans“ führt
  in ein Nachschlagewerk, das nach Bereich und Schwerpunkt gegliedert ist wie
  der gedruckte Lehrplan, mit Sprungliste über die Schwerpunkte.

### Was fehlt

4. **Die Liste eines Fachs ist lang.** Mathematik sind 136 Erwartungen auf
   einer Seite. Die Sprungliste hilft, ersetzt aber kein Zuklappen der
   Schwerpunkte und keine Merkliste.
5. **Kompetenzen sind nicht rückwärts verlinkt.** Zu einer Erwartung ist nicht
   zu sehen, in welchen Vorhaben sie vorkommt – obwohl die Abdeckungsmatrix
   genau diese Zahlen schon hat.
6. **Die eigene Planung kennt nur ein Dokument.** „Meine Planung“ arbeitet je
   Dokument, Schuljahr und Klasse. Wer in drei Fächern plant, hat drei Listen.
   Solange nur der Arbeitsplan Deutsch gepflegt ist, fällt das nicht auf;
   mit dem zweiten Fach (Punkt 1) wird es zur Frage.

## 5. Wie geprüft wurde

Nicht nur gelesen, sondern im Browser durchgespielt – angemeldet als
Schulleitung und als Lehrkraft, auf 1440, 1024, 768 und 390 px:

* Suche nach einem Wort aus einer Kompetenzerwartung,
* Fach wechseln, filtern, Sprungliste benutzen,
* XLSX herunterladen (die Datei kam an),
* Import als Lehrkraft aufrufen (403),
* Import als Administration prüfen und übernehmen,
* im Arbeitsplan Deutsch eine Kompetenz auswählen.

Dazu der wiederholbare Lauf `docs/gestaltung-pruefung.cjs` über 25 Ansichten
mit axe-Prüfung in hell und dunkel.

## 6. Optik

Die Gestaltung folgt dem Auftrag aus `DESIGN.md`: ein Grünton als Akzent,
warmes Grau, Status immer mit Text statt nur mit Farbe, Karten statt Rahmen,
Kennungen nur als kleine Schilder neben dem Klartext. Hell und dunkel sind über
Tokens gelöst und beide ohne Kontrastfehler. Die neuen Seiten verwenden
dieselben Bausteine; eigene Farben oder Abstände kamen nicht hinzu, nur eine
Sprungliste als Komponente.

Zwei kleine Berichtigungen aus dieser Prüfung:

* Die Suche zeigte „Stufe D“ statt „durchgängig“. Seit der Berichtigung der
  acht Deutsch-Stufen (KOMPETENZDATEN.md) ist der Buchstabe in der Kennung
  nicht mehr in jedem Fall der Stufenbuchstabe – im Klartext ist er eindeutig.
* In der Abdeckungsmatrix bleibt die schmale Spalte „Stufe“ beim Buchstaben,
  nennt den Klartext aber als `abbr`-Titel.

## 7. Empfehlung für das nächste Paket

In dieser Reihenfolge:

1. Gliederung je Fach beim Anlegen eines Arbeitsplans (Punkt 1) – damit zahlt
   sich der neue Datenbestand überhaupt erst aus. Die Abnahme aus PHASE4.md
   („Arbeitsplan Mathematik anlegen“) ist damit vollständig erfüllt.
2. Schulische Festlegung direkt in der Kompetenzübersicht bearbeiten (Punkt 2),
   mit demselben Schreibschutz wie die Einträge.
3. Rückverweise von der Kompetenzerwartung auf die Vorhaben (Punkt 5).
