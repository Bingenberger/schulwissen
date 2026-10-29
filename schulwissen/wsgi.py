"""WSGI-Einstiegspunkt für gunicorn."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schulwissen.einstellungen")

anwendung = get_wsgi_application()

# gunicorn sucht ohne weitere Angabe nach „application“.
application = anwendung
