# Gestaltung der Schulwissen-Plattform – Auftrag für Claude Code

> **So startest du:** Lies diese Datei und `SPEC.md`. Verschaffe dir einen Überblick über alle vorhandenen Templates, Styles und Komponenten. Schlage mir im Plan-Modus vor, in welcher Reihenfolge du die Seiten überarbeitest, und zeige nach dem ersten Schritt (Design-Grundlagen + Startseite) Screenshots, bevor du weitermachst. Funktionen nicht verändern – es geht nur um Gestaltung, Struktur der Oberfläche und Bedienbarkeit.

---

## 1. Für wen wir gestalten

- Rund 24 Grundschullehrkräfte, **eher wenig digital-affin**. Sie haben sich beruflich für „was mit Menschen“ entschieden, nicht für „was mit Maschinen“.
- Bisherige Werkzeuge (Nextcloud, digitale Pinnwand, Word-Tabellen) wurden als umständlich erlebt. Die App muss sich vom ersten Klick an **leichter** anfühlen als das, was sie ersetzt – sonst wird sie nicht genutzt.
- Genutzt wird an Schul-PCs, privaten Laptops und vor allem am **iPad**, oft zwischendurch und unter Zeitdruck.

**Leitbild: so einfach wie Google.** Wer die App öffnet, sieht ein Suchfeld und findet in Sekunden die Absprache, die er sucht.

## 2. Gestaltungsprinzipien

1. **Ruhe vor Vollständigkeit.** Jede Seite hat eine Hauptaufgabe. Alles andere tritt zurück oder ist eine Ebene tiefer.
2. **Lesen zuerst, Bearbeiten auf Wunsch.** Standard ist der Lesemodus. Bearbeiten ist ein deutlicher, aber nicht dominanter Schritt.
3. **Klartext statt Technik.** Keine IDs, Statuscodes oder Datenbankbegriffe als Hauptinformation. Kompetenz-IDs, Kennungen (V-3-01) nur als kleine Badges neben dem Klartext.
4. **Gültigkeit sichtbar machen.** Bei jedem Inhalt ist auf einen Blick klar: Ist das beschlossen oder ein Entwurf? Seit wann gilt es?
5. **Große Ziele, wenig Präzisionsarbeit.** Finger auf dem iPad, nicht Mauszeiger.
6. **Konsistenz.** Gleiche Dinge sehen überall gleich aus (Status, Badges, Buttons, Karten).

## 3. Design-Grundlagen (Tokens)

Alle Werte als CSS Custom Properties in **einer** zentralen Datei (z. B. `static/css/tokens.css`). Keine Farb- oder Abstandswerte direkt in Templates.

### Farben
- **Akzentfarbe:** Grün `#7AB648` (aus den bisherigen Schulmaterialien) – [PLATZHALTER: mit mir bestätigen]. Für Text auf Weiß und für Buttons eine dunklere Variante ableiten, die WCAG AA (4,5 : 1) erfüllt, z. B. `#4F7F2A`.
- **Neutrale Töne:** warmes Grau statt reinem Schwarz/Grau; Text `#1F2328`-ähnlich, Sekundärtext deutlich heller, Hintergrund leicht getönt (z. B. `#F7F7F4`), Karten weiß.
- **Statusfarben** (immer mit Text/Icon, nie Farbe allein):
  - Idee: Grau
  - Entwurf: Gelb/Amber
  - Abgestimmt: Blau
  - Beschlossen: Grün
  - Archiviert: helles Grau, durchgestrichen nicht nötig
- **Abdeckung:** fehlt = Rot (gedeckt, nicht grell), nur berührt = Gelb, Schwerpunkt = Grün.
- **Leistungsblock:** eigene dezente Hintergrundfarbe (z. B. zartes Violett oder Blau), damit er in jedem Vorhaben sofort erkennbar ist.

