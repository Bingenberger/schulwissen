# Betrieb der Schulwissen-Plattform

Diese Anleitung beschreibt den Betrieb auf einem Ubuntu-Server mit Docker
Compose hinter nginx. Sie richtet sich an die Person, die den Server betreut.
Programmierkenntnisse sind dafür nicht nötig.

```
Internet ──HTTPS──► nginx (Host, Port 443) ──HTTP──► app (127.0.0.1:8001) ──► db (PostgreSQL 16)
                                                      └── Docker Compose ──────────┘
```

## 1. Voraussetzungen

- Ubuntu 22.04 oder 24.04, zum Beispiel ein LXC auf dem Proxmox-Host, mit einer
  festen Domain wie `schulwissen.ggs-ndk.de`, deren DNS-Eintrag auf den Server
  zeigt.
- Docker Engine mit dem Compose-Plugin (`docker compose version` muss
  funktionieren), siehe <https://docs.docker.com/engine/install/ubuntu/>.
  Das alte `docker-compose` 1.x funktioniert mit aktuellen Docker-Versionen
  nicht zuverlässig.
- nginx und certbot: `sudo apt install nginx certbot python3-certbot-nginx`.
- Etwa 2 GB RAM und 10 GB Plattenplatz reichen für ein Kollegium dieser Größe
  bequem.

**Der Port.** Die App lauscht auf `127.0.0.1:8001`, nicht auf 8000 – dort läuft
auf diesem Host schon die Fahrradprüfungs-App. Über `SW_PORT` in `.env` lässt
sich das ändern; der Wert muss dann auch in die nginx-Konfiguration.

## 2. Installation

```bash
sudo mkdir -p /opt/schulwissen && sudo chown $USER /opt/schulwissen
# Code nach /opt/schulwissen kopieren (git clone oder Archiv entpacken)
cd /opt/schulwissen

cp .env.example .env
nano .env
chmod 600 .env        # die Datei enthält Passwörter
```

In `.env` müssen gesetzt sein:

| Variable | Wert |
| --- | --- |
| `SW_SECRET_KEY` | langer Zufallswert: `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | langes Zufallspasswort, nur Buchstaben und Ziffern: `openssl rand -hex 24` |
| `SW_ALLOWED_HOSTS` | `schulwissen.ggs-ndk.de` |
| `SW_OEFFENTLICHE_URL` | `https://schulwissen.ggs-ndk.de` (ohne `/` am Ende) |
| `SW_SMTP_*` | Mailzugang – ohne ihn funktioniert „Passwort vergessen“ nicht |

`SW_DEBUG` bleibt im Echtbetrieb **leer**. Ist es gesetzt, zeigt die App bei
Fehlern interne Angaben an und setzt die Sicherheitsvorgaben für Cookies herab.
`SW_DATABASE_URL` und `SW_MEDIEN_VERZEICHNIS` setzt `docker-compose.yml` selbst.

```bash
docker compose up -d --build
docker compose ps                     # app muss nach etwa 20 s laufen
docker compose exec app python manage.py admin_anlegen leitung@ggs-ndk.de \
    --name "Vorname Nachname"
```

Das Kommando gibt ein Startpasswort aus. Nach der ersten Anmeldung unter
`/passwort-aendern` ändern.

Beim Start bringt der Container die Datenbank selbst auf den neuesten Stand
(`migrate`) und legt Rollen und Gremien an (`rollen_einrichten`).

## 3. nginx und HTTPS

```bash
sudo cp deploy/nginx-schulwissen.conf /etc/nginx/sites-available/schulwissen
sudo nano /etc/nginx/sites-available/schulwissen      # Domain eintragen
sudo ln -s /etc/nginx/sites-available/schulwissen /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d schulwissen.ggs-ndk.de
```

certbot trägt den HTTPS-Teil und die Weiterleitung von http nach https selbst
ein und erneuert das Zertifikat automatisch.

**HTTPS ist Pflicht**, sobald die App aus dem Internet erreichbar ist: ohne sie
gehen Passwörter im Klartext über die Leitung.

### Die Prüfung `check --deploy`

```bash
docker compose exec app python manage.py check --deploy
```

Drei Warnungen bleiben dabei stehen; alle drei sind bewusst so:

