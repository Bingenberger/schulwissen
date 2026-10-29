# Phase 1 ausprobieren

Diese Anleitung führt dich durch alles, was Phase 1 kann – in etwa 20 Minuten.
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
   - die Filter **Bereich** und **Stufe**.

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

## 6. Import mit Vorschau

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

## 7. Tests

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
