"""Nextcloud-Anmeldung über OIDC mit expliziter Kontoverknüpfung."""

import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from kern.models import OIDCIdentitaet


def ist_eingerichtet():
    return bool(settings.OIDC_ISSUER and settings.OIDC_CLIENT_ID and settings.OIDC_CLIENT_SECRET)


def client():
    from authlib.integrations.django_client import OAuth

    if not ist_eingerichtet():
        raise Http404("Die Nextcloud-Anmeldung ist noch nicht eingerichtet.")
    if not settings.OIDC_ISSUER.startswith(
        "https://"
    ) or not settings.OIDC_DISCOVERY_URL.startswith("https://"):
        raise PermissionDenied("Der Nextcloud-Anbieter muss HTTPS verwenden.")
    oauth = OAuth()
    return oauth.register(
        "nextcloud",
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET,
        server_metadata_url=settings.OIDC_DISCOVERY_URL,
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
            "timeout": 15,
        },
    )


def _start(request, verknuepfen=False):
    anbieter = client()
    metadata = anbieter.load_server_metadata()
    if metadata.get("issuer") != settings.OIDC_ISSUER:
        raise PermissionDenied("Die Anbieterkennung stimmt nicht mit der Konfiguration überein.")
    for feld in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(metadata.get(feld, "")).startswith("https://"):
            raise PermissionDenied("Die Nextcloud-Anmeldeendpunkte müssen HTTPS verwenden.")
    nonce = secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    request.session["oidc_vorgang"] = {
        "state": state,
        "nonce": nonce,
        "zeit": timezone.now().timestamp(),
        "nutzer": request.user.pk if verknuepfen else None,
    }
    return anbieter.authorize_redirect(
        request,
        settings.OEFFENTLICHE_URL + "/anmelden/nextcloud/callback",
        state=state,
        nonce=nonce,
        **({"prompt": "login"} if verknuepfen else {}),
    )


def _start_mit_fehlerhinweis(request, verknuepfen=False):
    import requests
    from authlib.integrations.base_client.errors import OAuthError

    try:
        return _start(request, verknuepfen)
    except (requests.RequestException, OAuthError, ValueError, KeyError):
        messages.error(request, "Die Nextcloud-Anmeldung ist vorübergehend nicht erreichbar.")
        return redirect("kern:startseite" if verknuepfen else "kern:anmelden")


@require_GET
def anmelden(request):
    return _start_mit_fehlerhinweis(request)


@login_required
@require_POST
def verbinden(request):
    return _start_mit_fehlerhinweis(request, verknuepfen=True)


@require_GET
def callback(request):
    import requests
    from authlib.integrations.base_client.errors import OAuthError
    from joserfc.errors import JoseError

    if not ist_eingerichtet():
        raise Http404("Die Nextcloud-Anmeldung ist nicht eingerichtet.")
    vorgang = request.session.pop("oidc_vorgang", None)
    if (
        not vorgang
        or not secrets.compare_digest(
            request.GET.get("state", "").encode(), vorgang["state"].encode()
        )
        or not 0 <= timezone.now().timestamp() - vorgang["zeit"] <= 600
    ):
        raise PermissionDenied("Die Anmeldung ist abgelaufen oder ungültig. Bitte erneut beginnen.")
    try:
        token = client().authorize_access_token(
            request, claims_options={"iss": {"essential": True, "value": settings.OIDC_ISSUER}}
        )
        claims = token.get("userinfo") or {}
        # Zusätzlich zur Bibliotheksprüfung die zuvor erwartete Nonce erzwingen.
        if (
            not token.get("id_token")
            or claims.get("iss") != settings.OIDC_ISSUER
            or claims.get("nonce") != vorgang["nonce"]
            or not isinstance(claims.get("sub"), str)
            or not 0 < len(claims["sub"]) <= 255
        ):
            raise PermissionDenied("Die Nextcloud-Identität konnte nicht bestätigt werden.")
    except (OAuthError, JoseError, requests.RequestException, ValueError, KeyError):
        messages.error(
            request,
            "Die Nextcloud-Anmeldung konnte nicht bestätigt werden. Bitte erneut versuchen.",
        )
        return redirect("kern:anmelden")

    identitaet = (
        OIDCIdentitaet.objects.select_related("nutzer")
        .filter(issuer=settings.OIDC_ISSUER, subject=claims["sub"])
        .first()
    )
    if vorgang["nutzer"] is not None:
        if (
            not request.user.is_authenticated
            or not request.user.is_active
            or request.user.pk != vorgang["nutzer"]
        ):
            raise PermissionDenied("Zum Verbinden muss dasselbe Schulkonto noch angemeldet sein.")
        if identitaet and identitaet.nutzer_id != request.user.pk:
            raise PermissionDenied(
                "Diese Nextcloud-Identität ist bereits einem anderen Konto zugeordnet."
            )
        try:
            with transaction.atomic():
                OIDCIdentitaet.objects.get_or_create(
                    issuer=settings.OIDC_ISSUER,
                    subject=claims["sub"],
                    defaults={"nutzer": request.user, "erstellt_von": request.user},
                )
        except IntegrityError as fehler:
            raise PermissionDenied(
                "Für dein Konto ist bereits eine andere Nextcloud-Identität verbunden."
            ) from fehler
        messages.success(request, "Dein Konto ist jetzt mit Nextcloud verbunden.")
        return redirect("kern:startseite")
    if not identitaet or not identitaet.nutzer.is_active:
        # Eine gleiche E-Mail-Adresse allein ist keine Kontoverknüpfung.
        raise PermissionDenied(
            "Diese Nextcloud-Identität ist keinem aktiven Schulkonto zugeordnet. "
            "Bitte zuerst lokal anmelden und das Konto verbinden."
        )
    login(request, identitaet.nutzer, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("kern:startseite")
