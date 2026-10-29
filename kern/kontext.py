"""Werte, die jede Vorlage braucht."""

from __future__ import annotations

from kern import rechte


def oberflaeche(request) -> dict:
    nutzer = getattr(request, "user", None)
    return {
        "ist_administration": rechte.ist_administration(nutzer),
        "ist_redaktion": rechte.ist_redaktion(nutzer),
        "ist_lehrkraft": rechte.ist_lehrkraft(nutzer),
        "ist_nur_lesend": rechte.ist_nur_lesend(nutzer),
    }
