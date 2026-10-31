# AP01: Einheitliche Lesefassungen

Stand: 31.10.2026. Paket der [Roadmap](../ROADMAP.md).

## Verhalten

Die Rolle „Lesend“ erhält Titel, Inhalte, Status, Jahrgang und Suchausschnitte
jeweils aus der gültigen freigegebenen Fassung. Ein neuer Arbeitsstand ersetzt
sie weder bei der Suche noch beim Filtern oder Zählen. Lehrkräfte und Redaktion
suchen weiterhin ihren sichtbaren Arbeitsstand. Die Indizes vermischen diese
beiden Stände nicht mehr.

Die gemeinsame Fassungswahl steht in `kern/staende.py`: als lesbarer
`Eintragsstand` und als SQL-Projektion vor Suche, Filterung und Zählung.
Unversionierte Dokument- und Strukturangaben bleiben im bisherigen Kernmodell.
Ein fehlender Fassungsindex darf keinen Rückfall auf den Entwurfsindex auslösen.

Geschützt sind Volltext-, Wortlaut- und Tippfehlersuche, Vorschläge,
Kontextpfade, Navigation, Dokumentkarten, Startseite und Eintragszählungen.
Noch nicht freigegebene Kapitel bleiben als nicht anklickbares Gerüst mit
neutraler Bezeichnung sichtbar. Ihre aktuellen Entwurfstitel werden verborgen.
Interne Kommentare und Entwurfsfassungszahlen werden Lesenden nicht angezeigt.

Rückverweise stammen aus der sichtbaren Quellfassung. Ein später entfernter
Verweis bleibt dadurch im gültigen Stand erhalten; ein neuer Entwurfsverweis
erscheint dort nicht vorzeitig. Automatische Beschriftungen ausgehender
Eintragsverweise werden aus der erlaubten Zielfassung aufgelöst oder verborgen.
Das gilt auch für historische Ansichten und Vergleiche. Gespeicherte historische
Schnappschüsse werden dafür nicht umgeschrieben. Automatische Zielbeschriftungen
werden nicht ungeprüft in den Suchindex freigegebener Quellfassungen übernommen.

PDF-Zeilen und die zugehörigen Auswertungsdaten reichen Titel und Inhalte der
freigegebenen Fassung weiter. JSON-/XLSX-Arbeitsstandsexporte bleiben der
Administration vorbehalten; die Zugangsrechte wurden nicht ausgeweitet.

## Dateien und Migration

Migration `kern.0008` ergänzt Suchtext, Suchvektor samt GIN-Index und einen
Freigabezeitpunkt an gespeicherten Fassungen. Eine Datenmigration baut die
getrennten Indizes aus dem Bestand auf. Freigabe, Ablösung und Rücknahme wählen
automatisch den passenden Fassungsindex; die eigentlichen Fassungsinhalte
bleiben unverändert.

Eintragsanhänge sind für Lesende nur zugänglich, wenn sie seit der Freigabe
unverändert geblieben sind. Neue und geänderte Anlagen sind Arbeitsstand.
Anzeige, Dateisuche, Vorschläge, Protokollanlagen und direkte Medien-URLs
verwenden denselben Filter. Eine erneute unveränderte Indexierungsprüfung ist
keine Inhaltsänderung. Zur erneuten Freigabe den Eintrag als neue Fassung
speichern, mit seinen Anlagen prüfen und beschließen.

Alte Freigaben besitzen keinen gesicherten Freigabezeitpunkt. Die Migration
verwendet konservativ den Zeitpunkt der gespeicherten Fassung; später
hinzugefügte Anlagen müssen deshalb gegebenenfalls erneut freigegeben werden.
Dokumentanhänge ohne Eintragsbezug behalten ihren bisherigen Zugang für
angemeldete Konten. Bereichsrechte folgen in AP02.

**Bestehende nginx-Installationen:** Den bisherigen öffentlichen
`location /medien/`-Block mit `alias` entfernen, Konfiguration prüfen und nginx
neu laden. Alle Medienabrufe müssen durch Django laufen. Die angepasste Vorlage
und weitere Hinweise stehen in [DEPLOYMENT.md](../DEPLOYMENT.md#5-anhänge-durchsuchbar-machen).
Die lokale Compose-App ist aktualisiert; eine externe nginx-Installation wurde
in dieser Sitzung nicht verändert.

Die Prüfung ersetzt keine Fixierung externer Nextcloud-Dateiversionen. Diese
bleibt Teil von AP09. Zugriffsrechte am Nextcloud-Original gelten zusätzlich.

## Prüfung

Die Regressionstests stehen in `tests/test_lesestaende.py`. Sie prüfen insbesondere
abweichende Titel, Texte, Jahrgänge, Status, Trefferzahlen, Referenzbeschriftungen,
Rückverweise, Fassungszähler, Kommentare, Dateisuche und direkte Downloads sowie
Freigabe/Rücknahme und einen fehlenden Fassungsindex.

Zwei alte Tests wurden an die tatsächliche Freigabe mit Beschlussnachweis und
an neutrale Platzhalter für ungeprüfte Kapiteltitel angepasst.

Ergebnisse: Gesamtsuite **374 bestanden**; nach der letzten Absicherung gegen
einen fehlenden Fassungsindex **21 AP01-Regressionstests bestanden** (überlappt
mit der Gesamtsuite). Zusätzlich liefen **142 betroffene Tests** mit der
unveränderten Standard-Passwortkonfiguration erfolgreich. Für die Gesamtsuite
und die abschließende AP01-Prüfung wurde ausschließlich im isolierten
Testprozess `PASSWORD_HASHERS` auf `MD5PasswordHasher` gesetzt; die App- und
Produktionskonfiguration bleiben unverändert. Jede Prüfung nutzte eine eigene,
frisch migrierte Testdatenbank. Ruff, Formatprüfung, Django-Systemcheck und
`makemigrations --check --dry-run` waren erfolgreich.

Browserprüfung mit dem vorhandenen Lesend-Demokonto: Startseite, Suche,
Dokument und Leseansicht bei 390/768/1024/1440 Pixeln ohne horizontalen Überlauf;
axe-Prüfung für WCAG A/AA in Hell-/Dunkelmodus ohne Befund. Suchvorschläge mit
Pfeiltasten, Escape und Enter sowie die Druckansicht wurden geprüft.
Screenshots: `docs/screenshots/08-ap01-*.png` bei 1440 und 768 Pixeln.

Lokale Bestandsprüfung nach Indexerneuerung: 16 Einträge, 10 Fassungen,
2 Beschlüsse und 1 Anhang indexiert. In den vorhandenen Suchstichproben keine
abweichenden Lesetitel/-status und keine unberechtigten Rückverweise gefunden.
Die aussagekräftigeren Gegenbeispiele mit abweichenden Arbeitsständen decken
die automatisierten Regressionstests ab.
