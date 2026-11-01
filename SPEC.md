# Schulwissen-Plattform GGS Niederkassel – Auftrag für Claude Code

> **So startest du:** Lies diese Datei vollständig. Arbeite zuerst im Plan-Modus, stelle mir offene Fragen (Abschnitt 14) und schlage einen Umsetzungsplan für **Phase 1** vor. Beginne erst nach meiner Freigabe mit dem Code. Alle Oberflächentexte, Kommentare in der Doku und Commit-Nachrichten auf Deutsch.

---

## 1. Kontext

Die GGS Niederkassel ist eine Grundschule in NRW mit rund 24 Lehrkräften (inkl. Sozial- und Sonderpädagogik). Das Schulwissen liegt heute verstreut in einer **Nextcloud** (Word-/PDF-/ODT-Dateien) und auf einer digitalen Pinnwand (Edumaps), die auf diese Dateien verlinkt. Probleme:

- Informationen findet man nur, indem man Dateien öffnet; die Nextcloud-Suche ist schlecht.
- Dokumente sind linear, nicht verlinkt, nicht durchsuchbar.
- Gemeinsames Schreiben in Word-Tabellen nervt das Kollegium (Formatierung verrutscht, Word/LibreOffice/Mac gemischt).
- Konferenzbeschlüsse geraten in Vergessenheit; neue Kolleginnen finden die Absprachen nicht.

**Ziel:** Eine selbst gehostete Webapp, in der Arbeitspläne, Konzepte und Konferenzbeschlüsse als **strukturierte, verlinkte, durchsuchbare Einträge** leben. Das Kollegium schreibt direkt in der App, Entwürfe werden erst per **Konferenzbeschluss** freigeschaltet. Die Nextcloud bleibt als Dateispeicher dahinter.

**Erster Anwendungsfall:** der neue **Arbeitsplan Deutsch** (inkl. Leistungskonzept), der ab dem pädagogischen Ganztag am 9.11.2026 erarbeitet wird. Ziel für den Beschluss: Schuljahr 2027/28.

## 2. Leitprinzipien

1. **So einfach wie Google.** Das Kollegium ist wenig digital-affin. Startseite = großes Suchfeld. Keine versteckten Menüs, keine Fachbegriffe aus der IT.
2. **Formulare statt Formatierung.** Lehrkräfte füllen Felder aus; das Layout macht die App.
3. **Stabiler Kern, wachsende Dokumenttypen.** Neue Typen (Hygienekonzept, Medienkonzept, Arbeitsplan Mathe …) kommen ohne Umbau des Kerns hinzu.
4. **Nachvollziehbarkeit.** Jeder gültige Inhalt zeigt, durch welchen Beschluss (Datum, Gremium) er gilt. Historie bleibt erhalten.
5. **Keine Schülerdaten.** Die App verarbeitet nur Accounts des Kollegiums. Kindbezogene Beschlüsse werden höchstens anonymisiert eingetragen. Das System soll keine Felder anbieten, die zu personenbezogenen Schülerdaten einladen.

## 3. Nicht-Ziele (vorerst)

- Keine Schüler- oder Elterndaten, keine Notenverwaltung (dafür gibt es den KompetenzKompass).
- Kein Ersatz der Nextcloud als Dateiablage.
- Kein kollaboratives Echtzeit-Editing wie Google Docs; einfaches Sperren/Versionskonflikt-Hinweis genügt.
- Keine native Mobile-App; die Webapp muss aber auf Tablet und Handy gut bedienbar sein.

## 4. Technik

**Vorschlag (vor Beginn mit mir bestätigen):**

- **Backend:** Python 3.12, Django 5 (Admin, Auth, Migrationen, ORM)
- **Datenbank:** PostgreSQL 16 mit Volltextsuche (`german`-Konfiguration) und `pg_trgm` für Autovervollständigung
- **Frontend:** serverseitig gerenderte Templates + HTMX + wenig Alpine.js; kein SPA-Build nötig. Rich-Text-Editor: ein schlanker Editor (z. B. Tiptap oder Trix), der sauberes HTML/Markdown speichert
- **Dateiextraktion:** `pypdf`, `python-docx`, `odfpy`/`odfdo` für Volltext aus Anhängen
- **Nextcloud:** WebDAV (z. B. `webdavclient3` oder `httpx` direkt)
- **PDF-Export:** WeasyPrint aus HTML-Templates
- **Betrieb:** Docker Compose (app, db) **oder** systemd + nginx unter `/opt/schulwissen` auf einem Ubuntu-LXC (Proxmox). Beides dokumentieren, Compose bevorzugen.
- **Tests:** pytest + pytest-django; Linting mit ruff

Wenn du einen anderen Stack für klar besser hältst, begründe das im Plan.

## 5. Rollen und Rechte

