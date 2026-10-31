# AP04: Schulfunktionen und aktuelle Zuständigkeiten

Stand: 31.10.2026. Das Verzeichnis **Zuständigkeiten** im Benutzermenü ist für aktive angemeldete Konten lesbar. Es enthält höchstens zwölf Funktionen je Seite und eine Suche nach Funktion, Aufgabe oder aktueller Ansprechperson. Stabile Detailadressen lauten `/funktionen/<kennung>`.

## Pflege in der Verwaltung

1. Als Administration unter **Schulfunktionen** eine Funktion mit stabiler Kennung, Aufgabe und Besetzungsmodus anlegen. Optional einen dienstlichen Funktionskontakt und eine Anlaufstelle für Rückfragen oder Vakanz eintragen.
2. Über **Besetzungen hinzufügen** ein vorhandenes aktives Nutzerkonto auswählen. Die Suche findet Anzeigename, Kürzel und Konto-E-Mail. Eine Person kann mehrere Funktionen übernehmen. Es werden keine neuen Personenkarteien oder Konten erzeugt.
3. Hauptzuständigkeit oder Vertretung und den Zeitraum festlegen. Beide Datumsgrenzen gelten **einschließlich**; ein leeres Enddatum bedeutet unbefristet. Optional unter **Funktionsbereiche** eine benannte Zuständigkeit anlegen und auswählen.
4. Für Personalwechsel bei der bisherigen Besetzung **Besetzung wechseln …** verwenden: Neue Person und Wechseltermin angeben. Der Dialog beendet den bisherigen Zeitraum am Vortag und legt die Nachfolge mit dem bisherigen Enddatum an. Ein Wechsel am ersten Gültigkeitstag storniert die alte Zuordnung als Korrektur. Fehler führen zum vollständigen Zurückrollen beider Änderungen.

Der technische Verwaltungszugang (`is_staff`) und die passenden Django-Modellberechtigungen bleiben zusätzlich erforderlich. Das vorhandene Administrationskonto besitzt sie; eine bloße Funktionsbesetzung oder Gruppenzuordnung vergibt sie nicht. Für Autocomplete werden auch Leserechte auf Nutzer, Schulfunktionen und Funktionsbereiche benötigt.

Die Migration `0010` legt ausschließlich Tabellen und Datenregeln an. Es gibt keine vorgegebenen produktiven Funktionen oder erfundenen Besetzungen. Die tatsächlichen Aufgaben, Personen und dienstlichen Kontakte pflegt die Schule.

## Einzelzuständigkeit, Team und Vertretung

Eine Einzelzuständigkeit erlaubt je Funktionsbereich und Besetzungsart nur einen gleichzeitig gültigen Datensatz. Hauptzuständigkeit und Vertretung dürfen gleichzeitig hinterlegt sein. Mehrere Hauptzuständige sind nur im ausdrücklich gewählten Modus **Team** möglich; dieselbe Person wird dabei nicht mehrfach als aktueller Kontakt ausgegeben.

Eine hinterlegte Vertretung übernimmt **nicht automatisch**. Für ihren tatsächlichen Einsatz wird eine Vertretungsbesetzung mit **Vertretung übernimmt in diesem Zeitraum** und bewusst gewähltem Zeitraum angelegt. Eine bestehende Bereitschaftsbesetzung zuerst am Vortag beenden; danach bei Bedarf wieder als Bereitschaft anlegen. Die Aktivierung gehört zur unveränderlichen Identität eines Besetzungsdatensatzes. Der Modus einer Funktion mit bisherigen Besetzungen bleibt ebenfalls erhalten.

Bei einer Einzelzuständigkeit ersetzt die ausdrücklich aktive Vertretung für diesen Zeitraum den aktuellen Hauptkontakt; die reguläre Besetzung bleibt erkennbar. Bei Teams ergänzen aktive Vertretungen das Team. Abwesenheitsgründe, Gesundheitsdaten oder einzelne Schülerfälle werden nicht erfasst. Ist eine Hauptbesetzung inaktiv, übernimmt eine bloß hinterlegte Vertretung nicht stillschweigend.

Benannte Funktionsbereiche sind eigene Datensätze, unabhängig von den Wissensbereichen und ihren Zugriffsregeln. Die Auflösung berücksichtigt **genau den angefragten Bereich**. Es gibt keinen stillschweigenden Rückfall auf die allgemeine Zuständigkeit. Bisher verwendete Bereichsnamen und Kennungen bleiben stabil; für eine andere Bedeutung einen neuen Bereich anlegen. Auch abgelaufene Bereiche bleiben sichtbar, solange nicht stornierte Besetzungen darauf verweisen.

## Aktuelle Kontakte und Historie

