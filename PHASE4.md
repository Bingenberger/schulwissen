# Nextcloud und weitere Fächer

## Stand und Voraussetzungen

Die App unterstützt die regelmäßige Indexierung verlinkter Nextcloud-Dateien,
OIDC-Anmeldung über Nextcloud sowie Arbeitspläne und Kompetenzimporte für
Deutsch, Mathematik, Sport, Kunst, Musik, Religion katholisch, Religion evangelisch,
Sachunterricht und Englisch.

WebDAV und OIDC sind getrennte Verbindungen: Für die Indexierung wird ein
technisches Konto mit App-Passwort verwendet; für die persönliche Anmeldung
ein registrierter OIDC-Client. Solange die zugehörigen Einstellungen leer
bleiben, arbeitet die App weiterhin mit lokalen Konten. Eine echte Verbindung
muss nach dem Eintragen der Werte an der jeweiligen Nextcloud geprüft werden.

## Nextcloud-Dateien durchsuchbar machen

1. Technisches Konto und App-Passwort wie in DEPLOYMENT.md §6 einrichten.
   Das Konto benötigt Leserechte auf die verlinkten schulischen Dateien.
2. Dateien über den vorhandenen Nextcloud-Browser in Einträgen verlinken.
3. Indexierung zunächst manuell ausführen:

       docker compose exec app python manage.py nextcloud_indexieren

4. Die Vorlagen aus `deploy/schulwissen-nextcloud.service` und
   `deploy/schulwissen-nextcloud.timer` nach `/etc/systemd/system/` kopieren.
   Falls das Projekt woanders liegt, `WorkingDirectory` anpassen.

       sudo systemctl daemon-reload
       sudo systemctl enable --now schulwissen-nextcloud.timer

Der Timer ruft alle 15 Minuten höchstens 50 Dateien ab. Der älteste Prüfstand
kommt zuerst, sodass auch bei größeren Beständen alle Links an die Reihe kommen.
Unveränderte Dateien liefern über `If-None-Match` und ETag nur eine 304-Antwort.
`--alle` erzwingt das erneute Lesen. `--anzahl 100` erhöht den Umfang pro Lauf.

Die Dateien werden nur vorübergehend gespeichert und danach gelöscht.
`SW_NEXTCLOUD_MAX_MB` begrenzt Downloads, standardmäßig auf 25 MB.
Unterstützte Dateiformate entsprechen der lokalen Anhang-Extraktion.

Bei HTTP 403, 404 oder 410 wird alter Suchtext entfernt. Bei einem vorübergehenden
Netzwerk- oder Serverfehler bleibt der letzte erfolgreiche Stand erhalten.
Letzter Prüfzeitpunkt, ETag und Indexierungsfehler stehen am Anhang in der
Verwaltung. Die Sichtbarkeit der Treffer richtet sich nach den Rechten des
verknüpften Eintrags in Schulwissen. OIDC überträgt keine Nextcloud-Dateirechte;
das technische Konto sollte nur für das Kollegium bestimmte Inhalte lesen können.

Referenz: [Nextcloud WebDAV](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html).

## Mit Nextcloud anmelden