| Rolle | Darf |
| --- | --- |
| Administration (Schulleitung) | alles: Nutzer, Dokumenttypen, Stammdaten (Kompetenzen), Beschlüsse anlegen, Status „beschlossen“ setzen, Import/Export |
| Redaktion (z. B. Fachkonferenzvorsitz) | Einträge in zugewiesenen Dokumenten bearbeiten, Status bis „abgestimmt in Gruppe“ setzen, Beschlussvorlagen zusammenstellen |
| Lehrkraft | lesen; Entwürfe anlegen und bearbeiten (eigene und die ihrer Arbeitsgruppe); kommentieren; persönliche Planung |
| Lesend | nur beschlossene Inhalte lesen (z. B. OGS, Vertretungskräfte) |

Arbeitsgruppen (z. B. „Jahrgang 1“) sind Nutzergruppen, denen Einträge zugeordnet werden können.

Seit Roadmap AP02 gelten zusätzlich ausdrückliche Dokument- und Bereichszugänge:
Lesen, Bearbeiten und fachliche Freigabe sind getrennte Rechte für Nutzer oder Gruppen.
Dokumente sind standardmäßig allgemein lesbar; gesperrte Bereiche und zusätzlich
gesperrte Dokumente benötigen jeweils ihre eigene Leseregel. Arbeitsgruppenmitgliedschaft,
Urheberschaft und die technische Rolle Redaktion umgehen diese Grenzen nicht.
Bearbeiten und Freigeben benötigen Kollegiumsrolle und Dokumentzugang. Die
Administration verwaltet die Regeln; zugewiesene Fachredaktionen können mit passenden
Django-Rechten ihre fachbezogenen schulischen Festlegungen pflegen. Fachliche Freigaben
können ausdrücklich delegiert werden; sie vergeben kein allgemeines Bearbeitungsrecht.
Ein Beschluss über mehrere Dokumente ist nur sichtbar, wenn sein gesamter dauerhafter
Dokumentrahmen zugänglich ist. Details: [AP02_DOKUMENTZUGAENGE.md](docs/AP02_DOKUMENTZUGAENGE.md).

Anmeldung: lokale Accounts (E-Mail + Passwort, Passwort-Reset per Mail). Architektur so anlegen, dass später OIDC (Nextcloud als Login) ergänzt werden kann.

## 6. Datenmodell – Kern

Alle Tabellen mit `id`, `erstellt_am`, `geaendert_am`, `erstellt_von`.

### Schulfunktionen (AP04)
- `Schulfunktion`: stabile Kennung, Name, Aufgabe, Einzel-/Teammodus, Archivstatus und optionaler dienstlicher Funktionskontakt; unabhängig von Zugriffsrollen und Arbeitsgruppen.
- `Funktionsbesetzung`: vorhandenes Nutzerkonto, Funktion, optionaler `Funktionsbereich`, Hauptzuständigkeit/Vertretung, einschließlich gültiger Zeitraum, bewusst aktivierte Vertretung und Stornierung.
- `Funktionsstand`: unveränderliche Revisionshistorie von Funktion und Besetzung. Besetzungen werden beendet oder storniert, nicht gelöscht oder mit einer anderen Person überschrieben.
- Benannte Funktionsbereiche besitzen stabile Namen und Kennungen; sie vergeben keine Zugriffsrechte. Funktionsbereich und Historie weichen bei Metadaten vom allgemeinen Zeitstempelschema ab.
- Aktuelle Zuständigkeiten im lesbaren Verzeichnis, höchstens zwölf Funktionen je Seite; Pflege mit aktiver Nutzersuche ausschließlich in der Administration. Zentraler Resolver für spätere Prozessschritte; keine zufällige Auswahl bei Teams, keine automatische Vertretungsübernahme.
- Einrichtung, Datumsgrenzen, Historie und Schnittstelle: [AP04_SCHULFUNKTIONEN.md](docs/AP04_SCHULFUNKTIONEN.md).

### Dokumenttyp
- `schluessel` (z. B. `arbeitsplan_deutsch`, `konzept`, `protokoll`), `name`, `beschreibung`
- `eintragstypen`: welche Eintragstypen in diesem Dokumenttyp erlaubt sind
- Typspezifische Felder werden **im Code** als Eintragstyp-Klassen/Schemata definiert (siehe 7), nicht frei in der Oberfläche zusammengeklickt. Ziel: Neue Typen = neues Modul im Code, kein Umbau des Kerns.

### Dokument
- `titel`, `dokumenttyp`, `fach` (optional), `beschreibung`, `gueltig_ab_schuljahr`
- `bereich` (optional), `kollegiumsweit`; Zugangsregeln für Dokument oder Wissensbereich
- `gliederung`: Reihenfolge der Kapitel (über `Eintrag.eltern` + `Eintrag.position`)