| Warnung | Warum sie bleibt |
| --- | --- |
| `W008` SSL-Umleitung | Die macht nginx. In Django eingeschaltet, gäbe es ohne HTTPS eine Endlosschleife. Wer sie doch in Django will: `SW_SSL_UMLEITUNG=true`. |
| `W005` HSTS für Unterdomains | `ggs-ndk.de` hat weitere Unterdomains (zum Beispiel die Nextcloud). Die Festlegung würde auch für sie gelten. |
| `W021` HSTS-Vorabliste | Ein Eintrag dort lässt sich praktisch nicht zurücknehmen. Für eine Schulanwendung nicht nötig. |

HSTS selbst ist im Echtbetrieb auf ein Jahr eingestellt. **Erst einschalten,
wenn HTTPS zuverlässig läuft** – der Browser merkt sich die Festlegung für
diese Dauer. `SW_HSTS_TAGE=0` schaltet sie ab.

## 4. Stammdaten einspielen

```bash
docker compose exec app python manage.py kompetenzen_importieren \
    kompetenzerwartungen_lp2021.json

docker compose exec app python manage.py arbeitsplan_importieren \
    Datenmodell_Arbeitsplan_Deutsch.xlsx --vorschau
docker compose exec app python manage.py arbeitsplan_importieren \
    Datenmodell_Arbeitsplan_Deutsch.xlsx
```

Eine neuere Arbeitsmappe muss nicht ins Abbild: sie lässt sich einhängen.

```bash
docker compose cp ./Neue_Mappe.xlsx app:/tmp/mappe.xlsx
docker compose exec app python manage.py arbeitsplan_importieren /tmp/mappe.xlsx --vorschau
```

## 5. Anhänge durchsuchbar machen

Dateiabrufe unter `/medien/` laufen durch Django und dieselbe Rechteprüfung wie
die Leseansicht. nginx darf diesen Pfad nicht direkt aus dem Medienvolume
ausliefern. Bei bestehenden Installationen den alten `location /medien/`-Block
mit `alias` entfernen, die Konfiguration prüfen und nginx neu laden; die Vorlage
in `deploy/nginx-schulwissen.conf` reicht alle Abrufe an die App weiter.

Seit AP01 ergänzt Migration `kern.0008` getrennte Suchindizes für gespeicherte
Fassungen und baut die vorhandenen Indizes ohne vermischte Entwurfstexte neu auf.
Für alte Freigaben fehlt der genaue Freigabezeitpunkt; hier gilt konservativ der
Zeitpunkt der gespeicherten Fassung. Später hinzugefügte oder geänderte Anlagen
bleiben für Lesende verborgen, bis sie erneut mit einem Stand freigegeben werden.
Änderungen an Dateiinhalten oder Suchtext machen eine Anlage ebenfalls zum
Arbeitsstand; eine reine unveränderte Nextcloud-Prüfung dagegen nicht.
Das fixiert noch keine externen Nextcloud-Dateiversionen (Roadmap AP09).

Der Text hochgeladener PDF-, Word-, ODT- und Textdateien wird **nicht** beim
Hochladen gelesen – ein 200-seitiges PDF soll das Kollegium nicht warten
lassen. Das erledigt ein Lauf im Hintergrund:

```bash
docker compose exec app python manage.py anhaenge_indexieren
```

Damit das regelmäßig geschieht, zwei Dateien anlegen:

`/etc/systemd/system/schulwissen-index.service`

```ini
[Unit]
Description=Schulwissen: Text aus Anhaengen lesen
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/schulwissen
ExecStart=/usr/bin/docker compose exec -T app python manage.py anhaenge_indexieren
```

`/etc/systemd/system/schulwissen-index.timer`

```ini
[Unit]
Description=Schulwissen: Anhaenge viertelstuendlich indexieren

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now schulwissen-index.timer
systemctl list-timers schulwissen-index.timer
```

Jeder Lauf nimmt sich höchstens 50 Anhänge vor. `--alle` liest auch schon
indexierte Dateien erneut – nötig etwa, wenn eine Datei ersetzt wurde.

Dateien, aus denen sich kein Text holen lässt (Bilder, eingescannte PDFs ohne
Texterkennung), bleiben über **Dateiname und Beschreibung** auffindbar. Es
lohnt sich daher, beim Hochladen eine Beschreibung einzutragen.

