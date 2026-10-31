# AP02: Dokumentzugänge und redaktionelle Bereiche

Stand: 31.10.2026. Paket der [Roadmap](../ROADMAP.md).

## Einrichtung und Rechte

Die Administration öffnet auf der Dokumentseite **Zugänge verwalten**. Dort
lassen sich Wissensbereich, allgemeine Lesbarkeit und Zugangsregeln pflegen.
Alternativ gibt es die Verwaltungslisten **Wissensbereiche** und **Zugangsregeln**.
Auch das Anlegeformular neuer Dokumente bietet Bereich und Lesbarkeit an.
Zugangsregeln stehen als einzelne Formularblöcke untereinander, damit die drei
Rechtefelder auch auf dem Tablet vollständig erreichbar bleiben.

Jede Regel nennt genau ein Dokument oder einen Bereich und genau ein
vorhandenes Nutzerkonto oder eine vorhandene Gruppe. Drei getrennte Häkchen:

| Recht | Wirkung |
| --- | --- |
| Lesen | Öffnet eine ausdrücklich beschränkte Dokument- beziehungsweise Bereichsgrenze |
| Bearbeiten | Erlaubt dem Kollegiumsmitglied die Redaktion aller Einträge im zugewiesenen Umfang, einschließlich Abstimmung und neuer Entwurfsfassung nach einem Beschluss |
| Freigeben | Erlaubt dem Kollegiumsmitglied fachliche Freigaben und deren Rücknahme im zugewiesenen Umfang; vergibt kein Bearbeitungsrecht |

Bearbeiten und Freigeben benötigen ein zugängliches Dokument. Sie ersetzen
keine fehlende Leseregel. Eine Funktion wie „Sonderpädagogin“ vergibt keine
technischen Rechte; deren fachliches Modell folgt in AP04.

**Für alle angemeldeten Konten lesbar** ist zunächst aktiv. Auch dann sehen
Lesend-Konten und Konten ohne Kollegiumsrolle nur erlaubte Freigabefassungen.
Lehrkräfte behalten die Möglichkeit, in zugänglichen Dokumenten eigene Entwürfe
anzulegen und eigene oder ihrer Arbeitsgruppe zugeordnete Entwürfe zu bearbeiten.
Bloße Arbeitsgruppenmitgliedschaft oder Urheberschaft öffnet kein gesperrtes Dokument.

Dokument- und Bereichsgrenze gelten unabhängig voneinander:

- Ein gesperrter Bereich braucht eine Leseregel für den Bereich.
- Ein zusätzlich gesperrtes Dokument braucht außerdem eine Leseregel für das Dokument.
- Bereichsredaktion gilt für die zugänglichen Dokumente dieses Bereichs.
- Die Administration behält vollständigen Zugriff.

Beispiel: Die Deutschredaktion erhält **Bearbeiten** für den Bereich Deutsch.
Damit kann sie Deutschentwürfe redigieren, aber keine Mathematikeinträge übernehmen.
Bei einem gesperrten Deutschbereich benötigt sie zusätzlich **Lesen** für diesen
Bereich. **Freigeben** wird unabhängig davon vergeben.

Ein Widerruf wirkt bei der nächsten Anfrage, auch in bestehenden Sitzungen.
Bekannte URLs oder persönliche Planungen behalten keine Zugriffserlaubnis.

## Durchgehender Schutz

Die Entscheidungen in `kern/rechte.py` gelten für Startseite, Dokumentlisten
und Zählungen, Suche und Filterauswahl, Vorschläge, Einträge, Fassungen,
Vergleiche, Auswertungen, Rückverweise, Kommentare und persönliche Planung.
Anlege- und Schreibaktionen prüfen den Dokumentzugang ebenfalls.

Anhänge mit Dokument- oder Eintragsbezug verwenden diese Grenzen bei Anzeige,
Dateisuche, Vorschlägen und direkten Medienabrufen. Die Fassungsprüfung aus AP01
bleibt für Lesende zusätzlich bestehen. Dateien ohne jeden Dokument- oder
Eintragsbezug behalten ihren bisherigen Zugang für angemeldete Konten.
Das Nextcloud-Original benötigt zusätzlich seine eigenen Zugriffsrechte.

JSON-/XLSX-Importe und vollständige Dokumentexporte bleiben administrativ.
Beschlussvorlagen und deren PDF sind auf zugewiesene Bearbeitungs- oder
Freigabebereiche beschränkt. Reine Freigabeverantwortliche können Vorlagen
prüfen und freigeben, ohne redaktionelle Schreibrechte zu erhalten.

Konten, Gruppen, Zugänge und rohe Wissensdaten verwaltet die Administration.
`is_staff` oder einzelne Django-Modellrechte geben anderen Konten dort keinen
zusätzlichen Inhaltszugriff. Die bestehende Stammdatenpflege bleibt erhalten:
Mit passenden Django-Rechten dürfen zugewiesene Fachredaktionen ihre schulischen
Festlegungen pflegen. Fachauswahl, Listenbearbeitung und Einzelaufrufe bleiben
auf die zugewiesenen Fächer begrenzt.
Die Kompetenzstammdaten bleiben dokumentübergreifende gemeinsame Daten; ihre
Leseansichten erhalten keinen neuen Dokumentbezug.

