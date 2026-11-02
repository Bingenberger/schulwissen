#!/bin/sh
# Migrationen explizit vor dem Start: manage.py platform_migrate
set -e

exec gunicorn schulwissen.wsgi:anwendung \
    --bind 0.0.0.0:8000 \
    --workers "${SW_WORKER:-3}" \
    --timeout 120 \
    --worker-tmp-dir /tmp \
    --error-logfile -