Falls sich am Suchindex etwas grundlegend ändert, lässt er sich neu aufbauen:

```bash
docker compose exec app python manage.py shell -c \
  "from kern.suchindex import alles_neu_aufbauen; print(alles_neu_aufbauen())"
```

## 6. Nextcloud verbinden (optional)

Damit das Kollegium Dateien aus der Nextcloud verlinken kann, braucht die App
ein **eigenes technisches Konto** mit einem App-Passwort:

1. In der Nextcloud ein Konto anlegen, etwa `schulwissen`.
2. Diesem Konto **nur Leserechte** auf die Ordner geben, die verlinkt werden
   sollen (über eine Gruppe oder gezielte Freigaben).
3. Als dieses Konto anmelden → Einstellungen → Sicherheit → **App-Passwort
   erzeugen**. Das Passwort erscheint nur einmal.
4. In `.env` eintragen:

```bash
SW_NEXTCLOUD_URL=https://cloud.ggs-ndk.de
SW_NEXTCLOUD_NUTZER=schulwissen
SW_NEXTCLOUD_PASSWORT=das-app-passwort
```

```bash
docker compose up -d        # damit die neuen Werte gelesen werden
```

**Was gespeichert wird:** der Pfad der Datei und ein Link in die
Nextcloud-Oberfläche. Bewusst **kein** öffentlicher Freigabe-Link – wer den
Link öffnet, meldet sich mit dem eigenen Nextcloud-Konto an und sieht nur, was
er ohnehin sehen darf. Die Datei selbst bleibt in der Nextcloud, diese App
kopiert sie nicht.

Bleiben die Werte leer, fehlt nur die Dateiauswahl; alles andere läuft normal.

## 7. Konten für das Kollegium

Konten legt die Schulleitung unter `/verwaltung/` an (Menüpunkt „Nutzer“).
Je Konto gehört **eine Rolle** dazu und gegebenenfalls **eine Arbeitsgruppe**:

- Rollen: `Administration`, `Redaktion`, `Lehrkraft`, `Lesend`
- Arbeitsgruppen: zum Beispiel `Jahrgang 1` bis `Jahrgang 4`, `Steuergruppe`

Neue Arbeitsgruppen werden unter „Gruppen“ angelegt; im Feld „Art“ des
Gruppenprofils muss **Arbeitsgruppe** stehen, sonst gilt sie als Rolle.

Ein Konto ohne Rolle sieht nur beschlossene Inhalte. Das ist Absicht: ein neu
angelegtes Konto soll nicht versehentlich Entwürfe sehen.

Passwörter setzt sich jede Lehrkraft selbst über „Passwort vergessen“ – dafür
muss der SMTP-Zugang in `.env` stehen.

## 8. Dateien und Sicherung

Es gibt zwei Docker-Volumes:

| Volume | Inhalt |
| --- | --- |
| `schulwissen_pgdaten` | die Datenbank – **das ist das Wichtige** |
| `schulwissen_medien` | hochgeladene Anhänge |

Sicherung der Datenbank:

```bash
docker compose exec -T db pg_dump -U schulwissen schulwissen \
    | gzip > /sicherung/schulwissen-$(date +%F).sql.gz
```

Sicherung der Anhänge:

```bash
sudo tar czf /sicherung/medien-$(date +%F).tar.gz \
    -C /var/lib/docker/volumes/schulwissen_medien/_data .
```

Als täglicher Cron-Eintrag, zum Beispiel um 2:30 Uhr:

```cron
30 2 * * * cd /opt/schulwissen && docker compose exec -T db pg_dump -U schulwissen schulwissen | gzip > /sicherung/schulwissen-$(date +\%F).sql.gz
```

Zurückspielen:

```bash
gunzip < /sicherung/schulwissen-2026-11-09.sql.gz \
    | docker compose exec -T db psql -U schulwissen schulwissen
```

## 9. Aktualisieren

```bash
cd /opt/schulwissen
git pull                       # oder neues Archiv entpacken
docker compose up -d --build
```

Migrationen laufen beim Start automatisch. Vor einer größeren Aktualisierung
lohnt eine Sicherung der Datenbank.

## 10. Nachsehen, wenn etwas klemmt

```bash
docker compose ps              # läuft alles?
docker compose logs -f app     # Protokoll der App
docker compose logs db         # Protokoll der Datenbank
curl -s localhost:8001/gesundheit   # muss „ok" antworten
```

