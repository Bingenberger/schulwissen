# Schulwissen ausprobieren

Diese Anleitung führt dich durch die Funktionen der Phasen 1 bis 3.
Du brauchst nur Docker.

## Vorbereiten

```bash
cd /home/foerster_schule/Schulwissen
docker compose up -d --build
docker compose exec app python manage.py seed_demo
```

`seed_demo` legt Rollen, fünf Arbeitsgruppen, vier Demo-Konten, den Arbeitsplan
Deutsch mit vollständiger Gliederung, alle 117 Kompetenzerwartungen und die
beiden Beispielzeilen der Arbeitsmappe an.

Die App läuft dann auf **<http://127.0.0.1:8001>**.

| Konto | Rolle | Passwort |
| --- | --- | --- |
| `leitung@example.org` | Administration | `schulwissen-demo-2026` |
| `fachvorsitz@example.org` | Redaktion | `schulwissen-demo-2026` |
| `lehrkraft@example.org` | Lehrkraft (Jahrgang 3) | `schulwissen-demo-2026` |
| `ogs@example.org` | Lesend | `schulwissen-demo-2026` |

> `seed_demo` läuft nur mit `SW_DEBUG=true`. Auf dem Server verweigert es den
> Dienst – Demo-Konten mit bekanntem Passwort gehören nicht in den Echtbetrieb.

## 1. Der Weg einer Lehrkraft (das Wichtigste)

Melde dich als **`lehrkraft@example.org`** an.

1. **Startseite.** Der Blick fällt auf ein großes Suchfeld, das den Fokus hat.
   Darunter steht nur das Nötigste. (Die Suche selbst kommt in Phase 2.)
2. Klicke auf **Arbeitsplan Deutsch**. Links steht die Gliederung nach
   QUA-LiS: 1 Rahmenbedingungen, 2 Entscheidungen zum Unterricht mit 2.1 bis
   2.5, 3, 4 und A Anhang.
3. Klicke oben auf **„Unterrichtsvorhaben anlegen“**.

   Achte auf:
   - die Blöcke *Überblick · Kompetenzen · Zeit · Unterricht · Leistung ·
     Sonstiges*, wobei **Leistung** farbig abgesetzt ist;
   - den Hinweis **„Speichern geht immer“** über dem Formular;
   - die roten Sternchen an den Pflichtfeldern;
   - die Hilfetexte unter jeder Beschriftung – sie stammen aus dem Blatt
     „Felddefinitionen“ der Arbeitsmappe.

4. **Wähle bei „Jahrgang“ die 3.** Jetzt erscheint unten im Block *Leistung*
   das Feld **Klassenarbeit** – vorher war es nicht da. Stelle auf 1 zurück:
   es verschwindet wieder. (Klassenarbeiten gibt es erst ab Klasse 3.)

5. **Kompetenzen wählen.** Tippe im Block *Kompetenzen* bei „Kompetenzen
   Schwerpunkt“ `Märchen` ein. Nach kurzem Zögern erscheinen Treffer im
   Klartext, die Kennung steht als blaues Schild davor. Klicke einen an – er
   wandert nach oben zu den gewählten Kompetenzen und lässt sich mit dem ×
   wieder entfernen.

   Probiere auch:
   - `SC2.02` – Suche über die Kennung;
   - `Gesprch` (mit Tippfehler) – wird trotzdem gefunden;
   - `Gedicht` – zwei Treffer;
   - die Filter **Bereich** und **Stufe**.

   > `Märchen` liefert hier bewusst **nichts**: keine Kompetenzerwartung des
   > Lehrplans handelt von Märchen. Lieber keine Treffer als vierzig falsche,
   > von denen eine angehakt wird.

6. **Formatierten Text schreiben.** Klicke im Feld „Didaktische Zugänge /
   Methoden“ in die weiße Fläche. Über dem Feld steht eine Werkzeugleiste:
   Fett, Kursiv, Überschriften, Listen und **Tabelle**. Füge eine Tabelle ein –
   in den Grundlagenkapiteln braucht ihr die.

7. Fülle Titel und Kurzbeschreibung aus und klicke **Speichern**.

   Die App vergibt die Kennung selbst: **V-3-01**, mit dem Jahrgang darin. Du
   landest in der Leseansicht. Oben steht in Gelb, welche Pflichtfelder für
   „abgestimmt in Gruppe“ noch fehlen.

8. **Unvollständig speichern geht.** Lege ein zweites Vorhaben an, trage nur
   den Titel ein und speichere. Es wird gespeichert, und eine Meldung sagt,
   was noch fehlt. Niemand muss am Ganztag alles auf einmal ausfüllen.

## 2. Fassungen und Unveränderlichkeit

Noch als Lehrkraft:

1. Öffne **V-3-01**, klicke **Bearbeiten**, ändere den Titel, speichere.
2. Klicke rechts bei „Fassungen“ auf die Zahl. Es stehen jetzt **zwei**
   Fassungen da, mit Autor und Zeitpunkt.

Jede Speicherung erzeugt eine Fassung. Ein Beschluss macht später genau eine
davon gültig; die bleibt dann unveränderlich, und Bearbeiten erzeugt einen
neuen Entwurf.

## 3. Rechte ausprobieren

Melde dich ab und als **`ogs@example.org`** (Rolle *Lesend*) wieder an.

- Die Startseite zeigt keine Entwürfe.
- Rufe <http://127.0.0.1:8001/d/arbeitsplan-deutsch/V-3-01> auf: **403**.
  Entwürfe sind für Lesende nicht freigegeben.

Als **`lehrkraft@example.org`**:

- **V-3-01** (Jahrgang 3, also ihre Arbeitsgruppe) lässt sich bearbeiten.
- **R-01 Lesezeit** hat keine Arbeitsgruppe – dort gibt es keinen Knopf
  „Bearbeiten“. Daran kommt nur die Redaktion.

Als **`fachvorsitz@example.org`** (Rolle *Redaktion*) ist beides bearbeitbar,
und im Auswahlfeld „Status“ steht zusätzlich **abgestimmt in Gruppe**. Wähle
es bei einem unvollständigen Vorhaben: die App verweigert es und nennt genau
die fehlenden Felder.

## 4. Abdeckungsmatrix – die Probe aufs Exempel

Als beliebiges Konto: links unten **Abdeckungsmatrix**.

Vergleiche die Tabelle „Je Schwerpunkt“ mit dem Blatt **Übersicht** der
Arbeitsmappe. Wenn nur die beiden Beispielzeilen importiert sind, muss
zeilenweise dasselbe herauskommen:

| | Erwartungen | mit Schwerpunkt | nur berührt | fehlt |
| --- | --- | --- | --- | --- |
| SZ 2 Vor anderen sprechen | 8 | 0 | 2 | 6 |
| SC 2 Schreibstrategien … | 9 | 3 | 1 | 5 |
| LE 1 Über Lesefähigkeiten … | 10 | 4 | 0 | 6 |
| **Gesamt** | **117** | **10** | **8** | **99** |

Grün heißt Schwerpunkt, Gelb nur berührt, Rot fehlt. Mit **„Nur beschlossene“**
springt alles auf Rot – beschlossen ist ja noch nichts.

> Das prüft auch die Testabdeckung: `tests/test_abdeckung.py` vergleicht alle
> 14 Schwerpunkte mit den Werten aus dem Blatt „Übersicht“.

## 5. Prüfliste

Links unten **Prüfliste**. Dort stehen

- **20 Erwartungen ohne schulische Festlegung** – der Lehrplan sagt „u. a.“,
  die Schule muss festlegen, welcher weitere Inhalt bei euch verbindlich ist;
- **61 Erwartungen, deren Stufe zu prüfen ist** (SPEC.md nennt 58; es gilt die
  gelieferte Datei).

Als Redaktion oder Administration lässt sich die Festlegung unter
`/verwaltung/fachdaten/kompetenzerwartung/` eintragen – alle anderen Spalten
sind dort nur lesbar, denn sie sind amtliche Vorgabe.

## 6. Die Suche (Phase 2)

Melde dich als **`lehrkraft@example.org`** an.

### Autovervollständigung

Tippe oben im Suchfeld `Märchen`. Nach kurzem Zögern klappt eine Liste auf:
Kennung, Titel, darunter der Weg dorthin. Das funktioniert auf jeder Seite.
Mit **Esc** schließt die Liste, mit **Eingabe** kommst du zur Ergebnisseite.

Probiere auch `V-3` (Kennung) und `SC2.02` (Kompetenz).

### Die Abnahme aus SPEC.md §13

Damit das klappt, braucht es eine Datei mit Inhalt. Lege sie schnell an:

```bash
docker compose exec app python manage.py shell -c "
from kern.models import Anhang, Eintrag
from eintragstypen.dienste import suchtext_aktualisieren
v = Eintrag.objects.get(kennung='V-3-01')
Anhang.objects.get_or_create(eintrag=v, dateiname='Merkmale von Maerchen.pdf',
  defaults=dict(mimetype='application/pdf', beschreibung='Übersicht für die Kinder',
  extrahierter_text='Merkmale von Märchen: Es war einmal, Gut und Böse, ein gutes Ende.'))
k = Eintrag.objects.get(kennung='2.4')
k.daten = {'text': '<p>Das selbst geschriebene Märchen wird nach den Kriterien aus dem Märchenraster bewertet.</p>'}
k.save(); suchtext_aktualisieren(k); suchtext_aktualisieren(v)
print('bereit')"
```

