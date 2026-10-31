"""Werte, die jede Vorlage braucht."""

from __future__ import annotations

from kern import rechte


def oberflaeche(request) -> dict:
    nutzer = getattr(request, "user", None)
    from kern.oidc import ist_eingerichtet

    return {
        "oidc_eingerichtet": ist_eingerichtet(),
        "ist_administration": rechte.ist_administration(nutzer),
        "ist_redaktion": rechte.darf_vorlage(nutzer),
        "ist_lehrkraft": rechte.ist_lehrkraft(nutzer),
        "ist_nur_lesend": rechte.ist_nur_lesend(nutzer),
    }
