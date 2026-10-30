# Gestaltung: Bestandsaufnahme und Umsetzung

Stand: 30.10.2026. Grundlage: DESIGN.md und SPEC.md. Schulgrün `#7AB648` und Duzen sind bestätigt. Das Buchsymbol kennzeichnet die Anwendung; es ist kein nachgebildetes Schullogo.

## Ausgangslage

Die Anwendung besitzt serverseitige Django-Vorlagen, lokales HTMX und Alpine sowie eine gemeinsame CSS-Datei. Suche, Rechte, Freigaben, Nextcloud und Auswertungen bestehen bereits. Die Gestaltung verändert diese Abläufe nicht.

Die bisherige Kopfzeile zeigt viele gleichgewichtige Aktionen. Die blaue Farbwelt, unterschiedliche Schriftgrößen und verstreute Abstände ergeben noch kein gemeinsames System. Startseite und Dokumentlisten wirken dicht. Inhaltsseiten enthalten teils Inline-Styles. Die mobile Gliederung, Tabellen und Formularführung benötigen jeweils einen eigenen Überarbeitungsschritt.

## Reihenfolge

1. **Erstes Freigabepaket:** zentrale Tokens, Basisstyles, Kopfzeile und Benutzermenü, lokale Symbole, Komponentenübersicht `/styleguide`, Startseite. Screenshots bei 1440 und 768 Pixeln, zusätzliche Prüfung bei 390 und 1024 Pixeln. Danach Freigabe gemäß DESIGN.md abwarten.
2. **Suche:** Ergebnisse und Vorschläge gruppieren, Filter und Trefferkarten vereinheitlichen.
3. **Einträge:** Lesemodus, Gültigkeit, Formularblöcke, Kompetenzen, Anhänge und Fassungen.
4. **Dokumente und Auswertungen:** Gliederung, Karten, Tabellen und Diagramme.
5. **Planung, Beschlüsse und Verwaltung:** gemeinsame Bausteine und verständliche Rückmeldungen.
6. **Feinschliff:** alle Seiten, Tastatur, Druck, Kontraste, responsive Ansichten und Lighthouse-Abnahme.

Die erste Startseite verwendet ausschließlich vorhandene Daten: letzte Beschlüsse und eigene offene Entwürfe mit höchstens fünf Einträgen je Bereich. Ein bisher nicht vorhandener Verlauf „Zuletzt angesehen“ wird nicht neu erfasst. Die Komponentenübersicht kennzeichnet Beispieldaten ausdrücklich.

## Vorlageninventar

| Gruppe | Vorlagen | Überarbeitung |
| --- | --- | --- |
| Grundlayout | `vorlagen/grundlage.html` | Erstes Paket |
| Start und neue gemeinsame Komponenten | `kern/startseite.html`, `_suchfeld.html`, `_symbol.html`, `_symbole.html`, `styleguide.html` | Erstes Paket |
| Anmeldung und Konto | `kern/anmelden.html`, `passwort_aendern.html`, `passwort_vergessen.html`, `passwort_gesendet.html`, `passwort_neu.html`, `passwort_fertig.html` | Basisstyles jetzt, Detailprüfung im Feinschliff |
| Suche und Kompetenzen | `suche/ergebnisse.html`, `_vorschlaege.html`; `fachdaten/uebersicht.html`, `_treffer.html` | Zweites Paket |
| Dokumente | `kern/dokument.html`, `dokument_neu.html`, `_navigation.html` | Viertes Paket |
| Lesen und Bearbeiten | `kern/eintrag.html`, `eintrag_bearbeiten.html`, `eintrag_unbekannt.html`, `_formular.html`, `_kompetenzauswahl.html`, `nextcloud.html` | Drittes Paket |
| Fassungen | `kern/fassungen.html`, `version.html`, `vergleich.html`, `aenderungen.html` | Drittes Paket |
| Auswertungen | `deutsch/abdeckung.html`, `fahrplan.html`, `leistung.html`, `progressionspaare.html`, `pruefliste.html`, `ritualprogression.html`, `zeitbudget.html`, `_auswertungsnavigation.html`, `_ansichten.html` | Viertes Paket |
| Planung | `kern/planung.html` | Fünftes Paket |
| Beschlüsse | `kern/beschluesse.html`, `beschluss.html`, `beschluss_anlegen.html`, `beschlussvorlage.html`, `admin_beschluesse.html` | Fünftes Paket |
| Import und Export | `kern/json_import.html`, `export_pdf.html` | Fünftes Paket und Druckprüfung |

