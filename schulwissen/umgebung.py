"""Kleine Helfer, um Einstellungen aus Umgebungsvariablen zu lesen.

Alle Variablen der App beginnen mit ``SW_``. Statt einer zusätzlichen Bibliothek
genügen hier drei Funktionen – das hält die Abhängigkeiten klein und macht in
``einstellungen.py`` sofort sichtbar, was woher kommt.
"""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse


class EinstellungFehlt(Exception):
    """Eine Pflichtvariable ist nicht gesetzt."""


_FEHLT = object()


def text(name: str, standard: object = _FEHLT) -> str:
    wert = os.environ.get(name)
    if wert:
        return wert
    if standard is _FEHLT:
        raise EinstellungFehlt(
            f"Die Umgebungsvariable {name} fehlt. Siehe .env.example und DEPLOYMENT.md."
        )
    return str(standard)


def schalter(name: str, standard: bool = False) -> bool:
    wert = os.environ.get(name)
    if wert is None or wert == "":
        return standard
    return wert.strip().lower() in {"1", "true", "ja", "yes", "on"}


def liste(name: str, standard: str = "") -> list[str]:
    """Kommagetrennte Liste, Leerzeichen werden ignoriert."""
    return [teil.strip() for teil in text(name, standard).split(",") if teil.strip()]


def datenbank(name: str) -> dict:
    """``postgresql://nutzer:passwort@host:port/datenbank`` in Djangos Format."""
    url = urlparse(text(name))
    if url.scheme not in {"postgres", "postgresql"}:
        raise EinstellungFehlt(
            f"{name} muss mit postgresql:// beginnen, gefunden: {url.scheme or '(leer)'}"
        )
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": url.path.lstrip("/"),
        "USER": unquote(url.username or ""),
        "PASSWORD": unquote(url.password or ""),
        "HOST": url.hostname or "",
        "PORT": str(url.port or ""),
        "CONN_MAX_AGE": 60,
    }