Nextcloud benötigt die App
[OIDC Identity Provider](https://apps.nextcloud.com/apps/oidc).
Die Anwendung `user_oidc` erfüllt eine andere Aufgabe: Sie meldet Nextcloud
an einem externen Anbieter an.

In der Provider-App einen vertraulichen Client für Schulwissen registrieren:

- Authorization Code Flow, PKCE S256 und ID-Token-Signatur RS256.
- Scopes: `openid profile email`.
- Redirect-URI: `https://DEINE-SCHULWISSEN-ADRESSE/anmelden/nextcloud/callback`.

Die Discovery-Adresse ist üblicherweise
`https://DEINE-NEXTCLOUD/index.php/apps/oidc/openid-configuration`.
Sie kann je Installation abweichen. Den dort angegebenen `issuer` exakt übernehmen.
Die [Provider-Dokumentation](https://github.com/H2CK/oidc#endpoints) beschreibt
die Endpunkte.

In `.env` eintragen:

```dotenv
SW_OIDC_ISSUER=https://ANBIETERKENNUNG-AUS-DISCOVERY
SW_OIDC_DISCOVERY_URL=https://DEINE-NEXTCLOUD/index.php/apps/oidc/openid-configuration
SW_OIDC_CLIENT_ID=CLIENT-ID
SW_OIDC_CLIENT_SECRET=CLIENT-GEHEIMNIS
```

`SW_OEFFENTLICHE_URL` muss zur Schulwissen-Adresse passen. Anschließend:

    docker compose up -d --build

Danach erscheint auf der Anmeldeseite **Mit Nextcloud anmelden**.

### Konten verbinden

1. Ein bestehendes Schulkonto zuerst lokal anmelden.
2. Auf der Startseite **Mein Konto mit Nextcloud verbinden** wählen.
3. Die Anmeldung an der eigenen Nextcloud bestätigen.
4. In Schulwissen abmelden und **Mit Nextcloud anmelden** testen.

Alternativ kann die Administration in **Nextcloud-Anmeldungen** eine vorher
geprüfte Zuordnung aus Anbieterkennung, externer `sub`-Kennung und Schulkonto
hinterlegen. Das hilft bei Konten ohne lokales Passwort.

Konten werden nicht automatisch über E-Mail-Adressen verknüpft oder neu angelegt.
Lokale Rollen und Arbeitsgruppen bleiben maßgeblich. Gesperrte Schulkonten
können sich auch über OIDC nicht anmelden. Lokale Passwörter bleiben verfügbar.

Authlib prüft signierte ID-Tokens einschließlich Issuer, Zielgruppe, Ablaufzeit
und Nonce; die App bindet den Vorgang zusätzlich an State und Sitzung und begrenzt
ihn auf zehn Minuten. Tokens werden nicht dauerhaft gespeichert.
Die normale Abmeldung beendet die Schulwissen-Sitzung; die Nextcloud-Sitzung
bleibt bestehen. Ein globaler Logout ist nicht Teil dieser Anbindung.

Referenz: [Authlib für Django](https://docs.authlib.org/en/latest/oauth2/client/web/django.html).

## Weitere Fächer

Die Migration legt die neun gewünschten Fächer an. Unter **Verwaltung → Fächer**
stehen Fachname, Schlüssel, Lehrplanquelle und Kompetenzbereiche.

Für Deutsch bleiben die vorhandenen 117 Lehrplanerwartungen und ihre Kennungen
unverändert. Für die anderen Fächer sind keine amtlichen Kompetenzdateien im
Projekt vorhanden; sie werden nicht durch erfundene Inhalte ersetzt.

Für ein zusätzliches Fach:

1. Amtliche Lehrplandaten aufbereiten und Kompetenzbereiche mit ihren
   Kürzeln und Namen am Fach eintragen. Eine Lehrplanquelle hinterlegen.
2. Eine UTF-8-JSON-Datei im bekannten Kompetenzformat erstellen.
3. Zuerst prüfen, danach importieren:

       docker compose exec app python manage.py kompetenzen_importieren mathematik.json --fach mathematik --vorschau
       docker compose exec app python manage.py kompetenzen_importieren mathematik.json --fach mathematik

Fachschlüssel:

| Fach | Schlüssel |
| --- | --- |
| Deutsch | `deutsch` |
| Mathematik | `mathematik` |
| Sport | `sport` |
| Kunst | `kunst` |
| Musik | `musik` |
| Religion katholisch | `religion-katholisch` |
| Religion evangelisch | `religion-evangelisch` |
| Sachunterricht | `sachunterricht` |
| Englisch | `englisch` |

Das Datenformat enthält `id`, `bereich`, `bereichName`, `schwerpunktNr`,
`schwerpunkt`, `stufe` (`S`, `K` oder `D`), `text` und optional `klammer`,
`uaWeitererInhalt`, `stufePruefen` und `progressionspartner`.

Kennungen müssen fachübergreifend eindeutig sein. Ein Fachpräfix wie `M-`
verhindert Kollisionen; die bestehenden Deutschkennungen bleiben unverändert.
Fremde Kennungen können beim Import nicht überschrieben werden.
Progressionspartner müssen im selben Fach existieren. Fehler machen den
gesamten Import rückgängig; schulische Festlegungen bleiben erhalten.

**Dokument anlegen → Arbeitsplan → Fach auswählen** erzeugt einen leeren
Arbeitsplan. Kapitel, Rituale und Vorhaben können über Formulare oder den
generischen JSON-Import ergänzt werden. Die gemeinsame Feldstruktur ist der
Ausgangspunkt; fachspezifische Lehrplan- und Leistungsabsprachen müssen inhaltlich
erarbeitet werden. Kompetenzwahl, Abdeckungsmatrix, Suche, persönliche Planung
und Exporte berücksichtigen das ausgewählte Fach.

Für das Zeitbudget können in den Dokumenteinstellungen die Unterrichtsstunden
unter `stunden_pro_woche` mit den Schlüsseln `1` bis `4` eingetragen werden.
Die vorhandenen Deutsch-Einstellungen bleiben kompatibel.

## Abnahme

- Eine verlinkte Textdatei indexieren, über ihren Inhalt finden, ändern und
  erneut indexieren. Ein dritter Lauf ohne Änderungen muss sie überspringen.
- Datei in Nextcloud löschen oder die technische Freigabe entziehen:
  der nächste Lauf entfernt ihren bisherigen Suchtext.
- Schulkonto mit Nextcloud verbinden und anschließend extern anmelden.
  Ein unbekanntes Nextcloud-Konto erhält keinen automatischen Zugang.
- Arbeitsplan Mathematik anlegen. Nach dem Fachimport müssen in der
  Kompetenzwahl Mathematik-Erwartungen und passende Bereiche erscheinen.
- In der Kompetenzübersicht und Suche zwischen den neun Fächern umschalten.
