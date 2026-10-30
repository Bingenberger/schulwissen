"""Django-Einstellungen der Schulwissen-Plattform.

Alles, was sich je Installation unterscheidet, kommt aus Umgebungsvariablen mit
dem Prefix ``SW_`` (siehe ``.env.example``). Im Repository stehen keine Geheimnisse.
"""

from __future__ import annotations

from pathlib import Path

from schulwissen import umgebung

BASIS = Path(__file__).resolve().parent.parent

# --- Betrieb ---------------------------------------------------------------

DEBUG = umgebung.schalter("SW_DEBUG", False)

if DEBUG:
    # In der Entwicklung soll die App ohne .env starten können.
    SECRET_KEY = umgebung.text("SW_SECRET_KEY", "nur-fuer-entwicklung-unsicher")
    ALLOWED_HOSTS = umgebung.liste("SW_ALLOWED_HOSTS", "localhost,127.0.0.1")
else:
    # Im Echtbetrieb sind beide Pflicht: ein fehlender Schlüssel oder eine offene
    # Host-Liste soll den Start abbrechen, nicht stillschweigend unsicher laufen.
    SECRET_KEY = umgebung.text("SW_SECRET_KEY")
    ALLOWED_HOSTS = umgebung.liste("SW_ALLOWED_HOSTS")
    if not ALLOWED_HOSTS:
        raise umgebung.EinstellungFehlt(
            "SW_ALLOWED_HOSTS fehlt. Dort gehört der Hostname der App hinein, "
            "z. B. schulwissen.ggs-ndk.de. Siehe DEPLOYMENT.md."
        )

# Vollständige Adresse, unter der die App erreichbar ist – ohne „/“ am Ende.
# Steht in Mails (Passwort-Reset) und in der CSRF-Prüfung.
OEFFENTLICHE_URL = umgebung.text("SW_OEFFENTLICHE_URL", "http://localhost:8000").rstrip("/")
CSRF_TRUSTED_ORIGINS = [OEFFENTLICHE_URL]

# nginx terminiert HTTPS und setzt diesen Header. Ohne ihn hält Django jede
# Anfrage für unverschlüsselt und baut Links mit http:// zusammen.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = umgebung.schalter("SW_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# HSTS: Der Browser merkt sich, dass diese Adresse nur über HTTPS kommt.
# Erst einschalten, wenn HTTPS sicher läuft – die Festlegung gilt im Browser
# für die eingestellte Dauer und lässt sich nicht zurücknehmen. Darum mit
# SW_HSTS_TAGE=0 abschaltbar.
_hsts_tage = int(umgebung.text("SW_HSTS_TAGE", "0" if DEBUG else "365"))
SECURE_HSTS_SECONDS = _hsts_tage * 24 * 60 * 60
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Die Umleitung von http auf https macht nginx (certbot trägt sie ein).
# In Django eingeschaltet, gäbe es ohne HTTPS eine Endlosschleife.
SECURE_SSL_REDIRECT = umgebung.schalter("SW_SSL_UMLEITUNG", False)

# --- Anwendungen -----------------------------------------------------------

INSTALLED_APPS = [
    "kern.apps.KernConfig",
    "eintragstypen.apps.EintragstypenConfig",
    "fachdaten.apps.FachdatenConfig",
    "deutsch.apps.DeutschConfig",
    "suche.apps.SucheConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # whitenoise liefert die statischen Dateien aus – auch in der Entwicklung,
    # denn hinter gunicorn tut das sonst niemand.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "schulwissen.urls"
WSGI_APPLICATION = "schulwissen.wsgi.anwendung"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASIS / "vorlagen"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "kern.kontext.oberflaeche",
            ],
        },
    },
]

# --- Datenbank -------------------------------------------------------------

DATABASES = {"default": umgebung.datenbank("SW_DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Anmeldung -------------------------------------------------------------

AUTH_USER_MODEL = "kern.Nutzer"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "kern:anmelden"
LOGIN_REDIRECT_URL = "kern:startseite"
LOGOUT_REDIRECT_URL = "kern:anmelden"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Mail (Passwort-Reset) -------------------------------------------------

if umgebung.text("SW_SMTP_HOST", ""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = umgebung.text("SW_SMTP_HOST")
    EMAIL_PORT = int(umgebung.text("SW_SMTP_PORT", "587"))
    EMAIL_HOST_USER = umgebung.text("SW_SMTP_NUTZER", "")
    EMAIL_HOST_PASSWORD = umgebung.text("SW_SMTP_PASSWORT", "")
    EMAIL_USE_TLS = umgebung.schalter("SW_SMTP_TLS", True)
else:
    # Ohne SMTP-Zugang landen Mails im Containerprotokoll. Für den Passwort-Reset
    # im Echtbetrieb muss SW_SMTP_HOST gesetzt sein – DEPLOYMENT.md sagt das auch.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = umgebung.text("SW_ABSENDER", "schulwissen@localhost")

# --- Nextcloud (SPEC.md §10, Stufe 1) --------------------------------------

# Ein technisches Konto mit App-Passwort darf die Ordner lesen, damit sich
# Dateien im Browser durchklicken lassen. Ohne diese Werte bleibt die
# Dateiauswahl einfach aus – die App läuft trotzdem.
NEXTCLOUD_URL = umgebung.text("SW_NEXTCLOUD_URL", "").rstrip("/")
NEXTCLOUD_NUTZER = umgebung.text("SW_NEXTCLOUD_NUTZER", "")
NEXTCLOUD_PASSWORT = umgebung.text("SW_NEXTCLOUD_PASSWORT", "")

# --- Sprache und Zeit ------------------------------------------------------

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

# --- Dateien ---------------------------------------------------------------

STATIC_URL = "statisch/"
STATIC_ROOT = BASIS / "statisch"
STATICFILES_DIRS = [BASIS / "dateien"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Im Echtbetrieb mit Prüfsumme im Dateinamen, damit Browser zwischenspeichern
        # dürfen. In der Entwicklung und in Tests ohne – dort gibt es kein
        # collectstatic-Verzeichnis.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# In der Entwicklung nimmt whitenoise die Dateien direkt aus „dateien/“, ohne
# dass vorher collectstatic laufen muss.
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "medien/"
MEDIA_ROOT = Path(umgebung.text("SW_MEDIEN_VERZEICHNIS", str(BASIS / "medien")))

# Anhänge: 50 MB je Datei genügen für Konzepte und Scans.
DATA_UPLOAD_MAX_MEMORY_SIZE = 52_428_800
FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880

# --- Protokollierung -------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"knapp": {"format": "{levelname} {name}: {message}", "style": "{"}},
    "handlers": {"konsole": {"class": "logging.StreamHandler", "formatter": "knapp"}},
    "root": {"handlers": ["konsole"], "level": "INFO"},
    "loggers": {"django.request": {"level": "WARNING"}},
}

# Nextcloud als OpenID-Connect-Anbieter (optional).
OIDC_ISSUER = umgebung.text("SW_OIDC_ISSUER", "")
OIDC_DISCOVERY_URL = umgebung.text(
    "SW_OIDC_DISCOVERY_URL",
    OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration" if OIDC_ISSUER else "",
)
OIDC_CLIENT_ID = umgebung.text("SW_OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = umgebung.text("SW_OIDC_CLIENT_SECRET", "")
NEXTCLOUD_MAX_BYTES = int(umgebung.text("SW_NEXTCLOUD_MAX_MB", "25")) * 1024 * 1024
