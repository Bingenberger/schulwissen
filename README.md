# Schulwissen-Plattform der GGS Niederkassel

Arbeitspläne, Konzepte und Konferenzbeschlüsse als **strukturierte, verlinkte und
durchsuchbare Einträge** statt als Word-Dateien in der Nextcloud. Das Kollegium
schreibt direkt in der App; Entwürfe werden erst per Konferenzbeschluss gültig.

Erster Anwendungsfall ist der **Arbeitsplan Deutsch** inklusive Leistungskonzept,
der ab dem pädagogischen Ganztag am 9.11.2026 erarbeitet wird.

Die vollständige fachliche Beschreibung steht in [SPEC.md](SPEC.md).

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
über Nextcloud und Fachverwaltung für alle neun benötigten Fächer. Die
Live-Verbindungen benötigen die Nextcloud-Konfiguration; weitere amtliche
Kompetenzdaten müssen fachweise importiert werden.
Einrichtung und Abnahme stehen in [PHASE4.md](PHASE4.md).
Das JSON-Importformat und die Exportgrenzen stehen in [JSON-IMPORT.md](JSON-IMPORT.md).

## Geplante Weiterentwicklung

Die [Roadmap](ROADMAP.md) übersetzt die
[Analyse des Grundschulalltags](docs/PRODUKTANALYSE_GRUNDSCHULE.md) in
priorisierte Arbeitspakete mit Abhängigkeiten und Abnahmekriterien für kommende
Coding-Sitzungen. AP01 (einheitliche Lesefassungen) und AP02
(Dokumentzugänge und redaktionelle Bereiche) sind umgesetzt;
nächster Einstieg ist **AP03**. Den ersten großen Ausbau bildet
das [Prozesswerkzeug](docs/PROZESSWERKZEUG.md): Abläufe definieren, als
„Was passiert, wenn …?“-Grafik anzeigen und zuständige Schulfunktionsrollen mit
Personen aus dem vorhandenen Nutzerstamm besetzen. Diese Erweiterungen sind
geplant und noch nicht umgesetzt. Die Abnahme von AP01 steht in
[AP01_LESEFASSUNGEN.md](docs/AP01_LESEFASSUNGEN.md).

## Schnellstart

Voraussetzung: Docker mit Compose-Plugin (`docker compose version`).

```bash
cp .env.example .env
nano .env                 # SW_SECRET_KEY und POSTGRES_PASSWORD setzen
chmod 600 .env

docker compose up -d --build
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
| `fachdaten/` | Kompetenzerwartungen des Lehrplans, ihr Import und ihre Suche |
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
# Kompetenzerwartungen (idempotent; schulische Festlegungen bleiben erhalten)
docker compose exec app python manage.py kompetenzen_importieren \
    kompetenzerwartungen_lp2021.json

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

## Hinweise zu den Daten

- Die Datei `kompetenzerwartungen_lp2021.json` enthält **61** Erwartungen mit
  `stufePruefen = true`; SPEC.md §16 nennt 58. Es gilt die Datei. Die Prüfliste
  in der App zeigt alle 61.
- Die Kompetenzerwartungen sind amtliche Vorgabe (Lehrplan Deutsch Primarstufe
  NRW, RdErl. v. 01.07.2021) und werden nur importiert, nie in der App
  geschrieben. Die einzige Ausnahme ist `schulische_festlegung`.
