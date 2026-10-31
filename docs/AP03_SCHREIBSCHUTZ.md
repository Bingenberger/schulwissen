# AP03: Gemeinsames Schreiben ohne stilles Überschreiben

Stand: 31.10.2026. Arbeitspaket der [Roadmap](../ROADMAP.md).

## Bearbeiten im Kollegium

Beim Öffnen eines Eintrags erhält das Formular einen signierten Nachweis des
Bearbeitungsstands. Die App prüft diesen Stand unmittelbar vor dem Speichern.
Wurde der Eintrag zwischenzeitlich geändert, bleibt die fremde Änderung erhalten
und die eigene Eingabe wird im Formular erneut angezeigt. Der normale Schreibweg
liefert dann HTTP 409, ohne eine neue Fassung anzulegen.

Die Konfliktansicht stellt aktuell gespeicherte Texte und eigene Eingaben
gegenüber. Verweisänderungen werden ebenfalls angezeigt. Der aktuelle Eintrag
lässt sich zusätzlich in einem neuen Tab öffnen.

Zum Auflösen:

1. Unterschiede prüfen und im Formular die Änderungen übernehmen, die erhalten bleiben sollen.
2. Den Vergleich ausdrücklich über die zunächst leere Checkbox bestätigen.
3. **Geprüfte Eingabe speichern** wählen.

Die App prüft dabei erneut genau den angezeigten aktuellen Stand. Wenn eine
dritte Änderung hinzugekommen ist, erscheint wieder ein Konflikt; die frühere
Bestätigung wird nicht als pauschale Überschreiberlaubnis verwendet. Eine normale
erneute Übermittlung des alten Formulars umgeht die Prüfung ebenfalls nicht.
Eine erfolgreiche Speicherung erzeugt weiterhin eine neue Eintragsversion.

Ein fehlender, veränderter oder zu einem anderen Konto beziehungsweise Eintrag
gehörender Nachweis wird ebenfalls zurückgewiesen. Bereits vor der Aktualisierung
geöffnete Formulare können deshalb eine Vergleichsbestätigung verlangen. Es gibt
keine automatische Zusammenführung und keine Bearbeitungssperre, die während der
gesamten Schreibzeit eines Menschen gehalten wird.

## Gemeinsamer Schreibweg

`kern/schreibschutz.py` bildet den Bearbeitungsstand aus Eintragskennung und
Identität, aktueller Version, Inhalt, Status, Struktur, Zuständigkeiten, Fassung,
Verweisen und Anhangständen. Abgeleitete Suchindizes zählen nicht als neue
fachliche Eingabe. Der signierte Transport ist an Konto und Ziel gebunden.

`eintragstypen.dienste.speichern(..., erwarteter_stand=...)` sperrt zuerst das
Dokument und dann den betroffenen Eintrag, prüft die aktuelle Bearbeitungserlaubnis
und den Ausgangsstand und schreibt erst danach Eintrag, Verweise, Suchindex und
Version innerhalb derselben Transaktion.

Bei einer Neuanlage bedeutet `erwarteter_stand=None`, dass unter dieser Kennung
noch kein Eintrag bestehen darf. Die normale Anlegemaske vergibt ihre Kennung
innerhalb derselben Dokumentensperre. Zwei parallele Neuanlagen erhalten deshalb
unterschiedliche Kennungen. Bestehende Einträge werden nicht versehentlich als
neuer Datensatz überschrieben. Ein gelöschter Ausgangseintrag wird vom gemeinsamen
Schreibdienst nicht aus einem alten Bearbeitungsstand wiederhergestellt.
Die normale Bearbeitungsmaske erhält bei inzwischen entfernten Einträgen die
eigenen Eingaben, blendet das Speichern aus und bietet eine getrennte Neuanlage
zum bewussten Übertragen an. Dafür ist der ursprünglich signierte, kontogebundene
Nachweis erforderlich.

Der spätere Prozesseditor verwendet denselben Dienst: Nachweis beim Laden
holen, beim Senden Ziel und Konto prüfen, den daraus gelesenen Stand als
`erwarteter_stand` übergeben und `Schreibkonflikt` mit erhaltener Eingabe behandeln.
Ein erneutes Laden des aktuellen Standes darf keinen ungeprüften automatischen
Speicherversuch auslösen.

## Verwaltung und Importe

Die Eintragsverwaltung trägt denselben Nachweis in einem versteckten Feld.
Formularprüfung und Speichern halten dieselbe Dokumentensperre. Bei Konflikten
bleiben Titel, JSON und Metadaten im gebundenen Formular erhalten. Ein Hinweis
zeigt den aktuell gespeicherten Text und verlinkt die aktuelle Verwaltungsfassung.
Nach ausdrücklich bestätigtem Vergleich wird der erneut geprüfte Stand gespeichert.
Eine zwischenzeitliche weitere Änderung verwirft die alte Bestätigung.
Django zeigt solche Formularfehler wie üblich mit HTTP 200; sie schreiben nichts.

