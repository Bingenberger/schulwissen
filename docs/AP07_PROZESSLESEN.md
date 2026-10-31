# AP07: Prozesse grafisch und geführt nachlesen

Stand: 31.10.2026. AP07 ergänzt die Leseansichten zum [Prozesseditor](AP06_PROZESSEDITOR.md). Es ist keine Migration nötig. Veröffentlichung und fachlicher Pilot folgen in AP08.

## Bedienung

Ein Prozess wird wie jeder andere Eintrag aus seinem Dokument geöffnet. Unter „Nachschlagen“ stehen drei Ansichten bereit:

- **Geführt:** Am Start beginnen, Antworten auswählen und dem nächsten Schritt folgen. „Zurück“ erlaubt eine andere Entscheidung; „Neu beginnen“ verwirft die bisherige Auswahl. Rücksprünge werden erst durch eine bewusste Auswahl ausgeführt.
- **Grafik:** Einen Schritt per Maus, Touch oder Tastatur auswählen. Die Erklärung, aktuelle Zuständigkeit und erlaubte Materialien erscheinen darunter. Vergrößern, Verkleinern und Einpassen helfen bei umfangreicheren Abläufen; die Grafik kann innerhalb ihres Bereichs gescrollt werden.
- **Text:** Alle Schritte, Verzweigungen und Rücksprünge untereinander lesen. Diese Ansicht funktioniert auch ohne JavaScript.

Die bisherige Auswahl liegt ausschließlich im Arbeitsspeicher des geöffneten Tabs. Sie verändert weder URL noch Browserablage und löst keine Netzwerkanfrage aus. Neuladen beginnt erneut am Start. Es entstehen keine Antwortprotokolle, Fälle oder Tätigkeitsnachweise.

## Fassungen, Kontakte und Materialien

Die bestehenden Leseregeln bleiben maßgeblich: Lesende erhalten die gültige beschlossene Fassung; Lehrkräfte und Redaktion sehen im üblichen Einstieg den Arbeitsstand. Eine ausdrücklich geöffnete Fassung verwendet ausschließlich deren Prozessdaten. Die Quelle wird in der Prozessansicht bezeichnet. Dieses Paket erweitert nicht den Veröffentlichungsworkflow.

**Kontakte sind aktuell**, auch bei historischen Prozessfassungen. Der angezeigte Kontaktstand macht diesen Unterschied sichtbar. Der Resolver aus AP04 berücksichtigt aktive Konten, Gültigkeitszeiten, bewusst aktivierte Vertretungen, Teams und den ausdrücklich gewählten Geltungsbereich. Eine unbesetzte Bereichszuständigkeit wird nicht durch eine zufällige allgemeine Besetzung ersetzt. Archivierte oder fehlende Funktionen liefern einen Hinweis. Kontonamen werden angezeigt; Konto-E-Mail-Adressen werden nicht übernommen. Eine ausdrücklich gepflegte dienstliche Funktionsadresse, Telefonnummer oder Anlaufstelle kann erscheinen. Zuständigkeiten vergeben keine Zugriffsrechte.

Materialien werden beim Lesen nach den aktuellen Rechten aufgelöst. Gesperrte Verweisziele liefern weder fremde Titel noch Rohkennungen im HTML oder im ausgelieferten Graphen. Aus einem beschlossenen oder historischen Prozess führt ein Wissensverweis zur aktuell gültigen beschlossenen Zielfassung, nicht zu deren neuerem Entwurf. Nicht verfügbare Ziele erhalten einen neutralen Hinweis. Materiallinks öffnen einen neuen Tab.

Dateien durchlaufen den geschützten Medienzugang. Bei beschlossenen Prozessen werden seit der maßgeblichen Freigabe geänderte Dateien zurückgehalten. Das ist noch keine unveränderliche externe Dateiversionsbindung; diese gehört zu AP09. Externe Links erlauben ausschließlich HTTP/HTTPS ohne eingebettete Zugangsdaten. Nextcloud-Pfade benötigen eine konfigurierte sichere Basisadresse. Ein echter Nextcloud-Betriebsnachweis bleibt B01.

## Druck und PDF

„Drucken“ und „Alle Schritte als PDF“ enthalten den vollständigen Ablauf mit allen Alternativen und Rücksprungmarkierungen, aktuellen Kontakten und erlaubten Materialien. Die persönlich durchlaufene Auswahl wird nicht ausgegeben. Beide Darstellungen verwenden dieselbe aufbereitete Quelle und dieselbe Textvorlage wie die Textansicht.

Das einzelne Prozess-PDF steht allen für diesen Prozess berechtigten Nutzern zur Verfügung. Es verwendet denselben Lesestand beziehungsweise eine ausdrücklich berechtigte Fassung und wird mit `private, no-store` ausgeliefert. Der bisherige Dokumentexport behält seine Berechtigungen. Der gemeinsame PDF-Renderer lädt keine externen Ressourcen.

## Technische Übergabe

`kern/prozesslesen.py` bereitet den ausgewählten Schnappschuss mit aufgelösten Kontakten und Materialien auf. Rohreferenzen auf fremde Einträge oder Dateien werden nicht an den Browser weitergegeben. Die SVG-Erzeugung liegt gemeinsam für Editor und Leser in `dateien/prozessgrafik.js` und der zugehörigen CSS-Datei. Markierte Rücksprünge werden aus der Rangbildung ausgenommen; auch unvollständige Altentwürfe verursachen keine endlose Anordnung. Der Leser in `dateien/prozesslesen.js` verwendet dieses SVG und die serverseitige Textansicht. Es gibt keine zusätzliche Layoutbibliothek und keine zweite gespeicherte Diagrammquelle.

## Tatsächliche Abnahme

- **583 Tests** im Gesamtlauf bestanden. **97 betroffene Tests**, darunter **22 AP07-Fälle**, prüfen insbesondere Lesefassungen, aktuelle Kontakte, Bereiche, Vertretung, inaktive Konten, erlaubte Ressourcen, verweigerte Metadaten, Dateistände, URLs, Schleifen und PDF-Rechte. Isolierte Testdatenbank; schneller Passwort-Hasher ausschließlich zur Testlaufzeit.
- Ruff, Django-Systemprüfung und Migrationsabgleich erfolgreich.
- Browser: 390/768/1024/1440 Pixel, drei Ansichten, Tastatur, Zoom und axe Hell/Dunkel ohne Befund. Beide Antwortzweige, Rücksprung, Zurück, Neustart und Neuladen geprüft. Während der Auswahl keine Netzwerkanfragen und keine Änderung an URL, Local Storage oder Session Storage.
- Historische Fassung mit aktueller Besetzung, Text ohne JavaScript, serverseitiges PDF und Browserdruck geprüft. Beide PDF-Dateien enthalten den Ablauf und aktuelle Kontakte; geschützte Titel, neuere Entwurfsinhalte und die frühere Besetzung fehlen.
- Gemeinsame SVG-Auswahl im Autoreneditor und geführte Touch-Bedienung bei 768 Pixeln geprüft. Der fachliche iPad-Pilot mit einer Lehrkraft bleibt AP08.
- Browserdaten ausschließlich in einer separaten Testdatenbank, keine erfundenen Schulprozesse im Schulbestand.

Darstellungsnachweise: Geführt bei [1440](screenshots/14-ap07-gefuehrt-1440.png) und [768](screenshots/14-ap07-gefuehrt-768.png) Pixeln; Grafik bei [1440](screenshots/14-ap07-grafik-1440.png) und [768](screenshots/14-ap07-grafik-768.png) Pixeln.