### Eintrag (generisch)
- `dokument`, `eintragstyp` (z. B. `grundlagenkapitel`, `ritual`, `vorhaben`, `beschluss_text`)
- `kennung` (lesbare ID, z. B. `R-01`, `V-3-01`, `2.4`), eindeutig je Dokument, **wird nie neu vergeben**
- `titel`, `eltern` (für Verschachtelung), `position`
- `status`: `idee` | `entwurf` | `abgestimmt` | `beschlossen` | `archiviert`
- `daten` (JSONB): typspezifische Felder, validiert durch das Schema des Eintragstyps
- `verantwortlich` (Gruppe oder Person)
- `suchtext` (generiert, für Volltextindex)

### Eintragsversion
- Jede Speicherung eines Eintrags erzeugt eine Version (`eintrag`, `versionsnummer`, `daten`-Snapshot, `titel`, `status`, `autor`, `zeitpunkt`).
- **Beschlossene Versionen sind unveränderlich.** Wer einen beschlossenen Eintrag bearbeitet, erzeugt einen neuen Entwurf; die beschlossene Fassung bleibt bis zum nächsten Beschluss gültig und sichtbar.
- Lesende sehen standardmäßig die zuletzt beschlossene Fassung; Bearbeitende sehen zusätzlich den Entwurf mit Unterschieden (Diff-Ansicht).
- Seit AP03 prüfen Eingabemaske und Verwaltung einen signierten Ausgangsstand unter derselben Datenbanksperre wie die Speicherung. Konflikte erhalten die eigene Eingabe und erfordern einen Vergleich mit ausdrücklich bestätigter Auflösung. JSON-Vorschau und Übernahme sind an Importinhalt und Dokumentstand gebunden; Details: [AP03_SCHREIBSCHUTZ.md](docs/AP03_SCHREIBSCHUTZ.md).

### Gültigkeit und Wissenspflege (AP09)

- Inhaltsart und Verbindlichkeit sind typisierte, versionierte Angaben; Dokumentzugang und Bearbeitungsstand bleiben getrennt. Altbestände sind zunächst nicht fachlich eingeordnet.
- Wirksam ab/bis, letzter Prüfstand, nächster Prüftermin, Quellen, Pflegefunktion/Vertretung und Nachfolger gehören zum Schnappschuss. Eine zukünftige Freigabe verdrängt die heutige nicht. Ablauf einer jüngeren Regel reaktiviert keine ältere; ein überfälliger Prüftermin beendet keine Gültigkeit.
- Die fachliche Freigabe für Routineinformationen benötigt keine erfundene Konferenz. Getrennte Freigaberechte, Nachweis und bestehender Schreibschutz gelten weiter.
- Eine rechtegebundene Pflegeübersicht zeigt aktuell überfällige Prüfungen und ausdrücklich gemeldete Fehler, höchstens zwölf je Seite. Rollenwechsel aktualisieren Ansprechpartner ohne Inhaltskopien oder neue Rechte.
- Verbindliche Anlagen werden als geschützte, bytegenaue Freigabekopie mit SHA-256 an die Eintragsversion gebunden. Externe Anlagen benötigen geprüfte Kopie und Versionsnachweis; reine Live-Links bleiben dynamisches Material. Originaländerungen werden angezeigt, Freigabekopien bleiben unverändert. Anleitung und Grenzen: [AP09_WISSENSPFLEGE.md](docs/AP09_WISSENSPFLEGE.md).

### Schulhandbuch und Formularverzeichnis (AP10)

- Aufgabe, Kurzantwort/Verwendungszweck und Suchbegriffe/Synonyme sind gemeinsame versionierte Wissensangaben. Bestehende Quellen können über eine freigegebene Aufgaben-Zuordnung im Handbuch erscheinen, ohne ihre Inhalte zu kopieren.
- Handbuch und Formularverzeichnis zeigen ausschließlich heute gültige zugängliche Fassungen mit höchstens zwölf Einträgen je Seite. Die allgemeine Suche enthält die Gruppe „Schulhandbuch und Formulare“; mehrere Einstiege verweisen auf dieselbe Quelle.
- Formulare sind die fachliche Inhaltsart vorhandener Einträge. Neue Freigaben benötigen Verwendungszweck und verbindliche Dateifassung. Das Verzeichnis zeigt geprüfte Downloads, aktuellen Pflegekontakt und gültige zugängliche Prozessbezüge; es erweitert keine Rechte auf Arbeitsstandsexporte.
- Die schulische Auswahl und Aufnahme zehn echter Abläufe ist offen. Ein Aufnahmeplan und zehn nicht freigabefähige Aufnahmeentwürfe stehen bereit; keine tatsächliche Schulregel wurde daraus automatisch erzeugt. Anleitung: [AP10_SCHULHANDBUCH.md](docs/AP10_SCHULHANDBUCH.md).

### Prozesse (AP05–AP08)