Die JSON-Importvorschau bindet ihren Nachweis zusätzlich an den Importinhalt und
den Stand des gesamten Dokuments. Bei einer Änderung oder einem ausgetauschten
Importinhalt erfolgt keine Teilübernahme. Stattdessen werden Hinweis und erneuerte
Vorschau angezeigt. Erst eine weitere bewusste Übernahme kann diese aktuelle
Vorschau anwenden. Auch Änderungen außerhalb der ausgewählten Importzeilen machen
im ersten Stand eine neue Dokumentvorschau erforderlich.

Vertrauenswürdige programmgesteuerte Importe bleiben ausdrücklich aktuelle
Bestandsübernahmen: JSON ohne erwarteten Vorschau-Stand und XLSX über die CLI
prüfen und schreiben unter der Dokumentensperre. Die getrennten CLI-Aufrufe
„Vorschau“ und „Übernahme“ erhalten damit keinen nachträglichen gemeinsamen
historischen Stand. Der optionale Sentinel `UNGEPRUEFT` des Schreibdienstes gehört
zu solchen internen Aufrufen; browserbasierte Editoren dürfen ihn nicht verwenden.
Eine offene Bearbeitungsmaske erkennt Änderungen durch diese Importe über ihren
alten Nachweis.

## Freigaben und Bestandsdaten

Freigaben und Rücknahmen verwenden die Reihenfolge Dokument → Eintrag und lesen
die betroffenen Einträge nach der Sperre frisch. Bei einer verschwundenen
Freigabeauswahl wird keine Teilfreigabe vorgenommen. Der vollständige
Beschlussvorgang ist transaktional. Die bestehende signierte Standprüfung der
gemeinsamen Protokollgenehmigung bleibt erhalten.

Ein zwischenzeitlicher Beschluss ändert den Bearbeitungsstand ebenfalls. Eine alte
Eingabe kann ihn nicht unbemerkt ersetzen. Freigegebene Versionen bleiben wie bisher
unveränderlich; weitere zulässige Bearbeitung erzeugt einen neuen Entwurf.

Es ist keine Datenmigration notwendig. Dokumente, Fassungen, Zugangsregeln und
Schultexte werden für diese Änderung nicht umgeschrieben. Sämtliche Bearbeitungs-
und Leserechte aus AP02 gelten weiter.

## Prüfung

Regressionen: `tests/test_schreibschutz.py`. Die Prüfungen umfassen konkurrierende
Formulare, erhaltene Eingaben, explizite Auflösung, eine weitere Änderung während
der Auflösung, fehlende/manipulierte/falsch gebundene Nachweise, Metadatenänderungen,
Freigaben, Verwaltung, Importvorschau, vollständige Import-Rücknahme und
Doppelübermittlung eines Bearbeitungsformulars.

Zwei Tests verwenden echte getrennte Datenbankverbindungen: Von zwei Änderungen
am selben Ausgangsstand darf genau eine gewinnen; zwei parallele Neuanlagen müssen
zwei verschiedene Kennungen erhalten. Die Verbindungen werden im jeweiligen
Arbeitsthread ausdrücklich geschlossen.

Bestehende Verwaltungs- und Importtests holen nun den Nachweis aus dem zuvor
geöffneten Formular beziehungsweise der Vorschau, damit die bisherigen fachlichen
Validierungen weiterhin tatsächlich geprüft werden. Weitere Ergebnisse und
Browsernachweise stehen im Übergabeprotokoll der Roadmap.

Ergebnisse: **441 Tests im vollständigen Lauf bestanden**. Nach Ergänzung der
beiden Fälle für inzwischen entfernte Einträge liefen **59 betroffene Tests**
erfolgreich, darunter alle **22 Schreibschutztests**. Zuvor bestanden zusätzlich
131 bestehende Workflow-, Verwaltungs-, Import- und Oberflächentests. Die Läufe
überlappen; insgesamt sind alle 443 aktuellen Tests abgedeckt. Die Prüfungen
verwendeten frisch migrierte, getrennte Testdatenbanken und ausschließlich im
Testprozess einen MD5-Passworthasher. Die Passwortkonfiguration der App blieb
unverändert. Ruff, Formatprüfung, Django-Systemcheck und Migrationsabgleich sind grün.

Browser: Konfliktansicht bei 390/768/1024/1440 Pixeln, erhaltene Eingaben,
Vergleich, zunächst ungesetzte Bestätigung und Tastaturbedienung geprüft.
axe-Prüfungen für WCAG A/AA im Hell-/Dunkelmodus ohne Befund; kein horizontaler
Überlauf. Verwaltungskonflikte einschließlich aufgeklapptem JSON-Vergleich bei
768 und 1440 Pixeln geprüft. Screenshots: `docs/screenshots/10-ap03-*.png`.

Die Browserprüfung verwendete absichtlich ungültige Standnachweise und speicherte
keine gültige Eingabe. Dokument-Fingerabdrücke vor und nach der Prüfung stimmen
überein. Die lokale Compose-App wurde aktualisiert.