Das Verzeichnis zeigt nur aktuell erreichbare Besetzungen. Es unterscheidet unbesetzt, künftig vorgesehen, abgelaufen, aktive Vertretung, Team, archivierte Funktion und zu prüfende Besetzung bei inaktiven Konten. Archivierte Funktionen fehlen in der Übersicht; ihre Detailadresse zeigt den Archivstatus ohne aktuelle Kontakte. Historische und inaktive Personen sind keine aktuellen Suchtreffer. Konto-E-Mails werden nicht automatisch veröffentlicht; nur der ausdrücklich gepflegte Funktionskontakt erscheint.

Jede Speicherung einer Funktion oder Besetzung erzeugt einen unveränderlichen `Funktionsstand` mit Autor, Zeitpunkt, Revision und gespeichertem Inhalt. Bei Besetzungen werden auch der damalige Anzeigename und Bereichsname festgehalten. Die Historie ist nur in der Verwaltung zugänglich. Person, Funktion, Bereich, Art und Vertretungsaktivierung werden bei bestehenden Besetzungen nicht ersetzt. Zeiträume und Stornierungen lassen sich mit neuem Historienstand korrigieren. Besetzungen werden beendet oder storniert, nicht gelöscht; referenzierte Nutzerkonten bleiben geschützt und werden bei Austritt deaktiviert.

Die Verwaltung prüft die Ausgangsrevision. Veraltete Formulare behalten ihre Eingaben und verweisen auf einen manuellen Vergleich mit dem aktuellen Stand. Derselbe Schutz gilt für Personalwechsel. Eine gemeinsame Datenbanksperre auf der Funktion schützt die Überschneidungsprüfung auch bei paralleler Anlage.

## Schnittstelle für AP05–AP08

`kern.funktionen.aufloesen(funktion, bereich=None, stichtag=None)` liefert eine `Funktionsauskunft` mit Status, sämtlichen aktuellen Zuständigen, Hauptbesetzungen, Vertretungen und gegebenenfalls Prüfhinweis. Eine numerische Funktionskennung lädt den Datensatz frisch. Funktionsobjekte und Kontaktauflösungen nicht dauerhaft zwischenspeichern. `auskuenfte(funktion)` liefert allgemeine und benannte Zuständigkeiten für das Verzeichnis.

Spätere Prozessknoten referenzieren die stabile Funktion und gegebenenfalls den Bereich. Die aktuelle Kontaktanzeige nutzt diesen Resolver; Personen werden nicht in Prozessfassungen kopiert. Eine Umbesetzung ändert ausschließlich die Besetzungsdaten. Der Prozessdatentyp und seine Referenzintegration folgen in AP05.

Ein optionaler Stichtag wertet die gespeicherten Zeiträume aus, verwendet aber den **heutigen Kontostatus**. Das ist keine Rekonstruktion damaliger Kontoaktivität oder früherer Korrekturstände. Dafür bleibt die gesonderte, zeitgestempelte Verwaltungshistorie maßgeblich; eine öffentliche historische Kontaktansicht ist nicht Bestandteil von AP04.

Schulfunktionen vergeben keine technischen Rechte. Lesen und Pflegen von Dokumenten, redaktionelle Bereiche und Django-Berechtigungen bleiben unverändert. Backend und öffentliche Schreibdienste verlangen Administration; interne Fixture-/Migrationsaufrufe ohne Autor sind vertrauenswürdiger Code. Direkte SQL-, `QuerySet.update`- oder Bulk-Schreibwege umgehen Modellvalidierung und Historie und sind für die Pflege nicht vorgesehen.

## Abnahme

Gesamtlauf: **486 Tests erfolgreich**, davon **43 AP04-Fälle**, einschließlich zweier gleichzeitig versuchter Einzelbesetzungen über getrennte Datenbankverbindungen. Ruff, Django-Systemcheck und Migrationsabgleich sind erfolgreich. Browserprüfung bei 390/768/1024/1440 Pixeln: Suche, Tastatur, Nutzerauswahl, Personalwechsel-Dialog, Rollen und anonymer Zugang; axe im Verzeichnis und in der Demo jeweils Hell/Dunkel ohne Befund. Details stehen im Übergabeprotokoll der [Roadmap](../ROADMAP.md). Die Darstellung mit besetzten Funktionen wird ausschließlich mit ungespeicherten, ausdrücklich bezeichneten Demonstrationsobjekten geprüft; der lokale Schulbestand bleibt ohne erfundene Zuordnungen.

Darstellungsnachweise: [Verzeichnis 1440](screenshots/11-ap04-verzeichnis-leer-1440.png), [Verzeichnis 768](screenshots/11-ap04-verzeichnis-leer-768.png), [Demo mit Vertretung und Team 1440](screenshots/11-ap04-zustaendigkeiten-demo-1440.png), [Demo 768](screenshots/11-ap04-zustaendigkeiten-demo-768.png), [Besetzung anlegen 1440](screenshots/11-ap04-besetzung-anlegen-1440.png), [Besetzung anlegen 768](screenshots/11-ap04-besetzung-anlegen-768.png), [Personalwechsel-Demo 1440](screenshots/11-ap04-personalwechsel-demo-1440.png), [Personalwechsel-Demo 768](screenshots/11-ap04-personalwechsel-demo-768.png).
