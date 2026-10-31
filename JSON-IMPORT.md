# JSON-Import und Export

Einträge können in jedes vorhandene Dokument importiert werden. Die Administration
legt das Dokument auf der Startseite über **Dokument anlegen** an und öffnet dort
**JSON importieren**. Eine hochgeladene UTF-8-Datei wird zuerst geprüft. Erst
**Geprüfte Einträge übernehmen** schreibt die Daten; die gesamte Datei wird erneut
validiert. Bei einem Fehler wird nichts übernommen.

Alternativ auf der Kommandozeile:

    docker compose exec app python manage.py eintraege_importieren konzept.json --vorschau
    docker compose exec app python manage.py eintraege_importieren konzept.json

## Format

```json
{
  "dokument": "medienkonzept",
  "eintraege": [
    {
      "kennung": "1",
      "eintragstyp": "grundlagenkapitel",
      "titel": "Ziele",
      "status": "entwurf",
      "eltern": null,
      "position": 10,
      "daten": {
        "text": "<p>Unsere verbindlichen Ziele.</p>"
      }
    },
    {
      "kennung": "1.1",
      "eintragstyp": "grundlagenkapitel",
      "titel": "Umsetzung",
      "eltern": "1",
      "position": 10,
      "daten": {
        "text": "<p>So setzen wir die Ziele um.</p>"
      }
    }
  ]
}
```

`dokument` ist der dauerhafte Schlüssel aus der Dokumentadresse. `eintraege`
ist eine Liste. Pro Eintrag sind `kennung`, `eintragstyp` und `titel` erforderlich.
`daten` enthält ausschließlich die Felder des registrierten Eintragstyps.
Rich Text ist HTML und wird wie bei der Eingabemaske gesäubert.

| Feld | Verhalten |
| --- | --- |
| `kennung` | Text, 1–40 Zeichen; eindeutig innerhalb der Datei und des Dokuments |
| `eintragstyp` | Muss im Dokumenttyp erlaubt sein; der Typ vorhandener Kennungen bleibt gleich |
| `titel` | Text, höchstens 300 Zeichen, nicht leer |
| `status` | `idee`, `entwurf` (Standard), `abgestimmt`, `beschlossen`, `archiviert` |
| `daten` | Objekt mit den typspezifischen Daten; ersetzt die bisherigen Daten dieses Eintrags |
| `eltern` | Kennung im selben Dokument; `null` setzt den Eintrag auf die oberste Ebene; weggelassen bleibt die Zuordnung bestehen |
| `position` | Nichtnegative ganze Zahl für die Reihenfolge unter demselben Elternkapitel |
| `verantwortlich_text` | Optionaler Freitext, höchstens 200 Zeichen |
| `fassung_stand` | Optionales Datum `JJJJ-MM-TT` |

Verweise stehen **neben** `daten`, als Listen lesbarer Kennungen:

```json
{
  "dokument": "arbeitsplan-deutsch",
  "eintraege": [
    {
      "kennung": "V-3-11",
      "eintragstyp": "vorhaben",
      "titel": "Märchenwerkstatt",
      "daten": {
        "jahrgang": 3,
        "quartal": "Q2",
        "kurzbeschreibung": "Ein eigenes Märchenbuch schreiben"
      },
      "kompetenzen_schwerpunkt": ["SC2.02D"],
      "kompetenzen_beruehrt": [],
      "bezug_rituale": ["R-01"],
      "eltern": "2.1"
    }
  ]
}
```

Ziele dürfen später in derselben Datei stehen. Kompetenzen müssen vorher
importiert sein. Doppelte Kennungen, unbekannte Felder oder Ziele und Kreise in
der Gliederung brechen den Import ab. Eine leere Verweisliste entfernt diese
Verweise; ein fehlendes Verweisfeld lässt sie bestehen.

Unvollständige Entwürfe sind erlaubt und werden mit Warnungen gemeldet.
`abgestimmt` erfordert vollständige Pflichtfelder. `beschlossen` und `archiviert`
werden als `abgestimmt` übernommen; eine Freigabe entsteht ausschließlich über
einen neuen Beschluss. Änderungen an aktuell beschlossenen Einträgen erzeugen
einen neuen Entwurf und lassen die gültige Fassung bestehen.

## Dokumenttypen

| Dokumenttyp | Eintragstypen und Datenfelder |
| --- | --- |
| `konzept` | `grundlagenkapitel`: `text` (Rich Text), `bemerkungen` |
| `protokoll` | `protokollkopf`: `datum` (Datum), `gremium` (Text), `text` (Rich Text) |
| `protokoll` | `tagesordnungspunkt`: `text`, `beschluesse` (beides Rich Text) |
| `arbeitsplan_deutsch` | `grundlagenkapitel`, `ritual`, `vorhaben`; Felder gemäß SPEC.md §7.4 und `deutsch/eintragstypen.py` |

