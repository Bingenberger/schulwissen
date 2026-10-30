# Protokolle genehmigen, Einträge entfernen und Startseite begrenzen

## Sichtbarkeit

Entwürfe sind für aktive Lehrkräfte, Redaktion und Administration sichtbar. Konten der Rolle „Lesend“ erhalten weiterhin ausschließlich freigegebene Fassungen. Diese bestehende Regel wurde nicht in eine private Entwurfsablage geändert. Die Protokollübersicht und die eigene Entwurfsliste benennen die Sichtbarkeit ausdrücklich.

## Versehentlich angelegte Einträge

Über die Leseansicht oder die Bearbeitungsmaske führt „Eintrag löschen …“ zunächst zu einer Bestätigungsseite. GET löscht nichts. Der Löschvorgang verwendet die bestehenden Bearbeitungsrechte: Lehrkräfte bearbeiten und löschen nur im eigenen Arbeitsbereich; Redaktion und Administration haben ihre bisherigen erweiterten Rechte.

Freigegebene Fassungen, Beschlussbezüge, untergeordnete Einträge, eingehende Verweise einschließlich gespeicherter Fassungen, Anhänge, Kommentare und persönliche Planungen verhindern das Löschen. Der Eintrag und die Gründe bleiben dann sichtbar. Unbeschlossene, nicht verwendete Einträge können ausdrücklich und endgültig gelöscht werden.

Gelöschte Kennungen bleiben in einer eigenen Tabelle reserviert. Die automatische Vergabe, gemeinsame Importprüfung und Modellanlage verhindern eine Wiederverwendung. Migration: `kern/0007_reserviertekennung`.

## Das gesamte Konferenzprotokoll beschließen

Die Administration öffnet auf der Protokollübersicht „Gesamtes Protokoll beschließen“. Die Vorschau enthält den Protokollkopf und sämtliche aktiven Tagesordnungspunkte dieses Dokuments. Archivierte Einträge gehören nicht dazu. Datum, Gremium und Beschlusstext dokumentieren die tatsächliche Genehmigung durch die Konferenz. Der Beschluss wird mit dem Protokollkopf verknüpft.

Alle Pflichtangaben müssen ausgefüllt und die aktuellen Inhalte als Fassung gespeichert sein. Die Genehmigung ist ein gemeinsamer Vorgang: Bei einem Fehler bleibt das gesamte Protokoll unverändert. Die Vorschau ist signiert und höchstens eine Stunde gültig; eine zwischenzeitliche Änderung oder ein neu hinzugefügter Eintrag verlangt eine erneute Sichtprüfung und Bestätigung. Der Server bestimmt die vollständige Auswahl aus dem Dokument, nicht aus vom Browser übermittelten Eintragsnummern.

Bei einer neuen Gesamtgenehmigung bleiben ältere freigegebene Fassungen erhalten. Bereits gültige, unveränderte Blöcke erhalten dafür eine neue Fassung, damit der neue Beschluss tatsächlich das ganze aktive Protokoll umfasst. Eine erneute unveränderte Freigabe eines vollständig beschlossenen Protokolls wird verhindert.

## Begrenzungen

| Bereich | Startseite | Vollständige Liste |
| --- | --- | --- |
| Meine offenen Entwürfe | Höchstens 5, zuletzt geändert zuerst; Gesamtzahl sichtbar | `/meine-entwuerfe`, Suche nach Titel/Dokument, 20 pro Seite |
| Unsere Dokumente | Höchstens 6, alphabetisch; Gesamtzahl sichtbar | `/dokumente`, Suche nach Titel/Beschreibung, 12 pro Seite |

Die eigene Entwurfsliste zeigt wie zuvor Ideen und Entwürfe, die selbst angelegt wurden oder persönlich zugeordnet sind. Die bisherige Sichtbarkeit und die Daten der anderen Lehrkräfte werden dadurch nicht erweitert.

## Prüfung

Automatisierte Tests prüfen Löschberechtigungen, Bestätigung, geschützte Bezüge, dauerhafte Kennungen, atomare Protokollgenehmigung, vollständigen Rücklauf bei einem Fehler, veraltete Vorschauen, bestehende Freigaben sowie Listenbegrenzungen und Seitennavigation. Browserprüfungen betreffen die sechs neuen beziehungsweise geänderten Ansichten bei 390, 768, 1024 und 1440 Pixeln sowie WCAG AA. Die Browserprüfung hat keine bestehenden Einträge gelöscht und kein echtes Protokoll genehmigt. Screenshots: `docs/screenshots/07-*`.

Prüfergebnis: Gesamtlauf mit 353 Tests bestanden; anschließend alle 21 gezielten Workflowtests einschließlich des ergänzten Planungsschutzes bestanden. Ruff und Formatprüfung sind grün, `makemigrations --check --dry-run` meldet keine fehlende Migration. Die sechs Browseransichten bestanden 24 Breitenprüfungen und jeweils eine automatisierte WCAG-AA-Prüfung ohne Befund.
