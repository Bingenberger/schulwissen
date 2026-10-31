"""Optimistische Schreibprüfung; alle beteiligten Schreibwege sperren zuerst das Dokument."""

import hashlib
import json

from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q

from kern.models import PFLEGE_FELDER, Anhang, Dokument, Eintragsversion, Verlinkung

UNGEPRUEFT = object()  # Nur für ausdrücklich aktuelle, vertrauenswürdige Import-/CLI-Aufrufe.
SALT = "schulwissen-schreibstand-v1"


class Schreibkonflikt(Exception):
    pass


def _hash(wert):
    return hashlib.sha256(
        json.dumps(wert, cls=DjangoJSONEncoder, sort_keys=True).encode()
    ).hexdigest()


def schreibstand(eintrag):
    if eintrag is None:
        return None
    return _hash(
        {
            "eintrag": {
                f: getattr(eintrag, f)
                for f in (
                    "pk",
                    "dokument_id",
                    "kennung",
                    "eintragstyp",
                    "titel",
                    "status",
                    "daten",
                    "eltern_id",
                    "position",
                    "verantwortlich_gruppe_id",
                    "verantwortlich_person_id",
                    "verantwortlich_text",
                    "fassung_stand",
                    "geaendert_am",
                    *[
                        f + "_id"
                        if f in ("pflege_funktion", "pflege_vertretung", "ersetzt_durch")
                        else f
                        for f in PFLEGE_FELDER
                    ],
                )
            },
            "version": eintrag.versionen.order_by("-versionsnummer")
            .values("pk", "versionsnummer", "status", "beschluss_id")
            .first(),
            "verweise": list(eintrag.verlinkungen.order_by("pk").values()),
            "anhaenge": list(eintrag.anhaenge.order_by("pk").values("pk", "geaendert_am")),
        }
    )


def dokumentstand(dokument):
    return _hash(
        {
            "dokument": Dokument.objects.filter(pk=dokument.pk).values().get(),
            "eintraege": list(
                dokument.eintraege.order_by("pk").values(
                    "pk",
                    "kennung",
                    "eintragstyp",
                    "titel",
                    "status",
                    "daten",
                    "eltern_id",
                    "position",
                    "verantwortlich_gruppe_id",
                    "verantwortlich_person_id",
                    "verantwortlich_text",
                    "fassung_stand",
                    "geaendert_am",
                    *[
                        f + "_id"
                        if f in ("pflege_funktion", "pflege_vertretung", "ersetzt_durch")
                        else f
                        for f in PFLEGE_FELDER
                    ],
                )
            ),
            "versionen": list(
                Eintragsversion.objects.filter(eintrag__dokument=dokument)
                .order_by("pk")
                .values("pk", "status", "beschluss_id", "versionsnummer")
            ),
            "verweise": list(
                Verlinkung.objects.filter(von_eintrag__dokument=dokument).order_by("pk").values()
            ),
            "anhaenge": list(
                Anhang.objects.filter(Q(dokument=dokument) | Q(eintrag__dokument=dokument))
                .order_by("pk")
                .values("pk", "geaendert_am")
            ),
        }
    )


def token_fuer_eintrag(nutzer, eintrag):
    return signing.dumps(
        {
            "nutzer": nutzer.pk,
            "dokument": eintrag.dokument_id,
            "eintrag": eintrag.pk,
            "kennung": eintrag.kennung,
            "eintragstyp": eintrag.eintragstyp,
            "version": eintrag.versionen.order_by("-versionsnummer")
            .values_list("pk", flat=True)
            .first(),
            "stand": schreibstand(eintrag),
            "art": "eintrag",
        },
        salt=SALT,
    )


def token_lesen(token, nutzer, dokument, eintrag=None, inhalt=None, kennung=None):
    try:
        daten = signing.loads(token or "", salt=SALT)
        gueltig = daten["nutzer"] == nutzer.pk and daten["dokument"] == dokument.pk
        if eintrag is not None:
            gueltig = gueltig and daten["art"] == "eintrag" and daten["eintrag"] == eintrag.pk
        elif kennung is not None:
            gueltig = gueltig and daten["art"] == "eintrag" and daten["kennung"] == kennung
            gueltig = (
                gueltig
                and isinstance(daten["eintrag"], int)
                and isinstance(daten["eintragstyp"], str)
            )
        else:
            gueltig = gueltig and daten["art"] == "import" and daten["inhalt"] == _hash(inhalt)
        if not gueltig or not isinstance(daten["stand"], str):
            raise ValueError("Unpassender Bearbeitungsstand")
        return daten
    except (signing.BadSignature, KeyError, TypeError, AssertionError, ValueError) as fehler:
        raise Schreibkonflikt(
            "Der Bearbeitungsstand fehlt oder ist ungültig. "
            "Bitte öffne den aktuellen Stand neu; deine Eingabe bleibt hier erhalten."
        ) from fehler


def token_fuer_import(nutzer, dokument, inhalt):
    return signing.dumps(
        {
            "nutzer": nutzer.pk,
            "dokument": dokument.pk,
            "art": "import",
            "inhalt": _hash(inhalt),
            "stand": dokumentstand(dokument),
        },
        salt=SALT,
    )


def pruefe_stand(eintrag, erwartet):
    if erwartet is not UNGEPRUEFT and schreibstand(eintrag) != erwartet:
        raise Schreibkonflikt(
            "Der Eintrag wurde inzwischen geändert. Deine Eingabe wurde nicht gespeichert. "
            "Bitte vergleiche die Änderungen."
        )
