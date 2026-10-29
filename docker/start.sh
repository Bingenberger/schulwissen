#!/bin/sh
# Startet die App: erst die Datenbank auf den neuesten Stand bringen, dann gunicorn.
set -e

echo "Schulwissen: Migrationen anwenden …"
python manage.py migrate --noinput

echo "Schulwissen: Rollen und Stammdaten prüfen …"
python manage.py rollen_einrichten

exec gunicorn schulwissen.wsgi:anwendung \
    --bind 0.0.0.0:8000 \
    --workers "${SW_WORKER:-3}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
