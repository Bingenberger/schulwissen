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
| Auswertungen | `deutsch/abdeckung.html`, `fahrplan.html`, `leistung.html`, `progressionspaare.html`, `pruefliste.html`, `ritualprogression.html`, `zeitbudget.html`, `_auswertungsnavigation.html` | Viertes Paket |
| Planung | `kern/planung.html` | Fünftes Paket |
| Beschlüsse | `kern/beschluesse.html`, `beschluss.html`, `beschluss_anlegen.html`, `beschlussvorlage.html`, `admin_beschluesse.html` | Fünftes Paket |
| Import und Export | `kern/json_import.html`, `export_pdf.html` | Fünftes Paket und Druckprüfung |

Die Pfade in der Tabelle sind relativ zum jeweiligen `templates/`-Verzeichnis. Zusätzlich bleibt die Django-Verwaltung erhalten und wird im fünften Paket auf Konsistenz geprüft.

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

`docs/gestaltung-pruefung.cjs` erzeugt die Screenshots erneut und prüft Breiten, Suchbedienung, Menü und WCAG AA. Benötigt wird eine lokale Demo-Instanz mit den vorhandenen Märchen-Beispielen und ein Administrationskonto. Das Skript liest Inhalte und verändert keine Schuldaten; es überschreibt die zugehörigen Screenshot-Dateien.

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
