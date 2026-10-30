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