Suche jetzt nach **`Märchen`**. Die Ergebnisseite muss drei Dinge zeigen:

1. das Vorhaben **V-3-01**,
2. das Kapitel **2.4 Leistungsbewertung**,
3. die Datei **Merkmale von Maerchen.pdf**.

Die Treffer sind gruppiert, die Fundstellen gelb hervorgehoben, darunter steht
jeweils der Weg („Arbeitsplan Deutsch › 2 › 2.1“).

### Was die Suche sonst noch kann

| Eingabe | Was passiert |
| --- | --- |
| `Märchens` | findet „Märchen“ – deutsche Stammformen |
| `Maerchen` | Tippfehler; die App sagt „ähnlich geschrieben“ |
| `Es war einmal` | nur Füllwörter; die App sucht nach dem genauen Wortlaut und sagt das |
| `"Gut und Böse"` | Wortgruppe in Anführungszeichen |
| `Märchen -Hörspiel` | schließt ein Wort aus |

Unter **Filter** lässt sich nach Dokument, Status, Jahrgang und Fach
einschränken.

> **Probe:** Suche `Märchen` und sieh dir die Gruppe *Kompetenzerwartungen* an.
> Sie muss **leer** sein – keine Kompetenzerwartung des Lehrplans handelt von
> Märchen. Erschiene dort eine lange Liste, wäre die Ähnlichkeitsschwelle zu
> niedrig (siehe README).

## 7. Beschlüsse

Als **`fachvorsitz@example.org`** (Redaktion):

1. Öffne **V-3-01**, klicke *Bearbeiten*, setze den Status auf
   **„abgestimmt in Gruppe“** und speichere. Geht nur, wenn alle Pflichtfelder
   gefüllt sind – sonst nennt die App die fehlenden.
2. Gehe auf **Beschlussvorlage** (Startseite oder linke Navigation). Dort steht
   jetzt V-3-01.

Als **`leitung@example.org`** (Administration):

3. Öffne die **Beschlussvorlage**, lass das Häkchen stehen und klicke
   **„Beschluss eintragen“**.
4. Trage Datum (9.11.2026), Gremium (Fachkonferenz Deutsch), Titel und Text ein
   und speichere.

Öffne danach **V-3-01**: oben steht grün
*„Gilt seit Beschluss der Fachkonferenz Deutsch vom 09.11.2026“*.

### Die beschlossene Fassung ist unveränderlich

5. Bearbeite V-3-01 erneut, ändere den Titel, speichere.
6. Der Eintrag zeigt jetzt **beides**: den Beschluss *und* den Hinweis
   „Angezeigt wird der Arbeitsstand“ mit Link auf die Unterschiede.
7. Melde dich als **`ogs@example.org`** (Lesend) an und öffne V-3-01:
   Du siehst den **beschlossenen** Titel, nicht den Entwurf, dazu den Hinweis,
   dass es einen neueren Entwurf gibt.

Das ist der Kern von SPEC.md §6: Lesende sehen, was gilt – nicht, woran gerade
gearbeitet wird.

### Vergleich und Änderungen

- **Fassungen → Vergleich**: wortweise Gegenüberstellung, Entferntes rot,
  Hinzugefügtes grün. Oben lassen sich beliebige zwei Fassungen wählen.
- **Änderungen seit Beschluss** (linke Navigation): was ist neu, was wurde seit
  der beschlossenen Fassung geändert, was ist unverändert.

## 8. Die Auswertungen

Alle sieben hängen in der linken Navigation unter *Auswertungen*. Oben auf
jeder Seite lässt sich zwischen **„Inklusive Entwürfe“** und **„Nur
beschlossene“** umschalten.

| Auswertung | Worauf achten |
| --- | --- |
| **Abdeckungsmatrix** | Stimmt mit dem Blatt „Übersicht“ überein (siehe unten) |
| **Fahrplan je Jahrgang** | Vorhaben nach Quartal, darunter die Rituale mit der Ausprägung *dieses* Jahrgangs |
| **Ritual-Progression** | R-01 mit allen vier Jahrgängen nebeneinander; Jg. 2 und 3 sind rot, weil in der Mappe `[…]` steht |
| **Zeitbudget** | R-01 bindet 60 Min./Woche; Jg. 1 hat 6 Stunden à 45 Min. = 270 Min., also 22,2 % |
| **Leistungsübersicht** | Die Sicht „Leistungskonzept“: Überprüfungen und Klassenarbeiten je Jahrgang |
| **Progressionspaare** | 26 Paare; die meisten rot, weil erst zwei Einträge erfasst sind |
| **Prüfliste** | 20 offene schulische Festlegungen, 61 zu prüfende Stufen |

## 9. Nextcloud

