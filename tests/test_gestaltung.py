"""Die Komponentenübersicht bleibt auf die Administration beschränkt."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_styleguide_verlangt_anmeldung(client):
    antwort = client.get(reverse("kern:styleguide"))
    assert antwort.status_code == 302
    assert "anmelden" in antwort["Location"]


def test_administration_sieht_styleguide(client, admin_nutzer):
    client.force_login(admin_nutzer)
    antwort = client.get(reverse("kern:styleguide"))
    assert antwort.status_code == 200
    assert "So sieht Schulwissen aus." in antwort.content.decode()


@pytest.mark.parametrize("konto", ["lehrkraft", "redaktion_nutzer", "lesend_nutzer"])
def test_andere_rollen_sehen_keinen_styleguide(client, request, konto):
    client.force_login(request.getfixturevalue(konto))
    assert client.get(reverse("kern:styleguide")).status_code == 403


def test_dokumentkarten_zeigen_lesenden_beschlossene_metadaten(
    client, lesend_nutzer, importierter_arbeitsplan
):
    from kern.models import Status

    eintrag = importierter_arbeitsplan.eintraege.get(kennung="V-3-01")
    eintrag.versionen.create(
        versionsnummer=eintrag.versionen.count() + 1,
        titel="Gültiges Vorhaben",
        status=Status.BESCHLOSSEN,
        daten={"jahrgang": 2, "quartal": "Q1", "zeitumfang_std": 12},
    )
    eintrag.titel = "Vertraulicher neuer Titel"
    eintrag.daten = {"jahrgang": 4, "quartal": "Q4", "zeitumfang_std": 999}
    eintrag.save()
    client.force_login(lesend_nutzer)
    antwort = client.get(reverse("kern:dokument", args=[eintrag.dokument.schluessel]))
    karte = next(
        k
        for name, karten in antwort.context["kartengruppen"]
        for k in karten
        if k["eintrag"].pk == eintrag.pk
    )
    assert karte["titel"] == "Gültiges Vorhaben"
    assert karte["daten"] == {"jahrgang": 2, "quartal": "Q1", "zeitumfang_std": 12}
    assert "Vertraulicher neuer Titel" not in antwort.content.decode()
