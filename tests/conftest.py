"""Gemeinsame Vorbereitung der Tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth.models import Group

from deutsch import gliederung
from kern.models import (
    ROLLE_ADMINISTRATION,
    ROLLE_LEHRKRAFT,
    ROLLE_LESEND,
    ROLLE_REDAKTION,
    Gruppenart,
    Gruppenprofil,
    Nutzer,
)

BASIS = Path(__file__).resolve().parent.parent

#: Die Dateien aus SPEC.md §16. Sie liegen im Projektverzeichnis.
KOMPETENZ_JSON = BASIS / "kompetenzerwartungen_lp2021.json"
ARBEITSMAPPE = BASIS / "Datenmodell_Arbeitsplan_Deutsch.xlsx"


@pytest.fixture
def kompetenz_json() -> Path:
    if not KOMPETENZ_JSON.exists():
        pytest.skip(f"{KOMPETENZ_JSON.name} fehlt im Projektverzeichnis.")
    return KOMPETENZ_JSON


@pytest.fixture
def arbeitsmappe() -> Path:
    if not ARBEITSMAPPE.exists():
        pytest.skip(f"{ARBEITSMAPPE.name} fehlt im Projektverzeichnis.")
    return ARBEITSMAPPE


@pytest.fixture
def rollen(db) -> dict[str, Group]:
    """Die vier Rollen – wie „manage.py rollen_einrichten“ sie anlegt."""
    gruppen = {}
    for name in (ROLLE_ADMINISTRATION, ROLLE_REDAKTION, ROLLE_LEHRKRAFT, ROLLE_LESEND):
        gruppe, _ = Group.objects.get_or_create(name=name)
        Gruppenprofil.objects.get_or_create(gruppe=gruppe, defaults={"art": Gruppenart.ROLLE})
        gruppen[name] = gruppe
    return gruppen


@pytest.fixture
def arbeitsgruppe(db) -> Group:
    gruppe, _ = Group.objects.get_or_create(name="Jahrgang 3")
    Gruppenprofil.objects.get_or_create(
        gruppe=gruppe, defaults={"art": Gruppenart.ARBEITSGRUPPE}
    )
    return gruppe


def _nutzer_mit_rolle(rollen, rolle: str, email: str) -> Nutzer:
    nutzer = Nutzer.objects.create_user(
        email=email, password="testpasswort-sehr-lang", anzeigename=rolle
    )
    nutzer.groups.add(rollen[rolle])
    return nutzer


@pytest.fixture
def admin_nutzer(rollen) -> Nutzer:
    return _nutzer_mit_rolle(rollen, ROLLE_ADMINISTRATION, "admin@example.org")


@pytest.fixture
def redaktion_nutzer(rollen) -> Nutzer:
    return _nutzer_mit_rolle(rollen, ROLLE_REDAKTION, "redaktion@example.org")


@pytest.fixture
def lehrkraft(rollen) -> Nutzer:
    return _nutzer_mit_rolle(rollen, ROLLE_LEHRKRAFT, "lehrkraft@example.org")


@pytest.fixture
def andere_lehrkraft(rollen) -> Nutzer:
    return _nutzer_mit_rolle(rollen, ROLLE_LEHRKRAFT, "andere@example.org")


@pytest.fixture
def lesend_nutzer(rollen) -> Nutzer:
    return _nutzer_mit_rolle(rollen, ROLLE_LESEND, "ogs@example.org")


@pytest.fixture
def dokument(db):
    """Arbeitsplan Deutsch mit vollständiger Gliederung."""
    dok, _, _ = gliederung.dokument_anlegen()
    return dok


@pytest.fixture
def kompetenzen(db, kompetenz_json):
    """Alle 117 Kompetenzerwartungen des Lehrplans."""
    from fachdaten.importe import importieren

    importieren(kompetenz_json)
    from fachdaten.models import Kompetenzerwartung

    return Kompetenzerwartung.objects.all()


@pytest.fixture
def importierter_arbeitsplan(dokument, kompetenzen, arbeitsmappe):
    """Dokument mit den beiden Beispielzeilen der Arbeitsmappe."""
    from deutsch.import_xlsx import uebernehmen

    bericht = uebernehmen(arbeitsmappe, dokument, mit_beispielen=True)
    assert bericht.ok, bericht.als_text()
    return dokument
