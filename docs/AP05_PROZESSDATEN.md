# AP05: Prozessdaten und Graphprüfung

Stand: 31.10.2026. AP05 liefert die Datenbasis des Prozesswerkzeugs. Der schrittweise Editor folgt in AP06, Grafik und geführte Ansicht in AP07 und die durchgängige Veröffentlichung samt Pilot in AP08.

## Vorhandene Wege

Der neue Dokumenttyp **Schulhandbuch** erlaubt `grundlagenkapitel` und `prozess`. Die Administration kann ihn bei **Dokument anlegen** auswählen. Ein Prozess besitzt eine Kennung `PR-…`, Titel sowie die Registry-Felder `anlass` (Anlass und Ziel), `zielgruppe`, `schlagwoerter` und `ablauf`.

Abläufe können über den gemeinsamen Schreibdienst, die Verwaltung und den vorhandenen JSON-Import mit Vorschau angelegt werden. Sie nutzen **Eintrag → Eintragsversion**, den bestehenden Schreibschutz, Suche, Fassungsvergleich und Export. Es entsteht keine zweite Prozesshistorie. Bestehende Dokumente und ihre Eintragstypen bleiben erhalten.

Die normale Eingabemaske zeigt den Ablauf vorerst als lesbaren, nicht bearbeitbaren Text. Änderungen an Titel und Begleitangaben erhalten den gespeicherten Graphen; übermittelte Textfeldwerte ersetzen ihn nicht. Eine leere Prozesshülle ist als Entwurf möglich. Niemand muss für die normale Eingabemaske Diagrammcode oder JSON schreiben. Die bedienbare Schrittbearbeitung ist ausdrücklich noch AP06.

## Ablauf-Schema Version 1

`daten.ablauf` ist ein Objekt mit **genau** `schema_version: 1`, `knoten` und `verbindungen`. Diese Version ist unabhängig vom ebenfalls versionierten äußeren JSON-Importformat.

| Objekt | Felder |
| --- | --- |
| Knoten | `id`, `art`, `titel`, `text` (optional), `funktion` (optional), `bereich` (optional), `verweise` (optional) |
| Verbindung | `id`, `von`, `nach`, `beschriftung` (optional), `ruecksprung` (optional, boolescher Wert) |
| Wissensverweis | `typ: "eintrag"`, `dokument` (stabiler Dokument-Schlüssel), `kennung` (stabile Eintragskennung) |
| Dateiverweis | `typ: "anhang"`, `id` (positive Ganzzahl einer registrierten Anlage) |

Arten: `start`, `handlung`, `entscheidung`, `ende`. Knoten- und Verbindungskennungen sind innerhalb ihrer Liste eindeutig, maximal 64 Zeichen und bestehen aus Buchstaben, Ziffern, Unterstrich und Bindestrich. Umbenennen und Umordnen sollen diese IDs erhalten. Funktion und Bereich verwenden die stabilen Schlüssel aus AP04. Ein Bereich setzt eine Funktion voraus und ist keine Zugriffsrolle.

Grenzen: 200 Knoten, 600 Verbindungen, 250.000 UTF-8-Bytes für den gesamten Graphen, 200 Zeichen je Titel/Zweigbeschriftung, 4.000 Zeichen je Schritterklärung, 20 Ressourcen je Schritt und 400 Ressourcenverweise insgesamt. Unbekannte Felder, doppelte IDs, falsche Datentypen, unbekannte Arten oder Schema-Versionen sind auch im Entwurf Fehler. Die normalisierte Struktur enthält keine Layoutkoordinaten, Personenkopien, ausführbaren Bedingungen oder frei ausführbaren Links.

Die maßgebliche Implementierung liegt in `kern/prozessdaten.py`. Das [ausdrücklich fiktive JSON-Beispiel](beispiele/prozess-ap05.json) erklärt das Format. Zum Importieren wären ein entsprechend benanntes Testhandbuch und eine ausdrücklich als Demo bezeichnete Funktion `demo` erforderlich. Die Migration legt weder dieses Dokument noch Funktionen, Personen oder Verfahren an.