## Beschlüsse mit mehreren Dokumenten

Beschlusstexte können mehrere Dokumente betreffen. Der vollständige Beschluss
ist deshalb nur sichtbar, wenn alle betroffenen Dokumente zugänglich sind.
Das gilt auch für verknüpfte Protokolle und Protokollanlagen. Quellfassungen
zugänglicher Einträge bleiben lesbar; geschützte Beschlussbezeichnungen und
Herkunftsangaben werden dort nicht eingeblendet.

Betroffene Dokumente bilden einen dauerhaften Zugangsrahmen am Beschluss.
Eine Rücknahme entfernt diesen Rahmen nicht. Nichtadministrative Rücknahmen
benötigen die Freigabeberechtigung für den gesamten Rahmen. Dokumente lassen
sich in der Verwaltung nicht löschen, damit Beschlusszugänge und Fassungen
nicht durch Kaskaden verschwinden.

## Bestandsmigration

Migration `kern.0009` ergänzt Wissensbereiche, Regeln, Dokumentzuordnung und
Beschlussrahmen. Bestehende Dokumente bleiben allgemein lesbar. Für vorhandene
Fachangaben werden passende Bereiche angelegt.

Vorhandene Redaktionskonten erhalten für die bisherigen Dokumente ausdrückliche
persönliche Bearbeitungsregeln. Neue Mitglieder der technischen Rolle Redaktion
erhalten diese Zuordnungen nicht automatisch. Neue Dokumente brauchen bei Bedarf
eine bewusst vergebene Redaktion. Der Demo-Befehl ordnet seine Deutschredaktion
ausdrücklich dem Demo-Arbeitsplan zu.

Bestehende Beschlussrahmen werden aus Fassungen und Protokollnachweisen abgeleitet.
Schultexte, Konten, Arbeitsgruppen und Freigabeentscheidungen werden nicht erfunden
oder umgeschrieben. Die Administration muss bisherige redaktionelle Zuordnungen
bei gewünschter Begrenzung bewusst nachpflegen; die Migration entzieht bestehenden
Personen keine Arbeitsbereiche.

Bereichsrechte erweitern den vorgesehenen Datenumfang nicht auf Schüler-, Eltern-
oder Personalakten. Die App bleibt eine Wissensbasis für allgemeine Schulverfahren.

## Abnahme

Regressionen stehen in `tests/test_dokumentzugaenge.py`: Rollen, Suche/Filter,
Trefferzahlen, direkte URLs und Schreibversuche, Anlagen, Widerruf, Planung,
getrennte Bearbeitungs-/Freigaberechte, gemischte Beschlussrahmen, technische
Verwaltungsrechte, fachbezogene Stammdatenpflege, Datenbankbedingungen und
Bestandsmigration. Bestehende Freigabe-, Lösch- und Fassungsprüfungen bleiben erhalten.

Prüfergebnisse und Browsernachweise stehen im Übergabeprotokoll der Roadmap.
Für Medienzugriffe bleibt die nginx-Anpassung aus AP01 erforderlich.

Ergebnisse: 420 erfolgreiche Tests im Gesamtlauf. Ein neu angelegter
Testdatensatz hatte eine ungültige Stufenkennung; nach ihrer Korrektur liefen
alle 46 AP02-Tests erfolgreich. Diese Nachprüfung überlappt mit dem Gesamtlauf;
zusammen sind alle 421 Tests abgedeckt. Zuvor waren zusätzlich 66 Zugangs- und
Workflowtests erfolgreich. Die Prüfungen nutzten frisch migrierte, getrennte
Testdatenbanken und ausschließlich im Testprozess einen MD5-Passworthasher;
die reguläre Passwortkonfiguration der App bleibt unverändert.

Ruff, Formatprüfung, Django-Systemcheck und Migrationsabgleich sind grün.
Migration 0009 wurde auch lokal angewandt. Die bestehenden Dokumente sind
weiter allgemein zugänglich; persönliche Redaktionszuordnungen wurden überprüft.

Browser: Dokument, Dokumentanlage, Dokumentverwaltung mit Zugangsregeln,
Bereichsliste und Regelliste bei 390/768/1024/1440 Pixeln ohne horizontalen
Überlauf. Frontend-axe-Prüfungen ohne WCAG-A/AA-Befund, Tastaturreihenfolge der
neuen Felder geprüft; die Verwaltungsaktion ist für Lehrkräfte ausgeblendet.
Keine Schultexte oder Regeln wurden bei der Browserprüfung geändert.
Screenshots: `docs/screenshots/09-ap02-*.png` bei 1440 und 768 Pixeln.
