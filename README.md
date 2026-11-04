# Schulwissen-Plattform der GGS Niederkassel

Arbeitspläne, Konzepte und Konferenzbeschlüsse als **strukturierte, verlinkte und
durchsuchbare Einträge** statt als Word-Dateien in der Nextcloud. Das Kollegium
schreibt direkt in der App; Entwürfe werden erst per Konferenzbeschluss gültig.

Erster Anwendungsfall ist der **Arbeitsplan Deutsch** inklusive Leistungskonzept,
der ab dem pädagogischen Ganztag am 9.11.2026 erarbeitet wird.

Die vollständige fachliche Beschreibung steht in [SPEC.md](SPEC.md).

<!-- schulplattform:installation -->
## Installation

### Im Rahmen der Schulplattform

Empfohlen für den Schulserver: Die [Schulplattform](https://github.com/Bingenberger/schulplattform) installiert diese App zusammen mit den
anderen Schul-Apps auf einem leeren Ubuntu-24.04-Server, mit eigener Subdomain, TLS-Zertifikat, Mailversand,
Sicherung und Dashboard. Sie verwendet das signierte Release-Image `ghcr.io/bingenberger/schulwissen`
und die unveränderte `docker-compose.yml` dieses Repositorys plus eine Override-Datei.

1. In der Plattformkonfiguration (`./install.sh configure` bzw. `/etc/schulplattform/platform.toml`)
   unter `[apps.schulwissen]` `enabled = true` und den Hostnamen setzen, z. B. `wissen.ihre-schule.de`,
   und beim DNS-Provider einen A-Eintrag auf den Server anlegen.
2. `./install.sh apply …` installiert die App. Migration, Proxy, Zertifikat und Sicherung übernimmt die Plattform.
3. `./install.sh app-setup schulwissen` legt das erste Konto per E-Mail-Adresse an (`manage.py admin_anlegen`); das Startpasswort erscheint nur am Terminal.
4. Daten vom bisherigen Server übernehmen: `./install.sh import schulwissen …` nach dem
   [Umzugs-Runbook](https://github.com/Bingenberger/schulplattform/blob/main/docs/betrieb/umzug.md).

### Standalone mit Docker Compose

Ohne Plattform, z. B. zum Ausprobieren oder für einen eigenen Server mit eigenem Proxy.
Benötigt Docker Engine mit Compose v2 (amd64). Die App lauscht danach nur auf `http://127.0.0.1:8001`.

```sh
cp .env.example .env && chmod 600 .env   # SW_SECRET_KEY und POSTGRES_PASSWORD setzen
docker compose build
docker compose run --rm app python manage.py platform_migrate
docker compose up -d
docker compose exec app python manage.py admin_anlegen deine@adresse.de
```

Die Migration läuft nicht mehr beim Containerstart, sondern ausdrücklich über `platform_migrate`.

Statt selbst zu bauen, kann das veröffentlichte Image verwendet werden (dann `docker compose build` weglassen):

```sh
docker pull ghcr.io/bingenberger/schulwissen:0.1.0 && docker tag ghcr.io/bingenberger/schulwissen:0.1.0 schulwissen:0.1.0-dev
```
<!-- /schulplattform:installation -->

## Stand

**Die Hauptbausteine der Phasen 1 bis 3 sind vorhanden** (SPEC.md §13).

Phase 1: Kern, Rollen, Arbeitsplan Deutsch, Kompetenz-Stammdaten, Import aus
der Arbeitsmappe, Eingabemasken.

Phase 2: Volltextsuche mit Autovervollständigung und gruppierten Ergebnissen,
Textextraktion aus Anhängen, Beschlüsse mit Statusworkflow, Fassungsvergleich,
„Änderungen seit Beschluss“, alle sieben Auswertungen aus §7.5 und die
Nextcloud-Verlinkung (Stufe 1).

Phase 3: persönliche Planung mit Häkchen und privaten Notizen je Klasse und
Schuljahr, PDF des beschlossenen Dokumentstands und ausgewählter
Beschlussvorlagen, JSON-/XLSX-Export, Dokumenttypen „Konzept“ und
„Konferenzprotokoll“ sowie generischer JSON-Import mit Vorschau.

Phase 4: ETag-basierte Nextcloud-Indexierung, konfigurierbare OIDC-Anmeldung
über Nextcloud und Fachverwaltung für alle Fächer. Die
Live-Verbindungen benötigen die Nextcloud-Konfiguration.

Die Kompetenzerwartungen **aller zehn Fächer der Primarstufe NRW** (927) liegen
in `lehrplan/` bereit und lassen sich als Tabelle ausgeben und wieder
einlesen – siehe [docs/KOMPETENZDATEN.md](docs/KOMPETENZDATEN.md). Der
Prüfbericht vom 1.11.2026 steht in
[docs/PRUEFUNG_KOMPETENZEN_UND_BEDIENUNG.md](docs/PRUEFUNG_KOMPETENZEN_UND_BEDIENUNG.md).
Einrichtung und Abnahme stehen in [PHASE4.md](PHASE4.md).
Das JSON-Importformat und die Exportgrenzen stehen in [JSON-IMPORT.md](JSON-IMPORT.md).

## Geplante Weiterentwicklung

Die [Roadmap](ROADMAP.md) übersetzt die
[Analyse des Grundschulalltags](docs/PRODUKTANALYSE_GRUNDSCHULE.md) in
priorisierte Arbeitspakete mit Abhängigkeiten und Abnahmekriterien für kommende
Coding-Sitzungen. AP01–AP07 (Lesefassungen, Dokumentzugänge, Schreibschutz,
Schulfunktionen, Prozessdaten, Autoreneditor und Leseansichten) sind umgesetzt; AP08 ergänzt Veröffentlichung und Prozesssuche. AP09 ergänzt [Gültigkeit, Quellen und Wissenspflege](docs/AP09_WISSENSPFLEGE.md) sowie verbindliche Dateikopien. [AP10](docs/AP10_SCHULHANDBUCH.md) ergänzt Handbuch nach Aufgaben, Kurzantworten/Synonyme und das Formularverzeichnis mit geschützten Downloads. Die Aufnahme zehn echter Schulabläufe und die fachliche Pilotabnahme bleiben offen; nächstes geplantes Coding-Paket ist **AP11**. Der [Prüfbericht vom 1.11.2026](docs/PRUEFUNG_KOMPETENZEN_UND_BEDIENUNG.md) schlägt vor, davor die Arbeitsplan-Gliederung für jedes Fach anzubieten: die Kompetenzdaten aller zehn Fächer liegen vor und ein Arbeitsplan Mathematik lässt sich anlegen, die Kapitelstruktur entsteht aber nur für Deutsch.
Den ersten großen Ausbau bildet
das [Prozesswerkzeug](docs/PROZESSWERKZEUG.md): Abläufe definieren, als
„Was passiert, wenn …?“-Grafik anzeigen und zuständige Schulfunktionsrollen mit
Personen aus dem vorhandenen Nutzerstamm besetzen. Das Funktionsverzeichnis ist
bereits über **Zuständigkeiten** im Benutzermenü erreichbar; die Pflege erfolgt in
der Verwaltung. Einrichtung, Vertretung und Personalwechsel:
[AP04_SCHULFUNKTIONEN.md](docs/AP04_SCHULFUNKTIONEN.md). Die
[Prozessdatenbasis](docs/AP05_PROZESSDATEN.md) unterstützt bereits Entwürfe,
Prüfung und Fassungen. Der [Prozesseditor](docs/AP06_PROZESSEDITOR.md) bietet
Schritte, Verzweigungen, Zuständigkeiten, Materialien und eine automatische
Vorschau ohne Diagrammcode. Die [Leseansicht](docs/AP07_PROZESSLESEN.md) bietet Grafik, geführte Auswahl, aktuelle Kontakte sowie Text und PDF. [Veröffentlichung und Prozesssuche](docs/AP08_PROZESSVEROEFFENTLICHUNG.md) sind seit AP08 verfügbar: Über **Abläufe** öffnet das Kollegium gültige Fassungen; Arbeitsstände bleiben ausdrücklich auswählbar. Der echte schulische Pilot und die Betriebsabnahme bleiben offen. Die Abnahme von AP01 steht in
[AP01_LESEFASSUNGEN.md](docs/AP01_LESEFASSUNGEN.md).

## Schnellstart

Voraussetzung: Docker mit Compose-Plugin (`docker compose version`).

```bash
cp .env.example .env
nano .env                 # SW_SECRET_KEY und POSTGRES_PASSWORD setzen
chmod 600 .env

docker compose build
docker compose run --rm app python manage.py platform_migrate
docker compose up -d
docker compose exec app python manage.py admin_anlegen deine@adresse.de
```

Danach läuft die App auf <http://127.0.0.1:8001>. Zum Ausprobieren mit
Beispieldaten und vier Demo-Konten:

```bash
docker compose exec app python manage.py seed_demo
```

Eine Klickanleitung zum Testen steht in [DEMO.md](DEMO.md), die Anleitung für
den Server in [DEPLOYMENT.md](DEPLOYMENT.md).

## Aufbau

| Verzeichnis | Inhalt |
| --- | --- |
| `schulwissen/` | Einstellungen, URLs, WSGI |
| `kern/` | Nutzer, Rollen, Dokumente, Fassungen, Beschlüsse, Anhänge, Kommentare, Planung, Exporte, Konzepte und Protokolle |
| `eintragstypen/` | Registry der Feldschemata, Formular-Fabrik, gemeinsamer Schreibweg |
| `fachdaten/` | Kompetenzerwartungen des Lehrplans, ihr Import, Export und ihre Suche |
| `lehrplan/` | Die 927 Kompetenzerwartungen aller zehn Fächer als Importdateien |
| `deutsch/` | Dokumenttyp „Arbeitsplan Deutsch“: Gliederung, Eintragstypen, XLSX-Import, Auswertungen |
| `suche/` | Volltextsuche über alle Gruppen und die Autovervollständigung |
| `vorlagen/`, `dateien/` | Seitengerüst und statische Dateien |
| `frontend/` | Quelle des Rich-Text-Editors (für den Betrieb **nicht** nötig) |

Die Modulnamen folgen der Django-Konvention (`models.py`, `views.py`), die
fachlichen Klassen- und Feldnamen sind deutsch wie in SPEC.md – damit Import,
Export und Dokumentation zusammenpassen.

### Der stabile Kern

Der Kern weiß, dass ein Dokument aus Einträgen besteht, dass jede Speicherung
eine Fassung erzeugt und dass ein Beschluss Fassungen gültig macht. *Welche*
Felder ein Eintrag hat, steht nicht im Kern, sondern als Datenstruktur in
`eintragstypen/registry.py`:

```python
Feld(
    schluessel="zeitumfang_std",
    label="Zeitumfang",
    typ=Feldtyp.ZAHL,
    block=Block.ZEIT,
    pflicht=True,
    hilfe="Grobe Orientierung.",
    xlsx_spalten=("Zeitumfang (Std.)",),
)
```

Aus dieser einen Beschreibung entstehen die Eingabemaske mit Block und
Hilfetext, die Prüfung des Wertes, die Liste „was fehlt noch“ beim Statuswechsel,
die Spaltenzuordnung des XLSX-Imports und später die Spalten des Exports.

**Ein neuer Dokumenttyp ist damit eine neue Moduldatei, kein Umbau des Kerns.**
Vorbild ist `deutsch/eintragstypen.py`.

Weil die Typen im Code stehen, kann die Datenbank sie nicht erzwingen – eine
Prüfbedingung dort bräuchte je neuem Typ eine Migration, und genau das soll sie
nicht. Stattdessen prüft die Anwendung: Das Feld bietet nur die registrierten
Typen an, `Eintrag.clean()` weist alles andere zurück, und
`manage.py eintraege_pruefen` findet Altlasten. Trifft die App doch auf einen
unbekannten Typ, zeigt sie einen Hinweis statt eines Fehlers – ein einzelner
Datensatz darf nicht das ganze Dokument unlesbar machen.

## Rollen

| Rolle | Darf |
| --- | --- |
| Administration | alles: Nutzer, Stammdaten, Beschlüsse, Import und Export |
| Redaktion | zugewiesene Dokumente/Bereiche bearbeiten, Status bis „abgestimmt in Gruppe“ setzen, fachbezogene schulische Festlegungen pflegen |
| Lehrkraft | zugängliche Dokumente lesen; Entwürfe anlegen und die eigenen und die der Arbeitsgruppe bearbeiten; kommentieren |
| Lesend | nur zugängliche beschlossene Inhalte lesen (OGS, Vertretungskräfte) |

Rollen und Arbeitsgruppen sind beides Django-Gruppen; ein `Gruppenprofil`
unterscheidet sie. Alle Zugriffsentscheidungen stehen an einer Stelle:
`kern/rechte.py`.

Lesen, Bearbeiten und fachliches Freigeben werden über ausdrückliche Regeln
für Dokumente oder Wissensbereiche vergeben. Die Administration öffnet dafür
auf der Dokumentseite **Zugänge verwalten**. Eine Gruppenmitgliedschaft allein
öffnet kein gesperrtes Dokument. Einrichtung und Bestandsmigration stehen in
[AP02_DOKUMENTZUGAENGE.md](docs/AP02_DOKUMENTZUGAENGE.md).

**Wer darf einen importierten Eintrag bearbeiten?** Beim Import übernimmt die
Arbeitsgruppe „Jahrgang N“ die Verantwortung für ein Vorhaben dieses Jahrgangs,
sonst die Gruppe aus der Spalte „Verantwortlich“. Findet sich keine, bleibt das
Feld leer – dann kommt nur die Redaktion heran und ordnet zu.

## Die Suche

Gesucht wird in vier Gruppen: **Arbeitspläne und Konzepte · Konferenzbeschlüsse ·
Kompetenzerwartungen · Dateien**. Je Treffer gibt es Titel, Kontextpfad
(„Arbeitsplan Deutsch › 2.1 › V-3-01“), einen hervorgehobenen Ausschnitt und
ein Status-Schild. Beschlossenes steht vorn; Entwürfe sieht nur, wer darf.

Drei Wege führen zum Treffer:

1. **Volltext** mit deutschen Stammformen – „Märchen“ findet auch „Märchens“.
   `websearch`-Syntax wird verstanden: Anführungszeichen für Wortgruppen, `-`
   zum Ausschließen, `OR`.
2. **Ähnlichkeit** (`pg_trgm`), wenn der Volltext keinen Eintrag findet – so
   verzeiht die Suche Tippfehler wie „Maerchen“.
3. **Wortlaut**, wenn die Eingabe nur aus Füllwörtern besteht. „Es war einmal“
   ergibt eine leere Volltextanfrage; statt nichts zu finden, sucht die App
   dann nach der genauen Zeichenfolge und sagt das auch.

Anhänge werden mitdurchsucht. Der Text wird dafür **im Hintergrund** gelesen
(`manage.py anhaenge_indexieren`, siehe DEPLOYMENT.md §5) – nicht beim
Hochladen, damit niemand auf ein großes PDF warten muss.

### Ein Wort zur Ähnlichkeitsschwelle

`pg_trgm` vergleicht Buchstabengruppen und findet in langen Texten fast immer
irgendetwas. „Märchen“ und „Recherchen“ teilen genug Dreiergruppen für einen
Wert von 0,5 – obwohl keine einzige Kompetenzerwartung von Märchen handelt.
Mit der ursprünglichen Schwelle von 0,35 kamen so 68 falsche Treffer heraus
und begruben das eine richtige Ergebnis.

Darum gelten in `fachdaten/suche.py` zwei Schwellen: **0,6 auf dem Volltext**
(verzeiht „Gesprch“, lässt „Märchen“ gegen „Recherchen“ durchfallen) und
**0,4 auf der Kennung**, wo kurze Zeichenketten verglichen werden.

## Beschlüsse

1. Die Gruppe stimmt einen Eintrag ab → Status „abgestimmt in Gruppe“.
2. Die Redaktion stellt unter *Beschlussvorlage* zusammen, was in die Konferenz
   soll (zum Ausdrucken genügt die Drucktaste des Browsers).
3. Die Administration oder eine ausdrücklich zuständige Freigabeperson trägt
   den Beschluss ein und schaltet die Fassungen frei.

Dabei gilt: die beschlossene Fassung ist **unveränderlich**. Wer an einem
beschlossenen Eintrag weiterarbeitet, erzeugt einen neuen Entwurf – die
beschlossene Fassung bleibt gültig, und **Lesende sehen weiterhin sie**, nicht
den Entwurf. Bearbeitende sehen den Arbeitsstand mit einem Hinweis und einem
Link auf die Unterschiede.

### Fassungen und Verwaltung

Lesende sehen in der Historie nur tatsächlich freigegebene Fassungen. Auch
gezielte Aufrufe einer Entwurfsfassung oder ein Vergleich mit deren Nummer
geben keinen Entwurf frei. Vergleiche zwischen freigegebenen historischen
Fassungen sind möglich; „Änderungen seit Beschluss“ bleibt dem Kollegium
vorbehalten. Konten ohne Kollegiumsrolle erhalten keine Entwurfsrechte allein
durch die Mitgliedschaft in einer Arbeitsgruppe.

In der Verwaltung bleiben Einträge und ihre Zuständigkeit, Position und
Kapitelzuordnung bearbeitbar. Jede Speicherung verwendet dieselbe fachliche
Prüfung, HTML-Bereinigung, Suchindexierung und Versionierung wie die Eingabemaske.
Eine Bearbeitung beschlossener Inhalte erzeugt einen neuen Entwurf.

Fassungen, Beschlüsse und Verweise werden in der Verwaltung nur angezeigt.
Verweise bearbeitet man über den Link zur Eingabemaske; Beschlüsse werden über
die Beschlussvorlage erfasst und gegebenenfalls dort zurückgenommen.
Direkte Statusfreigaben sowie das Löschen von Einträgen oder Historie sind in
der Verwaltung gesperrt.

## Auswertungen

Alle sieben aus SPEC.md §7.5, jeweils umschaltbar zwischen „inklusive
Entwürfe“ und „nur beschlossene“:

„Nur beschlossene“ verwendet Titel, Inhalte und Verweise aus den gültigen
Fassungen, auch wenn daneben neue Entwürfe existieren. Für Lesende ist dieser
Stand verbindlich; ein URL-Parameter kann keine Entwürfe einschalten.
Die Prüfliste behandelt die gemeinsamen Kompetenz-Stammdaten.

Abdeckungsmatrix · Fahrplan je Jahrgang · Ritual-Progression · Zeitbudget ·
Leistungsübersicht (die Sicht „Leistungskonzept“) · Progressionspaare ·
Prüfliste.

## Import

```bash
# Kompetenzerwartungen aller zehn Faecher aus lehrplan/
# (idempotent; schulische Festlegungen bleiben erhalten)
docker compose exec app python manage.py kompetenzen_importieren

# Rituale und Vorhaben: erst ansehen, dann übernehmen
docker compose exec app python manage.py arbeitsplan_importieren \
    Datenmodell_Arbeitsplan_Deutsch.xlsx --vorschau
docker compose exec app python manage.py arbeitsplan_importieren \
    Datenmodell_Arbeitsplan_Deutsch.xlsx
```

`--vorschau` schreibt garantiert nichts und meldet unbekannte
Kompetenz-Kennungen, ungültige Wertelisten-Werte, doppelte Kennungen und
fehlende Pflichtfelder. Ohne `--vorschau` gilt: **entweder alles oder nichts** –
ein Fehler bricht den ganzen Import ab.

Zeilen, deren Titel auf „(Beispiel)“ endet, werden übersprungen.
`--mit-beispielen` nimmt sie mit und entfernt den Zusatz aus dem Titel.

Beide Dateien liegen im Projektverzeichnis und sind im Abbild enthalten; die
Kommandos finden sie ohne weitere Angabe.

## Persönliche Planung und neue Dokumente

**Meine Planung** in der Kopfzeile öffnet den Fahrplan für eine Klasse und ein
Schuljahr. Der Jahrgang wird aus „3b“ erkannt oder ausdrücklich gewählt.
Häkchen und Notizen sind nur im eigenen Konto sichtbar und verändern keine
Einträge oder Fassungen. Sie erscheinen weder in der Verwaltung noch in den
Dokumentexporten.

Die Administration legt über **Dokument anlegen** auf der Startseite auch
Konzepte und Konferenzprotokolle an. Kapitel und Tagesordnungspunkte entstehen
über dieselben Formulare und durchlaufen denselben Beschlussworkflow wie
der Arbeitsplan. Auf der Dokumentseite stehen Import und Exporte bereit.

## Entwickeln

```bash
# Tests (eigenes Abbild mit pytest und ruff)
docker compose -f docker-compose.yml -f docker-compose.test.yml \
    run --rm werkzeug pytest

# Linter und Formatierung
docker compose -f docker-compose.yml -f docker-compose.test.yml \
    run --rm werkzeug sh -c "ruff check . && ruff format --check ."
```

Der Rich-Text-Editor ist gebündelt und liegt als `dateien/vendor/editor.js` im
Repository. Für den Betrieb wird kein npm gebraucht. Nur wenn der Editor
geändert werden soll:

```bash
cd frontend && npm install && npm run build
```

## Was die App nicht tut

- **Keine Schüler- oder Elterndaten.** Die App kennt nur Konten des Kollegiums.
  Das Feld „Klasse“ in der persönlichen Planung ist Freitext wie „3b“; Felder,
  die zu personenbezogenen Daten einladen, gibt es bewusst nicht.
- Sie ersetzt die Nextcloud nicht als Dateiablage.
- Sie bietet kein gleichzeitiges Bearbeiten wie Google Docs.

Mehrere Personen können Formulare parallel öffnen. Vor dem Speichern prüft die
App den Ausgangsstand. Bei einem Konflikt bleiben die Eingaben erhalten; der
aktuelle Stand muss verglichen und die eigene Eingabe ausdrücklich bestätigt
werden. Verwaltung und JSON-Importvorschau sind ebenfalls geschützt. Details:
[AP03_SCHREIBSCHUTZ.md](docs/AP03_SCHREIBSCHUTZ.md).

## Hinweise zu den Daten

- In `lehrplan/` liegen die **927 Kompetenzerwartungen aller zehn Fächer** der
  Primarstufe NRW, eine Datei je Fach. Sie sind aus dem amtlichen Sammelband
  (RdErl. v. 01.07.2021) gelesen; Herkunft, Kennungen, Export und Import stehen
  in [docs/KOMPETENZDATEN.md](docs/KOMPETENZDATEN.md).
- Die Kompetenzerwartungen sind amtliche Vorgabe und werden nur importiert, nie
  in der App geschrieben. Die einzige Ausnahme ist `schulische_festlegung`:
  dort legt die Schule fest, was bei einem „u. a.“ verbindlich gilt. Diese
  Spalte lässt sich als Tabelle herunterladen, ausfüllen und zurückspielen.
- Der frühere Deutsch-Datensatz hatte 61 Stufen als „zu prüfen“ markiert. Sie
  sind jetzt am Lehrplan-PDF geprüft; neun Angaben wurden berichtigt
  (docs/KOMPETENZDATEN.md).