## Entwurf und Freigabe

Strukturell sichere, unvollständige Graphen bleiben als Entwurf speicherbar: etwa ein noch offener Folgeschritt, fehlende Zweige oder ein loser Schritt. Die Prüfung nennt die stabilen Schritt-/Verbindungs-IDs. Beim Übergang auf **abgestimmt** werden diese Hindernisse zu Fehlern.

Vor dem Beschließen wird die **tatsächlich ausgewählte gespeicherte Fassung** erneut geprüft, unabhängig vom aktuellen Status und vom Aufrufweg:

- Anlass und Ziel sowie ein lesbarer Ablauf sind vorhanden.
- Genau ein Start mit einem Ausgang und keinem Eingang; mindestens ein Ende ohne Ausgang.
- Jede Handlung besitzt genau einen Folgeschritt und eine zuständige Funktion.
- Jede Entscheidung besitzt mindestens zwei unterschiedlich beschriftete, verbundene Alternativen. Groß-/Kleinschreibung und äußere Leerzeichen machen gleiche Beschriftungen nicht verschieden.
- Alle Knoten sind vom Start erreichbar; jeder Knoten kann ein Ende erreichen.
- Jede Verbindung hat existierende Quell- und Zielschritte.
- Ohne explizite Rücksprünge ist der Graph azyklisch. Ein Rücksprung ist beschriftet und führt zu einem über Vorwärtskanten vorausgehenden Schritt. Ein beschrifteter Kreis mit einem erreichbaren Ausgang ist erlaubt; ein Kreis ohne Ausgang verhindert die Freigabe.
- Zuständigkeits- und Ressourcenreferenzen sind weiterhin verfügbar; Wissensziele und eintragsgebundene Anlagen besitzen eine Freigabe.

Die gemeinsame Beschlussfunktion und das Versionsmodell schützen die Freigabe. Bei einer ungültigen Auswahl bleibt die gesamte Freigabe unverändert. Das Beschlussformular erhält Eingaben und zeigt die Hindernisse. Frühere gültige Fassungen werden durch einen neuen Entwurf nicht verdrängt.

## Referenzen und Zugriff

Wissensverweise speichern Schlüssel und Kennung, keine fremden Titel. Dateiverweise beziehen sich ausschließlich auf vorhandene, dokument-/eintragsgebundene Anlagen: Upload, Nextcloud-Freigabelink oder registrierter Nextcloud-Pfad. Freie URLs sind kein Bestandteil des Graphschemas. Aktive, nicht archivierte Funktionen und existierende Funktionsbereiche werden serverseitig aufgelöst; eine derzeit unbesetzte Funktion ist zulässig und wird später durch den AP04-Resolver als solche angezeigt.

Interaktive Vorschau, Import und Schreiben prüfen die Rechte des handelnden Kontos. Die Freigabe prüft erneut. Fehlende und unzugängliche Ziele ergeben denselben allgemeinen Hinweis ohne fremden Titel oder Dateinamen. Der reine Graphtext, der Fassungsvergleich und der Prozesssuchtext übernehmen keine fremden Metadaten. Der Index für Lesende stammt weiterhin aus der freigegebenen Fassung. Graphlabels werden als Text ausgegeben und beim HTML-Rendering maskiert.

Zusätzlich zum Graphen erzeugt der Schreibdienst gemeinsame `Verlinkung`-Datensätze mit Feld `prozess_ablauf` und Art `prozess_bezug`. Die gespeicherte Version erhält kanonische Referenzschnappschüsse auch bei einer direkten Versionsanlage. Zieltypen `schulfunktion` und `funktionsbereich` ergänzen die vorhandenen Eintrags- und Anlagenbezüge. Damit bleiben Rückverweise und der vorhandene Löschschutz für Wissenseinträge nutzbar. Referenzen werden bei einer neuen Prozessfassung aktualisiert; alte Fassungen behalten ihre eigenen Bezüge.

