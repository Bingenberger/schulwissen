---
name: nextcloud-oidc-unter-plattform
description: "Offen seit 2026-11-09 – Nextcloud-OIDC lässt sich unter der Schulplattform nicht konfigurieren; Plattformerweiterung geplant, von einem anderen Rechner aus"
metadata:
  node_type: memory
  type: project
  originSessionId: 12d5a0fa-175c-4334-ab90-26c697bb160b
  modified: 2026-11-09T18:25:14.784Z
---

Schulwissen läuft bei dieser Schule im Rahmen der Schulplattform (Repo `/home/foerster_schule/Schulplattform`). Dort greift die `.env` des Schulwissen-Repos nicht: Compose liest nur `apps/schulwissen/docker-compose.yml` + `generated/schulwissen.yml`, und das Override setzt `env_file: !override /var/lib/schulplattform/runtime/wissen.env`. Diese Datei wird aus `catalogue.py` generiert und bei jedem `render()` überschrieben; `platform.toml` erlaubt pro App keine zusätzlichen Schlüssel (`additionalProperties: false`). Für `SW_OIDC_*` fehlt damit jeder vorgesehene Platz.

Geplant (Stand 2026-11-09 noch nicht begonnen, soll von einem anderen Rechner aus erfolgen): Erweiterung im Plattform-Repo nach dem Muster von `youtube-key`/`gallery-ai-key` – Schemaschlüssel `nextcloud_issuer`/`nextcloud_discovery_url`/`nextcloud_client_id`, Platzhalter `{oidc_block}` in der `wissen.env`-Vorlage, Secret `wissen-oidc`, neuer Befehl `./install.sh nextcloud-oidc`, danach signierter Release über `scripts/make_release.py`.

**Why:** Die Einrichtungsanleitung in `PHASE4.md` beschreibt nur den Standalone-Weg über die `.env` und führt unter der Plattform in die Irre.

**How to apply:** Bei Fragen zu `SW_*`-Einstellungen im Echtbetrieb immer zuerst klären, ob Plattform oder Standalone gemeint ist. Der `SW_OIDC_CLIENT_SECRET_FILE`-Weg darf nur eingetragen werden, wenn die Secretdatei gefüllt ist – `umgebung.text` prüft `_FILE` vor dem Standardwert und bricht bei leerer Datei den Start ab.