Die Pfade in der Tabelle sind relativ zum jeweiligen `templates/`-Verzeichnis. Zusätzlich bleibt die Django-Verwaltung erhalten; `vorlagen/admin/base_site.html` bindet ihre gemeinsamen Gestaltungstokens ein. Mail- und Betreffvorlagen bleiben unverändert.

## Styles und Komponenten

- `dateien/tokens.css`: Farben einschließlich Dunkelmodus, Schrift, Abstände, Radien und Größen.
- `dateien/schulwissen.css`: Basis und gemeinsame Komponenten; bestehende Seitengestaltung bleibt bis zum jeweiligen Paket enthalten.
- `dateien/startseite.css`: Startseite.
- `dateien/styleguide.css`: interne Komponentenübersicht.
- `dateien/oberflaeche.js`: Tastaturbedienung der Suchvorschläge, Benutzermenü und Erfolgsmeldungen.
- Lokale SVG-Symbole und Systemschrift; keine neuen externen Ressourcen und kein UI-Framework.

Die Übersicht zeigt Status und Kennung, Kompetenz-Chip, Gültigkeit, Karten, Buttons einschließlich deaktiviertem Zustand, Formular mit Hilfe und Fehler, echte Suchvorschläge, leeren Zustand, Rückmeldungen, scrollbare Tabelle, Akkordeon, Anhang und Kommentar. Ihre Beispieldaten werden nicht gespeichert. Die Verwendung in den übrigen Seiten folgt nach Freigabe.

## Prüfung des ersten Pakets

- 331 automatisierte Tests bestanden, einschließlich fünf neuer Prüfungen für die Zugriffsgrenze von `/styleguide`; Ruff und Formatprüfung ohne Befund.
- Startseite und Komponentenübersicht bei 390, 768, 1024 und 1440 Pixeln ohne horizontalen Seitenüberlauf.
- Suchvorschläge mit Pfeiltasten, Enter und Escape; Schließen des Benutzermenüs mit Escape; mobiles Menü und Suchladeanzeige geprüft.
- Erfolgsmeldung nach drei Sekunden ausgeblendet, Pause bei Maus/Fokus, Fehlermeldung bis zum Schließen erhalten.
- Automatisierte WCAG-2.1-AA-Prüfung mit axe auf Startseite und Komponentenübersicht, jeweils hell und dunkel.
- Lighthouse-Barrierefreiheit für die angemeldete Startseite und Komponentenübersicht: jeweils 100 Punkte. Suche und Eintragsseite werden nach ihrer Überarbeitung separat geprüft. Automatisierte Prüfungen ersetzen die noch ausstehende Erprobung mit einer Kollegin nicht.
- Screenshots in `docs/screenshots/`: Desktop und iPad, zusätzlich Handy, Suchauswahl, mobiles Benutzermenü und Dunkelmodus.

### Screenshots und Browserprüfung wiederholen

`docs/gestaltung-pruefung.cjs` erzeugt die Screenshots aller Hauptansichten erneut und prüft Breiten, Suchbedienung, Pflichtfeldfortschritt und WCAG AA in beiden Farbmodi. Benötigt wird eine lokale Demo-Instanz mit den vorhandenen Märchen-Beispielen und ein Administrationskonto. Das Skript liest Inhalte und verändert keine Schuldaten; es überschreibt die zugehörigen Screenshot-Dateien.

Die Prüfung verwendet Playwright 1.64.1 mit Chromium und `@axe-core/playwright` 4.14.0. Diese Werkzeuge sind ausschließlich Prüfwerkzeuge und keine Laufzeitabhängigkeiten der Anwendung. Beispiel mit temporärem Installationsverzeichnis:

```bash
npm install --prefix /tmp/schulwissen-browser playwright@1.64.1 @axe-core/playwright@4.14.0
```

Für den Aufruf `NODE_PATH=/tmp/schulwissen-browser/node_modules`, `SW_PRUEF_EMAIL` und `SW_PRUEF_PASSWORT` setzen, dann `node docs/gestaltung-pruefung.cjs` ausführen. Chromium muss über Playwright installiert sein; alternativ kann das passende Playwright-Docker-Abbild `mcr.microsoft.com/playwright:v1.64.1-noble` verwendet werden. `SW_PRUEF_URL` erlaubt eine abweichende lokale Adresse. Zugangsdaten und Sitzungsdateien gehören nicht ins Repository.