Die Funktionsverwaltung zeigt verwendende Prozesse einschließlich früherer Fassungen. Eine in einer gültigen Prozessfassung verwendete Funktion lässt sich erst archivieren, nachdem diese Abläufe geändert wurden. Gemeinsame Funktionssperren sichern dies gegen gleichzeitige Freigaben ab. Auch Sammelfreigaben sperren alle verwendeten Funktionen global in derselben Reihenfolge. Verwendete Bereichsnamen bleiben stabil. Personalwechsel über AP04 verändern Kontakte, keine Prozessfassung.

Registrierte Anlagen werden nach den vorhandenen Zugangsregeln geprüft. AP05 fixiert **keine externen Dateiversionen**. Der erfolgreiche Dateizugriff auf eine echte Nextcloud und die Bindung veränderlicher Dateien an einen verbindlichen Stand bleiben B01/AP09 beziehungsweise die in AP08 vorgesehenen Prüfhinweise. Eine Graphfreigabe ersetzt diese Nachweise nicht.

## Übergabe an AP06

- `normalisieren(graph)`: sichere kanonische Daten oder `ValidationError`.
- `freigabehindernisse(graph)`: Vollständigkeitsmeldungen für einen bereits normalisierten Graphen, mit Schritt-/Verbindungs-ID im Text.
- `referenzen(graph, nutzer=…, freigabe=False)`: gebündelte Ziel-/Rechteprüfung; keine Kontaktkopien.
- `freigabe_pruefen(daten, nutzer=…)`: komplette Prüfung unter einer Funktionssperre; Ergebnis sind die Referenzziele.
- `als_text(graph)`: lesbarer Text aus Eigeninhalten, auch für Vergleich und Export.
- `dienste.pruefen(…, nutzer=…)` und `dienste.speichern(…, nutzer=…, erwarteter_stand=…)`: dieselben Schreibwege wie für andere Einträge.

Der Editor muss die normalisierte Struktur erzeugen, stabile IDs erhalten, den bestehenden Ausgangsstand übergeben und Fehlermeldungen den Schritten zuordnen. Die bisher nur lesbare Formularkomponente für `Feldtyp.PROZESSGRAPH` wird dabei durch die Schrittbearbeitung ersetzt. Grafik und Text dürfen keine getrennten Kopien werden. Personen und erlaubte Verweisdetails sind beim Lesen frisch nach Nutzerrechten aufzulösen. Zuständige Funktionen eines Handlungsschritts und die redaktionelle Verantwortung für einen Wissenseintrag bleiben verschieden.

Migration: `0011_prozessgrundlage`. Sie ergänzt ausschließlich Typdefinitionen und den Schulhandbuch-Dokumenttyp; kein Bestandsdokument wird umgewandelt.

## Abnahme und Darstellungsnachweise

Im Gesamtlauf bestanden 537 Tests; die einzige fehlgeschlagene Prüfung erwartete noch die alte Liste der Eintragstypen. Nach Ergänzung von `prozess` und den abschließenden Prüfungen bestanden alle **89 betroffenen Tests**, davon **54 AP05-Fälle**. Enthalten sind echte Paralleltests für Freigabe gegen Funktionsarchivierung und zwei Sammelfreigaben mit unterschiedlicher Funktionsreihenfolge. Ruff, Django-Systemprüfung und Migrationsabgleich sind grün.

Die Browserprüfung umfasst 390/768/1024/1440 Pixel, Tastatur, Hell/Dunkel und axe ohne Befund. Die Demonstrationsobjekte wurden ausschließlich im Speicher gerendert; es wurden keine Schulabläufe oder Funktionen für Screenshots angelegt.

- Leseansicht: [1440](screenshots/12-ap05-lesen-demo-1440.png), [768](screenshots/12-ap05-lesen-demo-768.png).
- Begleitangaben mit erhaltener Ablaufstruktur: [1440](screenshots/12-ap05-metadaten-demo-1440.png), [768](screenshots/12-ap05-metadaten-demo-768.png).
- Fassungsvergleich: [1440](screenshots/12-ap05-vergleich-demo-1440.png), [768](screenshots/12-ap05-vergleich-demo-768.png).