- Der Dokumenttyp `schulhandbuch` erlaubt `grundlagenkapitel` und `prozess`; bestehende Typen bleiben erhalten.
- Prozesse speichern Anlass, Zielgruppe, Schlagwörter und einen Graphen mit eigener Schema-Version. Start, Handlung, Entscheidung, Ende und beschriftete Verbindungen einschließlich expliziter Rücksprünge verwenden stabile IDs.
- Strukturprüfung gilt für Entwürfe; vor Abstimmung und Freigabe gelten zusätzliche Vollständigkeits-, Erreichbarkeits-, Kreis- und Referenzprüfungen. Freigaben werden in den bestehenden Beschluss- und Versionswegen abgesichert.
- Prozessdaten bleiben Teil von `Eintrag.daten` und `Eintragsversion`, einschließlich bestehendem Schreibschutz, Fassungsvergleich und Suchsichtbarkeit. Funktions-/Bereichs-/Ressourcenbezüge stehen zusätzlich in der gemeinsamen Referenzverwaltung.
- Seit AP06 bietet die normale Maske Schrittbearbeitung, Funktions-/Bereichsauswahl, Materialien, serverseitige Prüfung mit Sprungzielen und eine automatisch erzeugte SVG-Vorschau. IDs und eigene Eingaben bleiben beim Speichern sowie bei Konflikten erhalten. Seit AP07 stehen Grafik, geführte Auswahl, aktuelle Kontakte, rechtegebundene Materialien und vollständiger Text/Druck/PDF bereit; Entscheidungen bleiben flüchtig im Browser. Leseansicht: [AP07_PROZESSLESEN.md](docs/AP07_PROZESSLESEN.md). Seit AP08 führen der Einstieg „Abläufe“ und eine eigene Suchgruppe für alle berechtigten Rollen zur aktuell freigegebenen Prozessfassung. Arbeitsstände bleiben ausdrücklich zugänglich. Eine getrennt berechtigte Freigabemaske dokumentiert die zuständige Stelle, Datum und fachlichen Nachweis; sie schützt gegen zwischenzeitliche Änderungen. Externe Materialien bleiben als veränderlich gekennzeichnet. Veröffentlichung und offene fachliche Pilotabnahme: [AP08_PROZESSVEROEFFENTLICHUNG.md](docs/AP08_PROZESSVEROEFFENTLICHUNG.md). Schema: [AP05_PROZESSDATEN.md](docs/AP05_PROZESSDATEN.md); Editor: [AP06_PROZESSEDITOR.md](docs/AP06_PROZESSEDITOR.md).

### Beschluss
- `datum`, `gremium` (Lehrerkonferenz, Fachkonferenz Deutsch, Schulkonferenz, Steuergruppe …), `titel`, `text`
- `protokoll` (Verweis auf ein Protokoll-Dokument oder Anhang, optional)
- `beschlossene_versionen`: Liste von Eintragsversionen, die dieser Beschluss freischaltet
- `dokumente`: dauerhafter Zugangsrahmen, der bei Rücknahme erhalten bleibt
- Beim Speichern eines Beschlusses werden alle verknüpften Versionen auf `beschlossen` gesetzt, ältere beschlossene Versionen derselben Einträge auf `archiviert`.

### Verlinkung
- `von_eintrag`, `ziel_typ` (`eintrag` | `kompetenz` | `anhang` | `beschluss` | `nextcloud`), `ziel_id`, `art` (`verweist_auf`, `nutzt`, `ersetzt`, `kompetenz_schwerpunkt`, `kompetenz_beruehrt`, `bezug_ritual` …)
- Rückverweise werden automatisch angezeigt („Wird verwendet in …“).
- Im Rich Text sollen Verweise per `[[` + Suche eingefügt werden können (wie in Wikis); sie werden als Verlinkung gespeichert.

### Anhang
- hochgeladene Datei (lokal gespeichert) **oder** Nextcloud-Verweis (Pfad + Freigabe-Link)
- `dateiname`, `mimetype`, `groesse`, `beschreibung`, `extrahierter_text`, `index_stand`

### Kommentar
- an Eintrag (optional an Feld), `autor`, `text`, `erledigt`

### Persönlicher Fortschritt
- `nutzer`, `eintrag`, `schuljahr`, `klasse` (Freitext wie „3b“, **keine** Schülerdaten), `erledigt`, `erledigt_am`, `notiz`

### Nutzer / Gruppe
- Django-User + Profil (`anzeigename`, `kuerzel`), Gruppen für Arbeitsgruppen, Rollen über Django-Gruppen/Permissions

## 7. Dokumenttyp „Arbeitsplan Deutsch“

Struktur nach dem **QUA-LiS-Beispiel für schuleigene Unterrichtsvorgaben**: Kern sind Unterrichtsvorhaben statt Bereiche; Arbeitsplan und Leistungskonzept sind **ein** Dokument.

### 7.1 Gliederung (beim Anlegen des Dokuments automatisch erzeugt)

