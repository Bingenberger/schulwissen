# AP08: Abläufe veröffentlichen und schulisch erproben

Stand: 31.10.2026. Die technische Umsetzung verbindet [Autoreneditor](AP06_PROZESSEDITOR.md), [Leseansicht](AP07_PROZESSLESEN.md), Zuständigkeiten und Freigabe. Der echte fachliche Pilot mit einer Lehrkraft am iPad ist noch offen; ein Browserdurchlauf mit fiktiven Daten ersetzt diese Abnahme nicht.

## Für das Kollegium

Auf der Startseite und im Benutzermenü führt **Abläufe** zum Einstieg „Was passiert, wenn …?“. Hier stehen nur aktuell veröffentlichte Prozesse aus zugänglichen Dokumenten. Ein neuer Entwurf ersetzt deren gültige Fassung erst nach erneuter Freigabe. Archivierte Prozesse werden nicht angeboten.

Die Liste zeigt höchstens zwölf Abläufe je Seite. Suche nach Titel, Kennung, Anlass oder dem heutigen Namen einer Schulfunktion, beispielsweise „Sonderpädagogin“. Derselbe Suchweg steht in der allgemeinen Suche und deren Vorschlägen als eigene Gruppe **Veröffentlichte Abläufe** bereit. Treffer öffnen unmittelbar die freigegebene Fassung. Ein umbenannter Funktionsname wird ohne neue Prozessfassung gefunden. Fremde oder inzwischen gesperrte Dokumente werden vor Suche und Zählung ausgefiltert.

Lehrkräfte können über **Arbeitsstände** ausdrücklich in die vorhandene interne Ansicht wechseln. Entwürfe bleiben für Lehrkräfte mit Dokumentzugang lesbar, auch wenn diese sie nicht selbst bearbeiten dürfen. Konten mit der Rolle Lesend erhalten keinen Zugriff auf diese Liste. Dokumentnavigation und direkte Eintragsadressen behalten ihre bisherigen Leseregeln. Auf einer Prozessfassung führt „Arbeitsstand ansehen“ bewusst zur Arbeitsansicht des Inhalts; die eigentliche Bearbeitung bleibt berechtigungsgesteuert.

**Neuen Prozess anlegen** bietet die zugänglichen Dokumente an, deren Dokumenttyp Prozesse erlaubt. Fehlt ein solches Dokument, kann die Administration zunächst ein Schulhandbuch anlegen. Schritte und Zweige werden weiterhin im Editor ohne Diagrammcode gepflegt.

## Fachliche Freigabe dokumentieren

1. Prozess erstellen und im Editor **Ablauf prüfen** verwenden. Die fachlich zuständige Person prüft Texte, Verzweigungen, Rücksprünge, Zuständigkeiten und Materialien.
2. Eine Person mit dem getrennten dokument- oder bereichsbezogenen Freigaberecht öffnet am Arbeitsstand **Ablauf freigeben**. Das Bearbeitungsrecht allein genügt nicht.
3. Datum der tatsächlich erfolgten Freigabe, zuständige Stelle und Freigabenachweis angeben. Die Stelle kommt aus den vorhandenen Gremien; die Administration kann dort beispielsweise „Schulleitung“ pflegen. Die Auswahl ersetzt keine schulinterne Entscheidung über Zuständigkeiten. Ein Datum in der Zukunft veröffentlicht keinen Prozess.
4. Fachliche Prüfung bestätigen. Bei verlinkten Materialien ist zusätzlich deren Prüfung einschließlich Fassung zu bestätigen.
5. **Geprüfte Fassung veröffentlichen** schaltet den geprüften Schnappschuss frei. Die Prozessliste und die Suche führen anschließend dorthin.

Die Freigabe verwendet das bestehende Beschluss- und Versionsmodell. Der Nachweis nennt zuständige Stelle, Datum und eintragendes Konto. Eine tatsächlich erfolgte Konferenzentscheidung kann dort ebenso dokumentiert werden wie eine fachliche Freigabe durch die Schulleitung; die Maske verlangt keine erfundene Konferenz. Andere Inhaltstypen und ihre bisherigen Freigabewege ändern sich nicht. Allgemeine Gültigkeitszeiträume, Pflegeprüfungen und weitere Freigabekategorien gehören zu AP09.