Für das Prozesswerkzeug gibt es eine [fiktive Demo mit zwei Importdateien](docs/AP08_PROZESSVEROEFFENTLICHUNG.md#fiktive-demo-vorbereiten). Zuerst Material importieren und freigeben, danach den darauf verweisenden Prozess. Die Schulfunktion muss bereits vorhanden sein; eine Veröffentlichung erfolgt anschließend ausdrücklich über die Freigabemaske.

Beim Anlegen eines Konferenzprotokolls entsteht ein leerer Protokollkopf.
Tagesordnungspunkte können über die App oder per Import ergänzt werden.
Beim Eintragen eines tatsächlichen Beschlusses kann ein Protokolleintrag
zugeordnet werden; Text im Protokoll allein schaltet keine Inhalte frei.

## Wissensangaben (AP09)

Optional enthält ein Eintrag `wissensangaben` mit `aufgabe`, `kurzantwort`, `suchbegriffe`, `inhaltsart`, `verbindlichkeit`, `wirksam_ab`, `wirksam_bis`, `geprueft_am`, `pruefen_am`, `quelle`, `pflege_funktion`, `pflege_vertretung` und `ersetzt_durch`. Datumswerte sind ISO-Daten oder `null`. Funktionen verwenden vorhandene aktive Schlüssel; Nachfolger sind Objekte mit `dokument` und `kennung`. Beide Ziele müssen bereits vorhanden und zugänglich sein. Fehlende Wissensangaben bleiben beim Import unverändert. Änderungen erzeugen Arbeitsstände und keine Freigaben. Details und Grenzen: [AP09_WISSENSPFLEGE.md](docs/AP09_WISSENSPFLEGE.md).

## Export und Rundlauf

Die Administration findet PDF-, JSON- und (im Arbeitsplan Deutsch)
Excel-Download auf der Dokumentseite.

- **PDF:** ausschließlich beschlossene Fassungen, mit Beschlussherkunft,
  Deckblatt, Inhaltsverzeichnis und beim Arbeitsplan der Abdeckungsmatrix aus
  genau diesen Fassungen. Spätere Entwürfe verändern den Export nicht.
- **JSON:** `schema_version: 1`, Dokumentmetadaten, aktueller Arbeitsstand aller
  Einträge, Gliederung, Verweise, Fassungen und zugehörige Beschlüsse sowie
  Anhang-Metadaten. Persönliche Planung bleibt privat und ist nicht enthalten.
- **XLSX:** Blätter `Rituale` und `Vorhaben` mit den bekannten Spaltennamen.
  Verweise sind durch Semikolon getrennt. Formatierter Text wird als HTML in
  den Zellen erhalten; der Import versteht sowohl dieses HTML als auch
  herkömmlichen Klartext. Berechnete Felder werden beim Import neu berechnet.

Der JSON-Export kann als Quelle eines Inhaltsimports verwendet werden.
`metadaten`, `beschluesse`, Anhang-Metadaten, rohe `verlinkungen` und historische
`fassungen` sind Archivinformationen und werden dabei nicht wiederhergestellt.
Der Import übernimmt die aktuellen Inhalte und die benannten Verweisfelder,
erzeugt neue Fassungen und ersetzt keine Beschlusshistorie. Beim Import in ein
anderes vorhandenes Dokument muss der Wurzelwert `dokument` angepasst werden.
Die Datei enthält keine Anhang-Binärdaten und ersetzt daher keine vollständige
Sicherung von PostgreSQL und Medienverzeichnis (siehe DEPLOYMENT.md §8).

Eine **Beschlussvorlage als PDF** laden Redaktion und Administration über
**Beschlussvorlage → Einträge auswählen → Auswahl als PDF herunterladen**.
Sie enthält die ausgewählten abgestimmten Einträge und, soweit vorhanden,
deren Änderungen gegenüber dem letzten Beschluss.

## Prozesse im Schulhandbuch (AP05)

Der Eintragstyp `prozess` besitzt `anlass`, `zielgruppe`, `schlagwoerter` und den
strukturierten Wert `daten.ablauf` mit eigener `schema_version: 1`. Unvollständige,
strukturell sichere Abläufe bleiben als Entwurf importierbar. Doppelte IDs,
unzulässige Ziele und unbekannte Schema-Versionen verhindern jede Übernahme.
Zum Abstimmen und Beschließen müssen alle Graphprüfungen erfüllt sein.

Das [Schema und die Grenzen](docs/AP05_PROZESSDATEN.md) sowie ein
[fiktives Beispiel](docs/beispiele/prozess-ap05.json) beschreiben den Vertrag.
Vorhandene Schulfunktionen werden über stabile Schlüssel referenziert; sie
werden beim Dokumentimport nicht automatisch angelegt oder mit Personen besetzt.
Wissensverweise verwenden Dokument-Schlüssel und Eintragskennung. Anlagen-IDs
beziehen sich auf den vorhandenen Datenbestand. Ein Dokumentexport überträgt keine
Nutzerkonten und ist keine automatische Neuinstallation aller externen Ressourcen.

Die [AP10-Aufnahmevorlage](docs/beispiele/ap10-aufnahmeplan.json) enthält zehn ausdrücklich unvollständige Aufnahmeentwürfe. Sie setzt ein passendes Schulhandbuch voraus, veröffentlicht nichts und ersetzt keine fachliche Bestätigung. Aufgaben verwenden die in der Wissensangaben-Maske angebotenen Schlüssel. Kurzantworten sind auf 600, Suchbegriffe auf 500 Zeichen begrenzt.