| Kennung | Kapitel | Eintragstyp |
| --- | --- | --- |
| 1 | Rahmenbedingungen der fachlichen Arbeit | grundlagenkapitel |
| 2 | Entscheidungen zum Unterricht | grundlagenkapitel (Klammer) |
| 2.1 | Unterrichtsvorhaben | Sammelkapitel für `ritual` und `vorhaben` |
| 2.2 | Fachdidaktische und fachmethodische Grundsätze | grundlagenkapitel |
| 2.3 | Differenzierung und individuelle Förderung | grundlagenkapitel |
| 2.4 | Leistungsbewertung und Leistungsrückmeldung | grundlagenkapitel |
| 2.5 | Lehr- und Lernmittel | grundlagenkapitel |
| 3 | Fächerverbindende Projekte | grundlagenkapitel |
| 4 | Qualitätssicherung und Evaluation | grundlagenkapitel |
| A | Anhang | grundlagenkapitel (nur Anhänge) |

Kapitel können umbenannt, ergänzt und verschachtelt werden; Nummerierung automatisch.

### 7.2 Eintragstyp `grundlagenkapitel`
Felder: `text` (Rich Text mit Überschriften, Listen, einfachen Tabellen), Anhänge, Verlinkungen.

### 7.3 Stammdaten `Kompetenzerwartung` (eigene Tabelle, fachbezogen)

Alle 117 Kompetenzerwartungen des Lehrplans Deutsch Primarstufe NRW (RdErl. v. 01.07.2021).

| Feld | Hinweis |
| --- | --- |
| `id` | z. B. `SC1.02S`; Aufbau: Bereich + Schwerpunkt-Nr. + „.“ + lfd. Nr. (2-stellig) + Stufe |
| `fach` | `deutsch` (später weitere Fächer) |
| `bereich`, `bereich_name` | SZ Sprechen und Zuhören · SC Schreiben · LE Lesen – mit Texten und Medien umgehen · SP Sprache und Sprachgebrauch untersuchen |
| `schwerpunkt_nr`, `schwerpunkt` | 14 Schwerpunkte |
| `stufe` | S = Ende Schuleingangsphase · K = Ende Klasse 4 · D = durchgängig |
| `text` | Kompetenzerwartung („Die Schülerinnen und Schüler …“) |
| `klammer` | verbindliche Inhalte laut Klammerzusatz |
| `ua_weiterer_inhalt` | bool: „u. a.“ = mindestens ein weiterer Inhalt verbindlich |
| `schulische_festlegung` | **schulspezifisch**: welcher weitere Inhalt bei uns verbindlich ist; Pflicht, wenn `ua_weiterer_inhalt` |
| `progressionspartner` | Verweis auf Erwartung gleicher Nummer der anderen Stufe |
| `stufe_pruefen` | bool: Stufenzuordnung rekonstruiert, noch am Lehrplan-PDF zu prüfen |

Kompetenzen sind für Lehrkräfte nur auswählbar, nicht editierbar (außer `schulische_festlegung` durch Redaktion/Admin).

### 7.4 Eintragstypen `ritual` und `vorhaben`

- **Ritual:** läuft dauerhaft im festen Takt, meist über alle Jahrgänge. Kennung `R-01`, `R-02` …
- **Vorhaben (einmalig):** zeitlich begrenzt, mit Produkt, genau ein Jahrgang. Kennung `V-[Jahrgang]-[Nr.]`, z. B. `V-3-01`.

| Feld (`daten`-Schlüssel) | Ritual | Vorhaben | Typ | Hinweis |
| --- | --- | --- | --- | --- |
| `kurzbeschreibung` | Pflicht | Pflicht | Text | Worum geht es, was entsteht? |
| Kompetenzen Schwerpunkt | Pflicht | Pflicht | Verlinkung `kompetenz_schwerpunkt` | gezielt aufgebaut, ggf. überprüft |
| Kompetenzen berührt | optional | optional | Verlinkung `kompetenz_beruehrt` | kommt vor, nicht im Fokus |
| `einheiten_pro_woche` | Pflicht | – | Zahl | Takt |
| `minuten_je_einheit` | Pflicht | – | Zahl | |
| `minuten_pro_woche` | berechnet | – | Zahl | Einheiten × Minuten |
| `fester_ablauf` | Pflicht | – | Rich Text | wiederkehrende Struktur |
| `auspraegung_jg1` … `auspraegung_jg4` | Pflicht | – | Rich Text ×4 | Progression; jede Jahrgangsgruppe füllt ihr Feld |
| `jahrgang` | – | Pflicht | Auswahl 1–4 | |
| `quartal` | – | Pflicht | Auswahl Q1–Q4, ganzjährig | |
| `zeitumfang_std` | – | Pflicht | Zahl | |
| Bezug zu Ritualen | – | optional | Verlinkung `bezug_ritual` | |
| `didaktik_methoden` | Pflicht | Pflicht | Rich Text | verbindliche methodische Absprachen |
| `material_medien` | optional | optional | Rich Text + Anhänge | Lehrwerk, Materialkiste, Nextcloud |
| `lernorte_kooperationen` | optional | optional | Text | Bücherei, Theater, Eltern, OGS |
| `faecherverbindung` | – | optional | Text (später Verlinkung) | |
| `differenzierung` | Pflicht | Pflicht | Rich Text | inkl. GL und DaZ |
| `leistung_bereich` | Pflicht | Pflicht | Auswahl | Sonstige Leistungen · Schriftliche Arbeiten · formativ (ohne Bewertung) |
| `leistung_feststellung` | Pflicht | – | Rich Text | Beobachtung, Rückmeldeformat, Kriterien |
| `leistung_form` | – | Pflicht | Rich Text | was wird wie überprüft |
| `leistung_kriterien` | – | Pflicht | Rich Text | Erwartungshorizont inkl. Niveau „befriedigend“, Verweis auf 2.4 |
| `klassenarbeit` | – | Pflicht | ja/nein | nur bei Jahrgang 3/4 auswählbar |
| `dokumentation` | optional | optional | Text | z. B. KompetenzKompass |
| `bemerkungen` | optional | optional | Text | |