Der signierte Freigabestand ist an Konto und Eintrag gebunden. Vor dem Schreiben werden Dokument und Eintrag gesperrt und der Stand erneut geprüft. Zwischenzeitliche Änderungen, bereits erfolgte Freigaben und Änderungen an registrierten verlinkten Dateimetadaten führen zum Konflikt; es wird weder ein Teilnachweis noch eine neue Freigabe geschrieben. Die eingegebenen Nachweistexte bleiben erhalten. Dann die aktuelle Fassung und eine neu geöffnete Freigabemaske prüfen und die Angaben bewusst übertragen.

Ein Wechsel der Funktionsbesetzung benötigt keine erneute Freigabe der Prozesslogik. Grafische Ansicht, geführte Ansicht, Text und PDF zeigen weiterhin die gleichen Schritte und lösen die **heutigen Kontakte** auf.

## Veränderliche Materialien

Die Freigabe bestätigt den geprüften Stand, friert aber keine externe Datei ein. Nextcloud- und andere externe Links tragen daher in der Leseansicht und im PDF den Hinweis **Veränderlicher Materiallink**. Die externe Dateifassung ist nicht an die Prozessfreigabe gebunden. Für verbindliche externe Anlagen ist bis AP09 eine nachprüfbare externe Fassung vorzuhalten und im Nachweis zu benennen; ein veränderlicher Link allein erfüllt das nicht.

Registrierte Änderungen seit der maßgeblichen Freigabe werden beim Lesen zurückgehalten und durch einen Prüfhinweis ersetzt. Wissensverweise verwenden die gültige freigegebene Zielfassung und die aktuellen Zugangsrechte. Die Prüfung registrierter Metadaten erkennt keine externe Inhaltsänderung, die in Nextcloud ohne Rückmeldung an die App erfolgt. Die technische Nextcloud-Betriebsabnahme bleibt B01.

## Fiktive Demo vorbereiten

Die beiden importierbaren Beispiele enthalten keinerlei echte schulische Regel und keine Personen oder Fälle. Sie werden nicht automatisch in den Schulbestand eingespielt.

1. Als Administration ein gesondertes Schulhandbuch **Fiktive Demo – Prozesswerkzeug** mit Schlüssel `demo-prozesswerkzeug` anlegen. Die vorgesehenen Testpersonen benötigen Zugang. Bei Bedarf den Zugang auf eine Testgruppe begrenzen.
2. In der Verwaltung eine Funktion **Demo-Materialdienst** mit Schlüssel `demo-materialdienst` anlegen. Für die Bedienprüfung ein bereits vorhandenes aktives Konto zuordnen; keine zweite Personenkartei oder künstlichen Lehrkraftkonten anlegen.
3. Zuerst [prozesswerkzeug-demo-material.json](beispiele/prozesswerkzeug-demo-material.json) über den bestehenden JSON-Import prüfen und übernehmen. Den ausdrücklich fiktiven Wissenseintrag `DEMO-INFO` über den bestehenden Beschlussweg freigeben.
4. Danach [prozesswerkzeug-demo.json](beispiele/prozesswerkzeug-demo.json) importieren. Die Reihenfolge ist erforderlich: Der Prozess verweist auf den bereits vorhandenen Wissenseintrag. Alternativ dieselben fünf Schritte im Frontend anlegen: Start → Frage „Ist das Demomaterial bereits vorhanden?“ → bei Ja „Demomaterial ansehen“ → Ende; bei Nein „Demo-Materialdienst ansprechen“ → beschrifteter Rücksprung zur Frage.
5. Als zuständige Stelle einen ausdrücklich fiktiven Freigabenachweis eintragen und den Demoablauf veröffentlichen. Der Name und der Anlass müssen sichtbar als Demo gekennzeichnet bleiben.
6. Als Lehrkraft über **Abläufe** nach „Demo-Materialdienst“ suchen. Beide Antworten, Rücksprung, Zurück, Neustart, Gesamtgrafik, Materiallink und PDF prüfen. Eine neue Besetzung über **Besetzung wechseln …** wählen; nach Neuladen ändert sich der aktuelle Kontakt, während die Prozessfassungen unverändert bleiben.

Bei einem anderen Dokumentschlüssel beide Beispieldateien einschließlich des Ressourcenverweises im Prozess entsprechend anpassen. Ein Demoablauf ist keine Vorlage für ungeprüfte echte Schulregeln.

## Noch offene fachliche Pilotabnahme

Eine verantwortliche Schulfunktion und eine Lehrkraft wählen einen repräsentativen echten Ablauf aus. Erst nach fachlicher Bestätigung werden echte Verfahrensinhalte und zuständige Personen übernommen. Die Prüfung kann mit der fiktiven Demo eingeübt werden.