Ohne Zugangsdaten erklärt die App das freundlich: Öffne einen Eintrag, rechts
**„Nextcloud durchsuchen“**. Mit eingetragenem Zugang (DEPLOYMENT.md §6)
lassen sich Ordner durchklicken und Dateien verlinken – die Datei bleibt in der
Nextcloud.

## 10. Import mit Vorschau

```bash
docker compose exec app python manage.py arbeitsplan_importieren \
    Datenmodell_Arbeitsplan_Deutsch.xlsx --vorschau --mit-beispielen
```

Die Ausgabe nennt je Datensatz die Zeile der Arbeitsmappe, ob er neu ist oder
aktualisiert wird, und was auffällt – bei `R-01` zum Beispiel die vier noch
offenen Pflichtfelder, weil in der Mappe dort `[…]` steht.

**Die Vorschau schreibt garantiert nichts.** Prüfen lässt sich das so:

```bash
docker compose exec app python manage.py shell -c \
  "from kern.models import Eintrag; print(Eintrag.objects.count())"
```

Die Zahl ist vor und nach der Vorschau gleich.

## 11. Phase 3 ausprobieren

### Persönliche Planung

1. Als Lehrkraft **Meine Planung** öffnen.
2. Arbeitsplan, Klasse „3b“ und Schuljahr „2026/27“ wählen, **Fahrplan anzeigen**.
3. Ein Vorhaben abhaken, eine Notiz ergänzen und speichern.
4. Seite neu laden: Häkchen und Notiz bleiben erhalten.
5. Klasse oder Schuljahr wechseln: der Fortschritt ist getrennt.
6. Mit einer anderen Lehrkraft anmelden: die Notiz des ersten Kontos ist
   nicht sichtbar. Ein lesendes Konto hat keinen Zugang zur Planung.

### Konzepte und Protokolle

1. Als Administration auf der Startseite **Dokument anlegen** wählen.
2. Ein Konzept mit dem Schlüssel „medienkonzept“ anlegen und ein Kapitel ergänzen.
3. Ein Konferenzprotokoll anlegen. Im automatisch erzeugten Protokollkopf Datum
   und Gremium eintragen; einen Tagesordnungspunkt mit Beratung und Beschlusstext
   ergänzen.
4. Einträge wie gewohnt abstimmen und per tatsächlichem Beschluss freigeben.
   Beim Beschluss kann ein Protokolleintrag zugeordnet werden.

### Exporte und generischer Import

1. Als Administration die Dokumentseite öffnen: **JSON exportieren** und beim
   Arbeitsplan **Excel exportieren** herunterladen.
2. **JSON importieren** öffnen und den JSON-Export hochladen. Die Vorschau
   schreibt nichts; erst die ausdrückliche Übernahme erzeugt neue Fassungen.
3. Die Excel-Datei mit dem bekannten Importkommando zuerst per `--vorschau`
   prüfen; Verweise und Rich Text bleiben beim Rundlauf erhalten.
4. **Beschlossenen Stand als PDF** herunterladen. Deckblatt, Inhaltsverzeichnis,
   beschlossene Kapitel/Steckbriefe und Abdeckungsmatrix prüfen.
5. Einen beschlossenen Inhalt als Entwurf ändern und PDF erneut herunterladen:
   im PDF steht weiterhin der gültige Inhalt.
6. Als Redaktion eine **Beschlussvorlage** öffnen, abgestimmte Einträge auswählen
   und **Auswahl als PDF herunterladen** wählen. Das PDF zeigt auch Unterschiede
   zum bisherigen Beschluss.
7. Eine JSON-Datei nach [JSON-IMPORT.md](JSON-IMPORT.md) mit unbekannter Kompetenz
   oder zyklischer Gliederung hochladen: der gesamte Import wird abgewiesen.

## 12. Phase 4 ausprobieren

1. Als Administration **Dokument anlegen** öffnen: „Arbeitsplan“ wählen und
   die Fachauswahl mit allen neun Fächern prüfen.
2. **Kompetenzen** öffnen und das Fach umschalten. Für Deutsch stehen die
   vorhandenen Erwartungen zur Verfügung; andere Fächer werden erst nach
   ihrem Lehrplanimport gefüllt.
3. Die echte Nextcloud-Anmeldung und Indexierung benötigen die Einrichtung
   aus [PHASE4.md](PHASE4.md). Ohne Konfiguration bleibt die lokale Anmeldung
   verfügbar und es wird keine Verbindung zur Nextcloud aufgebaut.

## 13. Tests

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml \
    run --rm werkzeug pytest
```

Rund zwei Minuten, dann müssen alle Tests grün sein.

## Aufräumen

```bash
docker compose down            # App anhalten, Daten bleiben
docker compose down -v         # Daten ebenfalls löschen
```