Status, Verantwortlich, Fassung/Version kommen aus dem Kern.

**Eingabemaske:** Felder in Blöcken gruppiert: *Überblick* · *Kompetenzen* · *Zeit* · *Unterricht* · *Leistung* (farbig abgesetzt) · *Sonstiges*. Pflichtfelder markiert; Speichern als Entwurf ist immer möglich, Statuswechsel auf „abgestimmt“ erst, wenn alle Pflichtfelder gefüllt sind (die Maske zeigt, was fehlt).

**Kompetenzauswahl:** Suchfeld mit Autovervollständigung über ID und Text, Filter nach Bereich und Stufe, Anzeige immer im Klartext mit ID als kleinem Badge. Bei Vorhaben in Jg. 1/2 Erwartungen der Stufen S und D vorschlagen, in Jg. 3/4 K und D (nicht erzwingen).

### 7.5 Auswertungen (automatisch, nur lesend)

1. **Abdeckungsmatrix:** je Kompetenzerwartung „Schwerpunkt“ (≥ 1× als Schwerpunkt), „nur berührt“ oder „fehlt“; Zählungen getrennt für Rituale und Vorhaben; Aggregat je Schwerpunkt mit Anteil; „fehlt“ rot, „nur berührt“ gelb, „Schwerpunkt“ grün. Filter: nur beschlossene / inkl. Entwürfe.
2. **Fahrplan je Jahrgang:** Vorhaben nach Quartal + Rituale mit der Ausprägung dieses Jahrgangs.
3. **Ritual-Progression:** ein Ritual mit Jg. 1–4 nebeneinander.
4. **Zeitbudget:** Eingabe Deutschstunden/Woche je Jahrgang (Dokumenteinstellung) × 45 Min. gegen Summe `minuten_pro_woche` der Rituale; Anteil in %.
5. **Leistungsübersicht:** alle Überprüfungen und Klassenarbeiten je Jahrgang aus den Leistungsfeldern – das ist die Sicht „Leistungskonzept“.
6. **Progressionspaare:** S- und K-Erwartung nebeneinander mit abdeckenden Vorhaben.
7. **Prüfliste:** Erwartungen mit `stufe_pruefen` und „u. a.“-Erwartungen ohne `schulische_festlegung`.

## 8. Workflow und Freigabe

1. Lehrkraft/Gruppe legt Eintrag an → `idee` oder `entwurf`.
2. Gruppe stimmt ab → `abgestimmt` (nur bei vollständigen Pflichtfeldern).
3. Redaktion stellt eine **Beschlussvorlage** zusammen: Auswahl abgestimmter Einträge, als PDF exportierbar für die Konferenz.
4. Administration oder ausdrücklich zugewiesene Freigabeperson trägt den **Beschluss** ein (Datum, Gremium, Text) und verknüpft die Versionen → `beschlossen`; Vorgängerfassungen → `archiviert`.
5. Jeder beschlossene Eintrag zeigt oben sichtbar: „Gilt seit Beschluss der [Gremium] vom [Datum]“ mit Link.
6. Ansicht **„Änderungen seit letztem Beschluss“** je Dokument.

## 9. Suche (Herzstück)

- **Startseite:** ein großes, zentrales Suchfeld mit Fokus beim Laden; darunter höchstens: zuletzt angesehen, zuletzt beschlossen, eigene offene Entwürfe.
- **Autovervollständigung** ab 2 Zeichen (Debounce ~200 ms) über Titel, Kennungen, Kompetenz-IDs, Kapitel, Beschlusstitel (`pg_trgm`, tippfehlertolerant).
- **Ergebnisse gruppiert:** Arbeitspläne/Konzepte · Konferenzbeschlüsse · Kompetenzen · Dateien. Je Treffer: Titel, Kontext („Arbeitsplan Deutsch › 2.1 › V-3-01“), Trefferausschnitt mit Hervorhebung, Status-Badge.
- **Volltext** (deutsche Stammformen) über alle Textfelder in `daten`, Rich Text, Beschlusstexte und **extrahierten Text aus Anhängen** (PDF, DOCX, ODT, TXT).
- Filter nach Dokument, Status, Jahrgang, Fach.
- Standard: beschlossene Inhalte zuerst; Entwürfe nur für Berechtigte, gekennzeichnet.
- Index wird beim Speichern aktualisiert; Anhang-Extraktion asynchron (einfacher Hintergrund-Job, z. B. Django-Management-Command per systemd-Timer oder eine schlanke Queue; keine schwere Infrastruktur).