| Fehlerbild | Ursache |
| --- | --- |
| „Unbekannter Eintragstyp" an einem Eintrag | Der Typ wurde von Hand gesetzt oder sein Modul ist weg. `manage.py eintraege_pruefen` findet alle, `--setzen <typ>` stellt sie richtig. |
| `SW_ALLOWED_HOSTS fehlt` beim Start | `.env` unvollständig oder nicht gelesen |
| „Bad Request (400)“ im Browser | Die aufgerufene Domain steht nicht in `SW_ALLOWED_HOSTS` |
| Links in den Passwort-Mails zeigen auf `http://` | nginx setzt `X-Forwarded-Proto` nicht |
| Seite ohne Gestaltung | `collectstatic` fehlgeschlagen – Abbild neu bauen |
| „port is already allocated“ | Auf dem Port läuft schon etwas. `SW_PORT` in `.env` ändern |

## 11. Betrieb ohne Docker (systemd und nginx)

Compose ist der empfohlene Weg. Wer die App lieber direkt auf dem Host
betreibt, braucht Python 3.12, PostgreSQL 16 und `uv`:

```bash
sudo apt install python3.12 python3.12-venv postgresql-16 \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core
sudo -u postgres createuser --pwprompt schulwissen
sudo -u postgres createdb -O schulwissen schulwissen
sudo -u postgres psql -d schulwissen -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

cd /opt/schulwissen
uv sync --frozen --no-dev
set -a && . ./.env && set +a
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py rollen_einrichten
```

`SW_DATABASE_URL` muss dabei in `.env` stehen, zum Beispiel
`postgresql://schulwissen:PASSWORT@127.0.0.1:5432/schulwissen`.

Dienstdatei `/etc/systemd/system/schulwissen.service`:

```ini
[Unit]
Description=Schulwissen-Plattform der GGS Niederkassel
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=exec
User=schulwissen
WorkingDirectory=/opt/schulwissen
EnvironmentFile=/opt/schulwissen/.env
ExecStartPre=/usr/local/bin/uv run python manage.py migrate --noinput
ExecStart=/usr/local/bin/uv run gunicorn schulwissen.wsgi:anwendung \
    --bind 127.0.0.1:8001 --workers 3 --timeout 120
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now schulwissen
sudo systemctl status schulwissen
```

Die nginx-Konfiguration ist dieselbe. Das Medienverzeichnis aus
`SW_MEDIEN_VERZEICHNIS` liest Django; `/medien/` erhält keinen direkten nginx-Alias.


## 12. Aktualisierung auf Phase 3

Mit `docker compose up -d --build` werden WeasyPrint, Pango und Schriftarten
mitgebaut. Die Startmigration ergänzt die Dokumenttypen „Konzept“ und
„Konferenzprotokoll“, bestehende Inhalte bleiben erhalten. Danach kann die
Administration Dokumente direkt auf der Startseite anlegen.

PDF-Exporte brauchen weder einen Browser noch einen zusätzlichen Dienst.
Bei Betrieb ohne Docker sind die oben genannten Systempakete erforderlich;
siehe auch die [Installationshinweise von WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).

Der generische Import ist über die Dokumentseite oder
`manage.py eintraege_importieren DATEI --vorschau` erreichbar.
Schema, Rundlauf und Archivgrenzen beschreibt [JSON-IMPORT.md](JSON-IMPORT.md).
PostgreSQL und Medienverzeichnis bleiben die Grundlage vollständiger Sicherungen.


## 13. Nextcloud-Anmeldung, Dateiindex und weitere Fächer

Die Anleitung in [PHASE4.md](PHASE4.md) beschreibt den OIDC-Client der
Nextcloud, die sichere Zuordnung zu bestehenden Schulkonten, den zusätzlichen
Indexierungstimer und den Kompetenzimport je Fach. OIDC und WebDAV werden
unabhängig konfiguriert. Ohne Zugangsdaten bleiben beide Verbindungen deaktiviert.

Nach dem Neubau werden die Fachverwaltung, alle neun Fächer, der allgemeine
Dokumenttyp „Arbeitsplan“ und die Metadaten zur Nextcloud-Indexierung migriert.
Bestehende Deutschkennungen und Schulkonten bleiben erhalten.
