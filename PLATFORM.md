# Container- und Plattformvertrag

Die eigenständige Compose-Datei bleibt verwendbar. Migrationen laufen jetzt
explizit und exklusiv statt bei jedem Webprozessstart:

```sh
docker compose build
docker compose run --rm app python manage.py platform_migrate
docker compose up -d
```

Vor einem bestehenden Deployment zuerst konsistent sichern und ein Wartungsfenster
nutzen. Der neue Migrationsjob verwendet eine PostgreSQL-Advisory-Sperre und richtet
danach die bisherigen Fachrollen ein. Nutzer- und Gruppen-IDs bleiben bestehen.

`/health/live` benötigt keine Datenbank; `/health/ready` prüft Datenbank und
ausstehende Django-Migrationen. Kein externer KI-/SMTP-Dienst beeinflusst Liveness.
Der bisherige Endpunkt `/gesundheit` bleibt bestehen.

`SW_*`-Namen bleiben erhalten. Für Text-/Secretwerte ist zusätzlich `SW_*_FILE`
möglich; eine konfigurierte Datei hat Vorrang. Nur die eigene App erhält ihre
Dateien. Das Plattformprofil verwendet eine separate Datenbankrolle ohne
Superuser-, Rollenverwaltungs- und Datenbankerstellungsrechte.

`SW_PROXY_IPS` enthält explizite Proxy-IP-Adressen, keine Wildcards. Forwarded-Header
von anderen IPs werden vor der Django-Sicherheitsmiddleware entfernt. Standalone
ist die Vorgabe Loopback; beim Plattformstart wird die interne Caddy-Adresse
ermittelt. Backendports werden durch das Override entfernt.

PDF-Anfragen teilen über alle Worker einen nicht blockierenden flock-Slot im
Container. Überlauf antwortet mit 503 und Retry-After. JSON-Exporte werden nicht
durch diesen Slot blockiert. Mehrere Container benötigen weiterhin eine gemeinsame
externe Begrenzung; der aktuelle Betrieb sieht eine Appinstanz vor.

Der Imagebuild sammelt statische Dateien im Produktionsmodus, damit das von
WhiteNoise benötigte Manifest vorhanden ist. Zwei Worker sind Compose-Vorgabe.
Das Entwicklungsimage wird lokal getestet und ist kein veröffentlichtes Release.
Nextcloud-OIDC bleibt optional; keine Änderung oder Zusage zentraler Sperrung.