- [ ] Ablauf und fachlich zuständige Freigabestelle benannt; Texte, Zweige und Anlaufstellen bestätigt.
- [ ] Vorgesehene Lehrkräfte haben den richtigen Dokumentzugang; weitere Konten bleiben entsprechend begrenzt.
- [ ] Eine Lehrkraft findet den freigegebenen Ablauf am echten iPad und durchläuft beide Zweige ohne Hilfe.
- [ ] Grafik, aktuelle Kontakte, Materialien, Zurück/Neustart, Text und Druck/PDF sind fachlich verständlich.
- [ ] Personalwechsel aktualisiert Kontakte, ohne die freigegebene Prozesslogik oder technische Rechte zu verändern.
- [ ] Bei verbindlichen Anlagen ist eine überprüfbare Fassung vorhanden; veränderliche Links sind erkennbar.
- [ ] Ergebnis mit Datum, Beteiligten, Prozessfassung, Gerät/Browser und nötigen Korrekturen dokumentiert. Es werden keine personenbezogenen Fallverläufe oder Entscheidungsantworten protokolliert.

B01 (Nextcloud, Anmeldung und Betriebsabnahme) bleibt vor dem verbindlichen breiten Einsatz erforderlich. Die technische Lieferung kann unabhängig davon geprüft werden; diese offenen fachlichen und betrieblichen Abnahmen bleiben ausdrücklich offen.

## Technische Übergabe und Prüfungen

`kern/prozesse.py` liefert Liste, Suche und Freigabemaske. `lesemenge(..., nur_beschlossene=True)` projiziert Titel, Daten, Status und Suchindex auf dieselbe gültige Fassung, unabhängig von der technischen Nutzerrolle. Diese Projektion wird vor Filtern und Zählen verwendet. Die Prozesssuche fragt aktuelle Funktionsnamen und deren stabile Referenzschlüssel ab; Prozessfassungen werden dafür nicht umgeschrieben. Die allgemeine Suche trennt veröffentlichte Prozesse von den bisherigen Wissenseinträgen. Arbeitsstände werden über die explizite Prozessliste gesucht.

Keine Migration und kein Neuaufbau des Suchindex erforderlich. Die Prozesse verwenden bereits die versionierten Suchtexte aus AP05. Bestehende Dokumentzugänge werden nicht erweitert. Bildnachweise und endgültige Testergebnisse werden im Übergabeprotokoll der Roadmap festgehalten.

Tatsächliche technische Abnahme am 31.10.2026:

- **602 Tests** im Gesamtlauf erfolgreich. **73 gezielte Tests** für AP08 und Prozessdaten, darunter **19 AP08-Fälle**, ebenfalls erfolgreich. Die vorherige gezielte Prüfung umfasste zusätzlich Suche und Leseansicht; ein ungültiger Vorlagenverweis wurde durch getrennte, geordnete Demoimporte korrigiert. Isolierte Testdatenbanken und schneller Passwort-Hasher ausschließlich zur Testlaufzeit.
- Ruff, Django-Systemprüfung und Migrationsabgleich grün; keine Migration.
- Vollständiger Browserweg mit fiktiven Daten: Prozess über den Editor erstellt, Rolle im Backend mit vorhandenem Demokonto besetzt, fachlich freigegeben, als Lehrkraft über Funktionssuche gefunden und beide Zweige durchlaufen. Personalwechsel im Backend aktualisiert den Kontakt bei gleicher freigegebener Prozessfassung. Ein nachträglicher Entwurf verdrängt weder Portal- noch Suchfassung.
- Portal, Suche und Freigabemaske bei 390/768/1024/1440 Pixeln; axe Hell/Dunkel ohne Befund. Tastatur mit Tab/Enter, Touch bei 768 Pixeln, Lesekonto, Zugriff auf private Dokumente und Text ohne JavaScript geprüft.
- Das erzeugte PDF enthält freigegebene Schritte, Rücksprung und neue Besetzung. Frühere Besetzung, neue Entwurfsinhalte und private Titel fehlen.
- Browserbestand ausschließlich in einer separaten Datenbank; keine Demoimporte oder erfundenen Besetzungen im Schulbestand.

Darstellungsnachweise: Portal bei [1440](screenshots/15-ap08-portal-1440.png) und [768](screenshots/15-ap08-portal-768.png), Suche bei [1440](screenshots/15-ap08-suche-1440.png) und [768](screenshots/15-ap08-suche-768.png), Freigabe bei [1440](screenshots/15-ap08-freigabe-1440.png) und [768](screenshots/15-ap08-freigabe-768.png) Pixeln.
