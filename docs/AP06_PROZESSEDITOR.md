# AP06: Prozesse ohne Diagrammcode bearbeiten

Stand: 31.10.2026. AP06 ergänzt den bedienbaren Autoreneditor zur [Prozessdatenbasis](AP05_PROZESSDATEN.md). Er nutzt die bestehende Registry, Formulare, Eintragsversionen und den gemeinsamen Schreibschutz. Die lesbare Ablaufgrafik und geführte Ansicht für das Kollegium sind seit [AP07](AP07_PROZESSLESEN.md) vorhanden; der fachliche Pilot bleibt AP08.

## Einen Ablauf erstellen

1. Die Administration legt bei Bedarf ein Dokument vom Typ **Schulhandbuch** an und richtet die tatsächlichen Schulfunktionen samt Besetzungen in der Verwaltung ein. Es werden keine fiktiven Zuständigkeiten automatisch angelegt.
2. Im Handbuch **Eintrag anlegen → Prozess anlegen** öffnen. Titel und **Anlass und Ziel** eintragen; Zielgruppe und Schlagwörter sind optional.
3. Unter **Ablauf bearbeiten** eine Schrittart wählen und **Schritt hinzufügen** drücken. Zur Auswahl stehen Start, Handlung, Entscheidung und Ende. Frage beziehungsweise Schritttitel und eine Erklärung eingeben.
4. Bei Handlungen die zuständige Funktion wählen. Der optionale Geltungsbereich beschreibt die Zuständigkeit und vergibt keine Zugriffsrechte. Die Kontaktvorschau zeigt die Besetzung beim Öffnen des Editors, einschließlich bewusster Vertretung oder Vakanz. Ein nicht besetzter benannter Bereich fällt nicht stillschweigend auf die allgemeine Zuständigkeit zurück.
5. Unter **Danach weiter** beziehungsweise **Antwortzweige** den passenden Folgeschritt auswählen. Entscheidungen starten mit **Ja** und **Nein**; weitere Antworten sind möglich. Rücksprünge bewusst kennzeichnen und verständlich beschriften, etwa „Erneut prüfen“.
6. Optional vorhandenes Wissen oder registrierte Dateien suchen und verknüpfen. Treffer und gespeicherte Zielbeschriftungen richten sich nach den Zugriffsrechten. Ein nicht verfügbarer Verweis wird neutral angezeigt und kann korrigiert oder entfernt werden. Wissens- oder Datei-Metadaten werden nicht in den Prozess kopiert.
7. **Ablauf prüfen** zeigt offene Angaben. Schritthinweise führen direkt zu den zugehörigen Feldern. Die Prüfung speichert nichts und ändert keinen Status.
8. Über **Als Entwurf speichern** auch unvollständige Abläufe sichern. Ein vollständiger Ablauf kann wie andere Einträge fachlich abgestimmt werden. Beschlossen wird er weiterhin ausschließlich über den vorhandenen Freigabeweg.

Die Eingabe verlangt weder JSON noch Mermaid. Ohne JavaScript bleibt der bestehende Graph im versteckten Formularwert erhalten; zum Bearbeiten der Schritte ist JavaScript erforderlich. Ein fehlender oder beschädigter Graphwert wird nicht stillschweigend durch einen leeren Ablauf ersetzt.

## Schritte, Vorschau und Fehler

Die Schrittliste und die Grafik wählen dieselben bearbeitbaren Felder aus. **Zur Vorschau** springt zur automatisch aktualisierten Grafik. Auswahl eines Grafikknotens führt zurück zum jeweiligen Schritt. Eine Textalternative zeigt dieselben Schritte und Verbindungen. Bei größeren Graphen lässt sich die Vorschau innerhalb ihres eigenen Bereichs verschieben; die Formularfelder bleiben ohne Drag-and-drop bedienbar.

**Schritt nach oben/unten** verändert die Reihenfolge der Schrittliste und die Reihenfolge gleichrangiger Vorschauknoten. IDs und Verbindungen bleiben erhalten. Ein Wechsel der Schrittart löscht vorhandene Verbindungen nicht automatisch; überzählige Verbindungen werden bei der Prüfung gemeldet und können bewusst entfernt werden.

**Schritt entfernen …** verlangt eine Bestätigung und entfernt den Schritt samt eingehenden und ausgehenden Verbindungen aus der ungespeicherten Eingabe. Bis zu zwanzig entfernte Schritte können vor dem Neuladen über **Entfernten Schritt wiederherstellen** zurückgeholt werden. Andere nachträgliche Eingaben werden dabei erhalten. Eine Wiederherstellung überschreibt keine fremden gespeicherten Fassungen und umgeht nicht die Größenlimits. Nach dem Speichern bleibt die bestehende Fassungsvergleichshistorie maßgeblich.

Auch ein älterer Entwurf mit einer Verbindung ohne vorhandenen Ausgangsschritt lässt sich unter **Verbindungen ohne Ausgangsschritt** korrigieren oder bereinigen. Hinweise zeigen die Schrittnummern statt technischer Kennungen.

Die Vorschau ist eine Darstellung des Graphen. Sie führt keine Entscheidungen aus und speichert keine personenbezogenen Fälle oder Antworten. Fehlerhafte Entwürfe und Kreise werden begrenzt dargestellt, nicht endlos durchlaufen. Nach Änderungen ist eine vorherige Prüfung als veraltet erkennbar; eine verspätete Serverantwort ersetzt keine neuere Prüfung.

## Rechte und gleichzeitige Bearbeitung

Die bestehenden Dokument-/Bereichsrechte bestimmen, wer einen Prozess anlegen oder bearbeiten darf. Eine im Schritt ausgewählte Funktion vergibt keine Autorenrechte. Lesende erhalten keinen Zugriff auf die Editor-APIs.