Der Lighthouse-Lauf erfolgte mit Lighthouse 13.6.0, Desktop-Ansicht 1440 × 1000 und einer angemeldeten lokalen Browser-Sitzung, ausschließlich Kategorie Barrierefreiheit.

## Freigabegrenze

Das erste Paket wurde vom Nutzer freigegeben („das sieht super aus. Fahre fort“). Die weiteren Schritte werden in der dokumentierten Reihenfolge umgesetzt. DESIGN.md verlangt nach diesem Schritt ausdrücklich: „Screenshots an mich, Freigabe abwarten.“ Diese Freigabe liegt vor; eine weitere Zwischenfreigabe ist nicht verlangt.

## Schritt 2: Suche

Treffergruppen mit Anzahl, Klartext vor Kennung, Status auch für beschlossene Inhalte, Datei-Symbole und markierte Ausschnitte. Filter sind einzeln aufklappbare Chips. Filter bleiben beim Wechsel der Treffergruppe erhalten. Vorschläge sind nach Inhaltstyp gruppiert; vorhandene Dateitreffer werden über dieselbe zugriffsgeschützte Suche ergänzt, insgesamt weiterhin höchstens acht Vorschläge.

32 Suchtests bestanden, einschließlich des neuen Nachweises, dass Dateivorschläge für lesende Konten keine Entwurfsanhänge anzeigen. Ergebnisse und leerer Zustand bei 390/768/1024/1440 Pixeln ohne Überlauf, axe AA ohne Befund, Filterbedienung geprüft. Screenshots: `02-suche-*` und `02-suche-leer-*`.

## Schritt 3: Lesen und Bearbeiten

Gültigkeit steht vor dem Titel, mit getrenntem Hinweis auf einen vorhandenen neueren Entwurf. Beschlossene Fassung, Arbeitsstand und Vergleich bleiben über eindeutige Links erreichbar. Gliederung und Ritual-Jahrgänge sind auf kleinen Bildschirmen einklappbar. Inhaltsblöcke, Kompetenzbereiche mit Farbpunkt, Schwerpunkt und berührte Kompetenzen, Leistungsblock, Klassenarbeits-Badge und Anhang-Kacheln verwenden die gemeinsamen Bausteine. Gespeicherte Fassungen behalten ihren eigenen Gültigkeitshinweis.

Die Bearbeitung zeigt ausgefüllte und offene Pflichtfelder mit Sprung zum Feld. Die Pflichtbedingungen und die serverseitige Prüfung bleiben unverändert; Fehler werden zusätzlich direkt dem jeweiligen Feld zugeordnet. Die Speicherleiste bleibt erreichbar. Die primäre Editorleiste enthält Fett, Listen, Link und Verweis; vorhandene zusätzliche Formatierungen bleiben unter „Weitere Formatierung“ verfügbar. Textfelder wachsen beim Schreiben. Ausgewählte Kompetenzen erhalten ihren Klartext bereits beim Rendern; gekürzte Texte lassen sich antippen und aufklappen.

Screenshots: `03-eintrag-*`, `03-ritual-*`, `03-grundlagen-*`, `03-bearbeiten-*`. Vier Breiten, Tastatur, Pflichtfeldfortschritt, Sprung zum Feld und Klartextanzeige aller neun gewählten Kompetenzen geprüft. Keine Schuldaten für die Prüfung gespeichert.

## Schritt 4: Dokumente und Auswertungen

Vorhaben und Rituale stehen als Karten nach Jahrgang beziehungsweise Ritualen geordnet. Lesende erhalten auch bei den Karten-Metadaten ausschließlich die beschlossene Fassung; ein Regressionstest schützt Titel, Jahrgang, Quartal und Zeitumfang. Kapitel bleiben als übersichtliche Gliederung erhalten. Import und zusätzliche Exporte sind zurückgenommen, PDF und Änderungen direkt erreichbar.