## 10. Nextcloud-Anbindung

- **Stufe 1 (Phase 2):** In Einträgen Nextcloud-Dateien verlinken: Dateiauswahl per WebDAV-Browser (Ordner durchklicken) mit einem technischen Nextcloud-Konto (App-Passwort in `.env`); gespeichert werden Pfad und ein Freigabe- bzw. Direktlink. Anzeige mit Dateityp-Icon.
- **Stufe 2 (Phase 4):** Verlinkte Nextcloud-Dateien regelmäßig abrufen, Text extrahieren, mit indexieren; Änderungen über ETag erkennen.
- Später optional: festgelegte Nextcloud-Ordner komplett indexieren.

## 11. Import und Export

### Import (Admin-Oberfläche + Management-Commands)
- **Kompetenzen** aus `lehrplan/kompetenzerwartungen_<fach>.json` (Felder: `id, bereich, bereichName, schwerpunktNr, schwerpunkt, stufe, text, klammer, uaWeitererInhalt, progressionspartner, stufePruefen, schulischeFestlegung`). Idempotent: erneuter Import aktualisiert, legt nicht doppelt an. Zusätzlich in der Oberfläche unter **Kompetenzen**: Export der gefilterten Auswahl als JSON, XLSX oder CSV und Import derselben Spalten – wahlweise als Lehrplandaten oder nur als schulische Festlegungen (docs/KOMPETENZDATEN.md).
- **Rituale und Vorhaben** aus `Datenmodell_Arbeitsplan_Deutsch.xlsx`, Blätter `Rituale` und `Vorhaben`: Spaltenüberschriften = Feldnamen laut Blatt `Felddefinitionen`; ID-Listen mit `;` getrennt; gelb markierte Beispielzeilen (Titel endet auf „(Beispiel)“) überspringen. Vor dem Import **Vorschau mit Validierung** (unbekannte Kompetenz-IDs, fehlende Pflichtfelder) und erst dann übernehmen.
- **Generischer JSON-Import** für Einträge beliebiger Dokumenttypen (Schema dokumentieren), damit Bestandskonzepte per KI-Agent umgewandelt und eingespielt werden können. Beispiel:

```json
{
  "dokument": "arbeitsplan-deutsch",
  "eintraege": [
    {
      "kennung": "V-3-01",
      "eintragstyp": "vorhaben",
      "titel": "Märchen entdecken und zu Märchenmotiven schreiben",
      "status": "entwurf",
      "daten": {
        "jahrgang": 3,
        "quartal": "Q2",
        "zeitumfang_std": 20,
        "kurzbeschreibung": "Märchen kennenlernen, Merkmale untersuchen, eigenes Märchen planen, schreiben, überarbeiten; Klassenmärchenbuch",
        "leistung_bereich": "Schriftliche Arbeiten",
        "leistung_form": "Märchen planen, verfassen und überarbeiten",
        "klassenarbeit": true
      },
      "kompetenzen_schwerpunkt": ["SC2.02D", "SC2.03D", "SC2.04D", "LE3.02K", "LE3.05D"],
      "kompetenzen_beruehrt": ["SZ2.02D", "SZ2.06D", "SC2.06D", "SP2.10D"],
      "bezug_rituale": ["R-01"]
    }
  ]
}
```

### Export
- **PDF** des beschlossenen Stands eines Dokuments in der Gliederung 7.1 (Deckblatt, Inhaltsverzeichnis, Kapitel, Vorhaben als einheitliche Steckbriefe, Abdeckungsmatrix im Anhang). Für Schulaufsicht und Einarbeitung.
- **PDF Beschlussvorlage** (Auswahl von Einträgen inkl. Änderungen).
- **JSON-Export** des gesamten Dokuments (Backup, Weiterverarbeitung).
- **XLSX-Export** der Rituale/Vorhaben im Format der Arbeitsmappe (Rundlauf möglich).

## 12. Oberfläche