### Typografie
- Systemschrift-Stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`) oder eine gut lesbare freie Schrift (z. B. Inter, Source Sans 3) **lokal eingebunden**, kein Google-Fonts-CDN.
- Grundgröße **mind. 17 px**, Zeilenhöhe ca. 1,55, Textbreite max. ~70 Zeichen im Lesemodus.
- Klare Hierarchie: Seitentitel, Abschnittstitel, Feldbeschriftung, Fließtext, Metainfo. Höchstens vier Größen im Einsatz.
- Feldbeschriftungen im Lesemodus als kleine, kräftige Überschriften über dem Inhalt (nicht links daneben – auf dem iPad zu eng).

### Abstände, Formen
- Abstandsskala in festen Stufen (4, 8, 12, 16, 24, 32, 48 px).
- Abgerundete Ecken einheitlich (z. B. 8 px Karten, 6 px Buttons/Felder).
- Schatten sparsam; Flächen lieber über Hintergrundton und Linien trennen.
- Klickflächen **mind. 44 × 44 px**.

### Icons
- Ein einheitliches, schlankes Icon-Set (z. B. Lucide oder Heroicons, lokal eingebunden). Icons immer mit Text, außer bei eindeutigen Standards (Suche, Schließen).

## 4. Grundlayout

- **Kopfzeile (alle Seiten):** links Name der App / Schullogo [PLATZHALTER], Mitte das **Suchfeld** (auf der Startseite ausgeblendet, weil dort groß), rechts Benutzer-Menü. Schlank, nicht höher als ~64 px.
- **Dokumentseiten:** links eine schmale, einklappbare **Gliederung** (Baum der Kapitel und Vorhaben), Mitte der Inhalt, rechts eine **Seitenleiste** mit Status, Beschluss, Rückverweisen („Wird verwendet in …“) und Kommentaren.
- **iPad hochkant / Handy:** Gliederung als ausklappbares Menü, rechte Seitenleiste wandert unter den Inhalt. Kein horizontales Scrollen, außer in breiten Tabellen (dort mit sichtbarem Hinweis).
- **Breadcrumb** über jedem Inhalt: „Arbeitsplan Deutsch › 2.1 Unterrichtsvorhaben › V-3-01“.

## 5. Seiten im Einzelnen

### 5.1 Startseite
- Viel Weißraum, oben App-Name und eine freundliche Zeile (z. B. „Was suchst du?“).
- **Großes Suchfeld** mittig, Fokus beim Laden, Platzhalter mit Beispiel („z. B. Lesezeit, Diktat, Märchen …“).
- Darunter maximal drei kompakte Bereiche als Karten: **Zuletzt beschlossen**, **Zuletzt angesehen**, **Meine offenen Entwürfe** (nur wenn vorhanden). Je höchstens 5 Einträge.
- Darunter schlicht die Liste der Dokumente (Arbeitsplan Deutsch, Konzepte, Protokolle) als große, klickbare Kacheln.

### 5.2 Suche
- **Autovervollständigung** als Dropdown direkt unter dem Feld, gruppiert mit kleinen Gruppenüberschriften (Arbeitspläne & Konzepte · Beschlüsse · Kompetenzen · Dateien), Tastatur (Pfeile, Enter, Esc) und Touch bedienbar.
- **Ergebnisseite:** Gruppen als Abschnitte mit Trefferzahl; je Treffer: Titel (fett), Pfad (klein, grau), Trefferausschnitt mit **markierten Suchwörtern**, Status-Badge rechts. Dateien mit Dateityp-Icon.
- Filter (Dokument, Status, Jahrgang, Fach) als dezente Chips oberhalb der Ergebnisse, nicht als Formular.
- Leerer Zustand: freundlicher Hinweis + Vorschläge („Versuche ein anderes Wort“ / häufige Suchen).

### 5.3 Eintrag lesen (Grundlagenkapitel, Ritual, Vorhaben)
- Oben ein **Gültigkeitsbanner**:
  - Beschlossen: grün, „Gilt seit Beschluss der Fachkonferenz Deutsch vom 12.03.2027“ mit Link zum Beschluss.
  - Entwurf: amber, „Entwurf – noch nicht beschlossen“; wenn es eine beschlossene Fassung gibt, Umschalter „Beschlossene Fassung / Entwurf / Unterschiede“.
- Titel groß, Kennung als Badge, darunter Kurzbeschreibung.
- Inhalte in Blöcken mit Abschnittsüberschriften: **Überblick · Kompetenzen · Zeit · Unterricht · Leistung · Sonstiges**. Leere optionale Felder im Lesemodus **ausblenden**.
- **Kompetenzen:** Liste im Klartext, gruppiert nach Bereich, mit kleinem ID-Badge und farbigem Punkt für den Bereich; „Schwerpunkt“ und „berührt“ als zwei klar getrennte Listen.
- **Rituale:** die Ausprägung Jg. 1–4 als vier nebeneinanderliegende Spalten (auf schmalen Bildschirmen als Reiter/Akkordeon); der eigene Jahrgang der Person, falls bekannt, hervorgehoben.
- **Leistungsblock** farbig abgesetzt mit Icon, damit sofort klar ist: So wird das bewertet. Klassenarbeit als deutliches Badge.
- Anhänge als Kacheln mit Icon, Name, Größe; Nextcloud-Dateien mit kleinem Nextcloud-Hinweis.
- Button **„Bearbeiten“** oben rechts, nur für Berechtigte.

### 5.4 Eintrag bearbeiten
- Gleiche Blockstruktur wie im Lesemodus, damit man sich wiederfindet.
- Fortschrittsanzeige oben: „7 von 9 Pflichtfeldern ausgefüllt“; fehlende Pflichtfelder in der Gliederung des Formulars markiert, Klick springt hin.
- Feldbeschriftung über dem Feld, darunter kurzer Hilfetext (aus den Felddefinitionen) in Sekundärfarbe.
- Große Textfelder, die mitwachsen. Rich-Text-Editor mit **minimaler** Werkzeugleiste (fett, Liste, nummerierte Liste, Link, Verweis `[[`). Keine Schriftarten, Farben oder Schriftgrößen.
- **Kompetenzauswahl:** Suchfeld mit Vorschlägen, Filter-Chips für Bereich und Stufe, ausgewählte Kompetenzen als entfernbare Chips im Klartext (gekürzt, voller Text als Tooltip/Antippen).
- Feste Aktionsleiste unten (sticky): **Speichern als Entwurf** (primär) · Status ändern · Abbrechen. Hinweis „Zuletzt gespeichert vor 2 Minuten“; automatisches Zwischenspeichern, wenn bereits vorhanden.
- Validierungsfehler direkt am Feld, verständlich formuliert („Bitte einen Jahrgang auswählen“), nie nur oben gesammelt.

### 5.5 Dokumentübersicht (z. B. Arbeitsplan Deutsch)
- Kopf mit Titel, Gültigkeitsstand, Buttons „Als PDF“ und „Änderungen seit Beschluss“.
- Gliederung als gut lesbare Inhaltsübersicht; Kapitel 2.1 zeigt Rituale und Vorhaben als **Karten**, gruppierbar nach Jahrgang, mit Status-Badge, Quartal, Zeitumfang.
- Reiter oder Unternavigation für die Auswertungen.

### 5.6 Auswertungen
- **Abdeckungsmatrix:** Tabelle mit fixierter erster Spalte (Kompetenz) und Kopfzeile; Zellen als farbige Felder mit Zahl; Aggregat je Schwerpunkt oben als Balken mit Prozentangabe. Klick auf eine Kompetenz zeigt die abdeckenden Vorhaben.
- **Fahrplan je Jahrgang:** Zeitleiste über das Schuljahr (Q1–Q4) mit Vorhaben als Blöcken; Rituale als durchgehende Bänder darüber. Auf dem Handy als vertikale Liste.
- **Zeitbudget:** einfacher Balken „Rituale binden X % der Deutschzeit“.
- **Leistungsübersicht:** Tabelle je Jahrgang, Klassenarbeiten hervorgehoben.
- Diagramme schlicht, ohne 3D und Effekte, mit Beschriftung direkt an den Daten.

### 5.7 Meine Planung
- Oben Auswahl Schuljahr + Klasse (große Auswahlfelder).
- Liste nach Quartal; jede Zeile mit großem **Häkchen-Feld**, Titel, kurzem Hinweis und Notiz-Symbol. Erledigtes rutscht optisch zurück (abgeschwächt), bleibt aber sichtbar.
- Fortschritt je Quartal als kleine Leiste.

### 5.8 Beschlüsse und Protokolle
- Beschlussliste chronologisch, je Beschluss: Datum, Gremium, Titel, Anzahl betroffener Einträge.
- Beschlussseite zeigt, welche Einträge er freigeschaltet hat (Liste mit Links).

### 5.9 Verwaltung / Import
- Darf nüchterner sein, aber dieselben Komponenten nutzen.
- Import-Vorschau als Tabelle mit klaren Markierungen: grün = ok, gelb = Hinweis, rot = Fehler mit Erklärung; Button „Übernehmen“ erst aktiv, wenn keine Fehler.

## 6. Komponenten (einmal bauen, überall nutzen)

Status-Badge · Kennungs-Badge · Kompetenz-Chip (mit Bereichsfarbe) · Gültigkeitsbanner · Karte · Button (primär, sekundär, leise, Gefahr) · Formularfeld mit Label/Hilfetext/Fehler · Suchfeld mit Dropdown · Leerer Zustand · Toast-Meldung („Gespeichert“) · Tabelle mit fixierter Kopfzeile · Akkordeon/Reiter · Anhang-Kachel · Kommentar.

Lege eine interne Seite **`/styleguide`** (nur Admin) an, auf der alle Komponenten mit ihren Zuständen zu sehen sind.

## 7. Zustände und Rückmeldungen

- Jede Aktion gibt sichtbare Rückmeldung (Toast unten, verschwindet nach ~3 s).
- Ladezustände bei Suche und HTMX-Anfragen: dezente Ladeanzeige, kein Springen des Layouts.
- Leere Zustände immer mit einem Satz Erklärung und – wenn sinnvoll – einer Aktion („Noch keine Vorhaben für Jahrgang 2. Vorhaben anlegen“).
- Bestätigungsdialog nur bei Dingen, die nicht rückgängig zu machen sind.
- Fehlermeldungen in normaler Sprache, ohne Stacktrace oder Fachbegriffe.

## 8. Sprache in der Oberfläche

- Deutsch, freundlich, kurz. **Duzen** [PLATZHALTER: mit mir bestätigen – im Kollegium üblich].
- Begriffe aus der Schule verwenden: Vorhaben, Ritual, Jahrgang, Fachkonferenz, Beschluss – nicht „Entity“, „Item“, „Record“.
- Buttons mit Verben: „Speichern“, „Als Entwurf speichern“, „Zur Abstimmung geben“.
- Datumsformat `TT.MM.JJJJ`, Schuljahr `2026/27`.

## 9. Barrierefreiheit und Technik

- WCAG 2.1 AA: Kontraste, sichtbarer Fokusrahmen, vollständige Tastaturbedienung, Labels an allen Feldern, sinnvolle Überschriftenhierarchie.
- `prefers-reduced-motion` respektieren; Animationen kurz (≤ 200 ms) und funktional.
- Optional, aber gern: **Dunkelmodus** über `prefers-color-scheme`, sauber über die Tokens gelöst.
- Druckstylesheet für Eintragsseiten (Lesemodus ohne Navigation).
- Keine externen CDNs; alle Schriften, Icons und Skripte lokal.
- CSS schlank halten: Tokens + Basis + Komponenten + Seiten. Kein großes UI-Framework nachträglich einführen, ohne mich zu fragen.

## 10. Vorgehen

1. **Bestandsaufnahme:** Liste aller Seiten/Templates, aktuelle Probleme kurz benennen.
2. **Grundlagen:** Tokens, Basisstyles, Grundlayout, Komponenten, `/styleguide`. → **Screenshots an mich, Freigabe abwarten.**
3. **Startseite und Suche.** → Screenshots.
4. **Eintrag lesen und bearbeiten** (Vorhaben, Ritual, Grundlagenkapitel).
5. **Dokumentübersicht und Auswertungen.**
6. **Meine Planung, Beschlüsse, Verwaltung.**
7. **Feinschliff:** Responsivität (Breiten 390, 768, 1024, 1440 px), Tastatur, Kontrast, Druck.

Nach jedem Schritt: Screenshots bei 1440 px und 768 px (iPad hochkant), mit Playwright o. Ä. automatisch erzeugt und in `docs/screenshots/` abgelegt, Tests weiterhin grün, Commit mit deutscher Nachricht.

## 11. Abnahme

- Eine Kollegin ohne Einweisung findet über die Startseite in unter 30 Sekunden die Absprache zur Lesezeit in Jahrgang 2.
- Eine Kollegin legt am iPad ein neues Vorhaben an, ohne zu fragen, was ein Feld bedeutet.
- Auf jeder Inhaltsseite ist ohne Scrollen erkennbar, ob der Inhalt beschlossen ist.
- Keine Seite hat horizontales Scrollen bei 390 px Breite (außer gekennzeichneten Tabellen).
- Lighthouse-Barrierefreiheit ≥ 95 auf Startseite, Suche und Eintragsseite.