Alle Auswertungen teilen dieselbe Navigation, einschließlich des ausgewählten Beschlussstands. Tabellen haben eine eigene Scrollfläche, einen sichtbaren Hinweis, feste Kopfzeile und erste Spalte. In der Abdeckungsmatrix lässt sich eine Kompetenz aufklappen, um die zugehörigen Vorhaben und Rituale zu öffnen. Der Fahrplan zeigt ganzjährige Ritualbänder über den Quartalen. Zeitbudget und Abdeckung behalten ihre beschrifteten Balken, Klassenarbeiten sind ausdrücklich gekennzeichnet.

Screenshots: `04-*`, jeweils Desktop und iPad. Die erste Tabellenspalte wurde beim seitlichen Verschieben und das Aufklappen der Kompetenzverweise zusätzlich mit Playwright geprüft.

## Schritt 5: Planung, Beschlüsse und Verwaltung

Die Planung verwendet große Auswahlfelder, gut treffbare Häkchen, einklappbare persönliche Notizen und einen Fortschrittsbalken pro Zeitraum. Gespeicherte erledigte Einträge treten optisch zurück. Die bisherige ausdrückliche Speicherung und die Trennung persönlicher Daten bleiben erhalten.

Beschlüsse erscheinen chronologisch mit Datum, Gremium, Titel und Anzahl freigegebener Fassungen. Die Beschlussseite behält ihre Fassungslinks und Protokolle. Die Importvorschau zeigt eine Tabelle mit Klartext und farbiger Prüfung; Übernehmen ist bei Fehlern deaktiviert. Ungültige und gültige Vorschau wurden über den echten Uploadweg geprüft, ohne den Import zu übernehmen. Die Django-Verwaltung übernimmt die zentralen Farben, Typografie und Eingabegrößen; ihre Berechtigungen und Datenmasken bleiben erhalten.

Screenshots: `05-*`, zusätzlich `05-importvorschau-*`.

## Schritt 6: Abschlussprüfung und Grenzen

- Vollständiger Testlauf: **333 Tests bestanden**. Zusätzlich gezielter erneuter Oberflächentest für die zuletzt ergänzten Klartexte der Kompetenzauswahl.
- Ruff, Python-Formatprüfung, JavaScript-Syntax und `git diff --check` ohne Befund.
- **22 Ansichten × 4 Breiten = 88 responsive Prüfungen**, ohne horizontalen Seitenüberlauf. Breite Tabellen scrollen innerhalb ihrer gekennzeichneten Fläche.
- **44 axe-Prüfungen** auf denselben 22 Ansichten, jeweils hell und dunkel, ohne automatisierten WCAG-2.1-AA-Befund. Dazu ergänzende Prüfungen von zehn Detail- und Formularansichten bei 390 Pixeln.
- Lighthouse 13.6.0: **100 Punkte Barrierefreiheit** auf angemeldeter Startseite, Suche und Eintragsseite. Gemessen mit Desktop-Emulation 1440 × 1000.
- Druck aus dem Dunkelmodus: heller Hintergrund, Inhalt und Gültigkeit bleiben erhalten, Kopfzeile, Gliederung und Nebenspalte werden ausgeblendet. Screenshots `06-druck-*`; PDF zusätzlich lokal geprüft.
- Lesendes Konto: beschlossene Fassung mit Gültigkeitsbanner, `/styleguide` weiterhin gesperrt. Neue Dateivorschläge verwenden die vorhandenen Leserechte.
- Wiederholbare Prüfung: `docs/gestaltung-pruefung.cjs`; maschinenlesbares Ergebnis: `docs/gestaltungspruefung.json`. Das Skript prüft alle Hauptansichten, beide Farbmodi und die Bedienung, erzeugt Screenshots und verändert keine Schuldaten.

Die Überarbeitung ergänzt keine zuvor nicht vorhandene Verlaufserfassung oder automatische Zwischenspeicherung. Statt eines vorgetäuschten Speicherstands zeigt das Formular den tatsächlichen Stand beziehungsweise „Ungespeicherte Änderungen“. Ein persönlicher Jahrgang ist am Konto nicht hinterlegt; deshalb wird keiner erfunden oder automatisch hervorgehoben. Nextcloud-Verbindung und Anmeldung werden weiterhin über die vorhandene Konfiguration betrieben.

Die beiden Abnahmekriterien mit einer Kollegin (Lesezeit ohne Einweisung finden und am iPad ein Vorhaben anlegen) bleiben eine **praktische Kollegiumsprobe**. Automatisierte Prüfungen können diese nicht bestätigen. Die technische Gestaltung und die dokumentierten Prüfungen sind abgeschlossen.