Die serverseitige Prüfung verwendet dieselben Grenzen, Graphregeln und Referenzprüfungen wie Import, Schreiben und Freigabe aus AP05. Clientseitige Bedienung ersetzt keine Serverprüfung. Die Zielsuche liefert begrenzte Treffer aus der zulässigen Lesefassung und übernimmt keine Metadaten fremder Dokumente oder Dateien. Vorhandene Verweise bleiben beim Bearbeiten erhalten, auch wenn ein Ziel nur noch neutral beschriftet werden kann.

Bei einem Schreibkonflikt kommt **HTTP 409** mit Vergleich und eigenem Graphen zurück. Texte, IDs, Verbindungen und Referenzen bleiben im Editor erhalten. Die aktuelle Fassung lässt sich in einem neuen Tab prüfen. Erst nach ausdrücklicher Bestätigung kann die eigene geprüfte Eingabe gegen den aktualisierten Ausgangsstand gespeichert werden.

## Technische Übergabe

- `ProzessFeld` und `ProzessWidget` in `kern/prozesseditor.py` ersetzen das bisher nur lesbare Feld für `Feldtyp.PROZESSGRAPH`. `EintragFormular` erhält optional Nutzer und Dokument für erlaubte Optionen und Zielbeschriftungen.
- Das Widget serialisiert ausschließlich die Struktur aus AP05 in `f_ablauf`. Sichtbare Formularelemente werden mit sicheren DOM-Textoperationen aufgebaut; unkontrolliertes HTML aus Graphlabels wird nicht eingefügt.
- `POST /d/<dokument>/prozess-pruefen` prüft mit CSRF- und Quellenzugangskontrolle, ohne zu schreiben. Hinweise enthalten gegebenenfalls stabile Schritt-/Verbindungsschlüssel zum Anspringen; die angezeigten Texte nennen verständliche Schrittnummern.
- `GET /d/<dokument>/prozess-ziele?q=…` sucht ab zwei Zeichen in erlaubten Wissenseinträgen und registrierten Anlagen; maximal zwanzig Treffer je Zielart. Eine bestehende Quellkennung wird erneut auf Bearbeitungsrechte geprüft. Bereits gespeicherte Verweise werden innerhalb des AP05-Limits vollständig beschriftet, soweit erlaubt.
- `dateien/prozesseditor.js` verwaltet die ungespeicherte Eingabe, Auswahllisten und SVG-Vorschau. Es gibt keine zusätzliche Speicherung, keinen externen Diagrammdienst und keine neue Frontend-Plattform.
- Die native SVG-Vorschau ordnet Vorwärtskanten über eine topologische Rangfolge an. Markierte Rücksprünge werden seitlich geführt; nicht vollständig prüfbare Kreise bleiben begrenzt zeichnbar. IDs, Fragen und Verbindungen stammen aus derselben Struktur wie der Editor.

Für diese begrenzte Autorenansicht genügt native SVG. Eine zusätzliche Layoutbibliothek würde hier Paket- und Betriebsaufwand erzeugen, ohne für die geprüfte Verzweigung und den Rücksprung erforderlich zu sein. Die Entscheidung wurde mit beiden Fällen im Browser geprüft. Seit AP07 nutzen Editor und Leseansicht dieselbe native SVG-Erzeugung; das Datenschema bleibt unverändert.

Keine Migration erforderlich. Bestehende Dokumente und Graphen werden nicht automatisch umgeschrieben. Die gegenwärtige Leseansicht außerhalb des Editors bleibt vorerst die Textdarstellung aus AP05.

## Abnahme

Prüfungen, konkrete Testzahlen und Screenshots stehen im Übergabeprotokoll der [Roadmap](../ROADMAP.md). Der vollständige Browserworkflow wird in einer getrennten Testdatenbank ausgeführt. Fiktive Abläufe, Funktionsbesetzungen und Freigaben dieser Prüfung gehören nicht zum lokalen Schulbestand.

Gesamtlauf: **559 Tests erfolgreich**. Nach Ergänzung der vollständigen Beschriftung vorhandener Verweise und der Reparatur nicht zugeordneter Verbindungen bestanden abschließend **97 betroffene Tests**, darunter **21 AP06-Fälle**. Ruff, Django-Systemprüfung und Migrationsabgleich sind erfolgreich. Es ist keine Migration erforderlich.

Browsernachweis: Einen Ablauf im Editor erstellen → Ja/Nein und weitere Alternative ergänzen → Funktion und Material wählen → Rücksprung beschriften → einen versehentlichen Schritt entfernen und wiederherstellen → speichern und neu laden. Zwei geöffnete Tabs erzeugen einen echten Schreibkonflikt mit erhaltener eigener Eingabe und bewusster Auflösung. Auch ein tatsächlich gespeicherter, unvollständiger Altentwurf mit fehlendem Ausgangsschritt wurde über die Oberfläche repariert. Die Prüfungen umfassen 390/768/1024/1440 Pixel, Tastatur, Touch im Browser sowie axe Hell/Dunkel ohne Befund. Das ersetzt noch nicht den fachlichen iPad-Pilot aus AP08.

Darstellungsnachweise aus dem ausdrücklich isolierten Testbestand:

- Editor und Vorschau: [1440](screenshots/13-ap06-prozesseditor-1440.png), [768](screenshots/13-ap06-prozesseditor-768.png).
- Eigener Graph beim Schreibkonflikt: [1440](screenshots/13-ap06-editor-konflikt-1440.png), [768](screenshots/13-ap06-editor-konflikt-768.png).