- Klare, ruhige Gestaltung, große Schrift (mind. 16 px), große Klickflächen, gut auf iPad nutzbar.
- Navigation: oben Suchfeld (auf allen Seiten), links schmale Dokumentnavigation (Gliederungsbaum), Inhalt in der Mitte, rechts bei Einträgen: Status, Beschluss, Rückverweise, Kommentare.
- Eintragsansicht im **Lesemodus** zuerst; „Bearbeiten“ als deutlicher Button.
- **Meine Planung:** Klasse + Schuljahr wählen → Fahrplan des Jahrgangs mit Häkchen und Notizen je Vorhaben/Ritual.
- Barrierearm: Tastaturbedienung, ausreichende Kontraste, sinnvolle Labels.
- Keine Pflicht-Tutorials; kurze Hilfetexte direkt an den Feldern (aus den Felddefinitionen).

## 13. Phasen und Abnahmekriterien

**Phase 1 – Kern + Arbeitsplan Deutsch (Ziel: nutzbar zur Erfassung der Ergebnisse vom 9.11.)**
- Projekt-Setup, Docker Compose, README mit Installation
- Auth, Rollen, Gruppen
- Kernmodell (Dokument, Eintrag, Version, Verlinkung, Anhang-Upload, Kommentar)
- Dokumenttyp Arbeitsplan Deutsch mit Gliederung, Grundlagenkapiteln, Ritualen, Vorhaben
- Kompetenz-Stammdaten + JSON-Import
- XLSX-Import mit Vorschau
- Eingabemasken inkl. Kompetenzauswahl
- Abnahme: Ich kann die Beispielzeilen und 10 eigene Vorhaben importieren, bearbeiten, verlinken, und eine Lehrkraft ohne Einweisung legt ein neues Vorhaben an.

**Phase 2 – Suche, Freigabe, Auswertungen**
- Startseite mit Suche, Autovervollständigung, gruppierten Ergebnissen, Volltext inkl. Anhänge
- Beschlüsse, Statusworkflow, Versionen mit Diff, „Änderungen seit Beschluss“
- Auswertungen 7.5 (alle sieben)
- Nextcloud Stufe 1 (verlinken)
- Abnahme: Suche nach „Märchen“ findet das Vorhaben, das Kapitel 2.4 und eine verlinkte PDF; Abdeckungsmatrix stimmt mit der Excel-Übersicht überein.

**Phase 3 – Kollegium und Export**
- Meine Planung (Abhaken, Notizen)
- PDF-Export Dokument und Beschlussvorlage, JSON-/XLSX-Export
- Dokumenttypen „Konzept“ (nur Grundlagenkapitel) und „Konferenzprotokoll“ (Datum, Gremium, Tagesordnungspunkte, Beschlüsse)
- Generischer JSON-Import

**Phase 4 – Ausbau**
- Nextcloud Stufe 2 (indexieren)
- OIDC-Login
- weitere Fächer (Kompetenzen-Import je Fach)

Nach jeder Phase: kurze Demo-Anleitung für mich (was testen, wie), Tests grün, README aktualisiert.

## 14. Offene Fragen an mich (vor Phase 1 klären)

1. Stack wie in Abschnitt 4 vorgeschlagen ok?
2. Hosting: neuer LXC auf dem Proxmox-Host, Domain/Subdomain (z. B. unter gsndk.de)?
3. Docker Compose oder systemd/nginx direkt?
4. Lokale Accounts zum Start ok, oder direkt Login über Nextcloud?
5. Lehrwerk(e) je Jahrgang für Kapitel 1/2.5 – als Freitext oder als eigene Stammdaten?
6. Reicht Quartal als Zeitangabe für Vorhaben, oder Monate?
7. Sollen die Kompetenz-IDs auch im KompetenzKompass verwendet werden (spätere Verknüpfung)?

## 15. Arbeitsweise

- Kleine, nachvollziehbare Schritte; nach jedem größeren Baustein lauffähiger Stand + Commit mit deutscher Nachricht.
- Migrationen sauber halten; Beispieldaten per Fixture/Command (`./manage.py seed_demo`).
- Keine Geheimnisse im Repo; `.env.example` pflegen.
- Bei Unklarheiten fragen statt raten, besonders bei fachlichen Begriffen aus dem Schulkontext.
- Code und Bezeichner dürfen englisch sein, wo es Konvention ist (Django); fachliche Modell- und Feldnamen deutsch wie in dieser Datei, damit Import und Doku zusammenpassen.

## 16. Dateien, die ich bereitstelle

- `Datenmodell_Arbeitsplan_Deutsch.xlsx` (Blätter: Anleitung, Übersicht, Kompetenzerwartungen, Rituale, Vorhaben, Felddefinitionen, Wertelisten)
- `ps_lp_sammelband_2025_03_18_0.pdf` – der amtliche Sammelband aller zehn Lehrpläne der Primarstufe
- daraus gelesen: `lehrplan/kompetenzerwartungen_<fach>.json` (927 Kompetenzerwartungen in zehn Fächern) und `lehrplan/faecher.json`
- Der frühere Datensatz `kompetenzerwartungen_lp2021.json` hatte 61 Stufen als „zu prüfen“ markiert; sie sind am Sammelband geprüft und neun Angaben berichtigt (docs/KOMPETENZDATEN.md).
