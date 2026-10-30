"""Ansichten des Kerns: Startseite, Dokument, Eintrag lesen und bearbeiten."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from eintragstypen import dienste
from eintragstypen.formulare import AnhangFormular, EintragFormular, KommentarFormular
from eintragstypen.registry import registry
from fachdaten.models import Bereich, Stufe
from kern import rechte
from kern.models import (
    Anhang,
    Dokument,
    Eintrag,
    Kommentar,
    Status,
    Verlinkung,
    Zieltyp,
)


@login_required
def startseite(request):
    """Großes Suchfeld, darunter wenige Einstiege (SPEC.md §9).

    Die Suche selbst kommt in Phase 2; das Feld steht schon hier, damit das
    Kollegium von Anfang an denselben Einstieg sieht.
    """
    sichtbar = rechte.sichtbare_eintraege(request.user, Eintrag.objects.all())

    zuletzt_beschlossen = (
        sichtbar.filter(status=Status.BESCHLOSSEN)
        .select_related("dokument")
        .order_by("-geaendert_am")[:5]
    )
    eigene_entwuerfe = (
        Eintrag.objects.filter(
            status__in=(Status.IDEE, Status.ENTWURF),
        )
        .filter(Q(erstellt_von=request.user) | Q(verantwortlich_person=request.user))
        .select_related("dokument")
        .order_by("-geaendert_am")[:8]
        if rechte.ist_lehrkraft(request.user)
        else Eintrag.objects.none()
    )

    return render(
        request,
        "kern/startseite.html",
        {
            "dokumente": Dokument.objects.select_related("dokumenttyp").annotate(
                anzahl=Count("eintraege")
            ),
            "zuletzt_beschlossen": zuletzt_beschlossen,
            "eigene_entwuerfe": eigene_entwuerfe,
        },
    )


def _gliederungsbaum(dokument, nutzer):
    """Kapitelbaum für die linke Navigation.

    Zwei Besonderheiten für Konten, die keine Entwürfe sehen dürfen:

    * Die **Kapitel** stehen immer im Baum, auch wenn ihr Inhalt noch nicht
      freigegeben ist. Sonst fiele die ganze Gliederung weg – und mit ihr die
      Orientierung, denn ein freigegebenes Vorhaben hängt unter einem Kapitel,
      das selbst noch Entwurf ist. Nicht freigegebene Kapitel sind als solche
      gekennzeichnet und nicht anklickbar.
    * Gezeigt wird der Titel der **beschlossenen** Fassung, nicht der des
      Arbeitsstandes.
    """
    from kern.models import Eintragsversion

    alle_eintraege = list(dokument.eintraege.order_by("position", "kennung"))
    sichtbare = set(
        rechte.sichtbare_eintraege(nutzer, dokument.eintraege.all()).values_list("pk", flat=True)
    )

    beschlossene_titel: dict[int, str] = {}
    if not rechte.zeigt_entwurf(nutzer):
        beschlossene_titel = dict(
            Eintragsversion.objects.filter(
                eintrag__in=alle_eintraege, status=Status.BESCHLOSSEN
            ).values_list("eintrag_id", "titel")
        )

    def gehoert_in_den_baum(eintrag) -> bool:
        return eintrag.pk in sichtbare or eintrag.eintragstyp == "grundlagenkapitel"

    kinder: dict[int | None, list] = {}
    for eintrag in alle_eintraege:
        if gehoert_in_den_baum(eintrag):
            kinder.setdefault(eintrag.eltern_id, []).append(eintrag)

    def bauen(eltern_id, tiefe=0):
        zeilen = []
        for eintrag in kinder.get(eltern_id, []):
            zeilen.append(
                {
                    "eintrag": eintrag,
                    "tiefe": tiefe,
                    "titel": beschlossene_titel.get(eintrag.pk, eintrag.titel),
                    "lesbar": eintrag.pk in sichtbare,
                    # Wer die beschlossene Fassung sieht, soll auch deren
                    # Status sehen – nicht den des Arbeitsstandes.
                    "status": (
                        Status.BESCHLOSSEN if eintrag.pk in beschlossene_titel else eintrag.status
                    ),
                }
            )
            zeilen.extend(bauen(eintrag.pk, tiefe + 1))
        return zeilen

    return bauen(None)


@login_required
def dokument_ansehen(request, schluessel: str):
    dokument = get_object_or_404(
        Dokument.objects.select_related("dokumenttyp"), schluessel=schluessel
    )
    return render(
        request,
        "kern/dokument.html",
        {
            "dokument": dokument,
            "baum": _gliederungsbaum(dokument, request.user),
            "eintragstypen": [
                registry.holen(s)
                for s in (dokument.dokumenttyp.eintragstypen or [])
                if registry.bekannt(s)
            ],
        },
    )


def _eintrag_holen(request, schluessel: str, kennung: str) -> Eintrag:
    eintrag = get_object_or_404(
        Eintrag.objects.select_related("dokument", "dokument__dokumenttyp"),
        dokument__schluessel=schluessel,
        kennung=kennung,
    )
    if not rechte.darf_lesen(request.user, eintrag):
        raise PermissionDenied("Dieser Eintrag ist noch ein Entwurf und darum nicht freigegeben.")
    return eintrag


def _ruckverweise(eintrag: Eintrag):
    """„Wird verwendet in …“ – wer zeigt auf diesen Eintrag?"""
    return (
        Verlinkung.objects.filter(ziel_typ=Zieltyp.EINTRAG, ziel_id=str(eintrag.pk))
        .select_related("von_eintrag", "von_eintrag__dokument")
        .order_by("von_eintrag__kennung")
    )


def bloecke_zum_lesen(typ, daten: dict, verweise_je_feld: dict | None = None):
    """Blöcke mit gefüllten Feldern – für Leseansicht und alte Fassungen.

    ``verweise_je_feld`` bildet einen Feldschlüssel auf die Liste seiner
    Verweise ab. Für einen Eintrag kommen die aus der Datenbank, für eine
    gespeicherte Fassung aus ihrem Schnappschuss.
    """
    from eintragstypen.registry import Feldtyp

    verweise_je_feld = verweise_je_feld or {}
    daten = daten or {}

    for block, felder in typ.bloecke_mit_feldern(daten):
        zeilen = []
        for feld in felder:
            if feld.ist_verlinkung:
                ziele = verweise_je_feld.get(feld.schluessel) or []
                if ziele:
                    zeilen.append({"feld": feld, "verweise": ziele})
                continue
            wert = daten.get(feld.schluessel)
            if wert in (None, "", []):
                continue
            zeilen.append(
                {
                    "feld": feld,
                    "html": wert if feld.typ == Feldtyp.RICHTEXT else None,
                    "text": None if feld.typ == Feldtyp.RICHTEXT else feld.anzeige(wert),
                }
            )
        if zeilen:
            yield {"name": block, "felder": zeilen}


def _felder_zum_lesen(eintrag: Eintrag):
    """Blöcke des aktuellen Standes eines Eintrags."""
    verweise: dict[str, list] = {}
    for verlinkung in eintrag.verlinkungen.order_by("ziel_id"):
        verweise.setdefault(verlinkung.feld, []).append(verlinkung)
    return bloecke_zum_lesen(eintrag.typ, eintrag.daten, verweise)


def verweise_aus_schnappschuss(version) -> dict[str, list]:
    """Die Verweise einer gespeicherten Fassung, nach Feld geordnet.

    Sie kommen aus dem Schnappschuss, nicht aus der Datenbank – sonst zeigte
    eine alte Fassung die heutigen Kompetenzen.
    """
    from types import SimpleNamespace

    verweise: dict[str, list] = {}
    for verweis in version.verlinkungen or []:
        verweise.setdefault(verweis.get("feld", ""), []).append(
            SimpleNamespace(
                ziel_id=verweis.get("ziel_id", ""),
                beschriftung=verweis.get("beschriftung", ""),
            )
        )
    return verweise


@login_required
def eintrag_ansehen(request, schluessel: str, kennung: str):
    """Leseansicht zuerst – „Bearbeiten“ ist ein deutlicher Knopf (SPEC.md §12)."""
    eintrag = _eintrag_holen(request, schluessel, kennung)
    beschlossen = eintrag.beschlossene_version()

    offene_pflichtfelder = eintrag.typ.fehlende_pflichtfelder(
        eintrag.daten,
        [v.feld for v in eintrag.verlinkungen.all() if v.feld],
    )

    # Lesende sehen die zuletzt beschlossene Fassung, alle anderen den
    # Arbeitsstand (SPEC.md §6).
    zeigt_entwurf = rechte.zeigt_entwurf(request.user, eintrag)
    if not eintrag.typ_bekannt:
        return render(
            request,
            "kern/eintrag_unbekannt.html",
            {
                "dokument": eintrag.dokument,
                "eintrag": eintrag,
                "baum": _gliederungsbaum(eintrag.dokument, request.user),
                "ist_administration": rechte.ist_administration(request.user),
            },
        )

    if zeigt_entwurf or beschlossen is None:
        bloecke = list(_felder_zum_lesen(eintrag))
        angezeigter_titel = eintrag.titel
    else:
        bloecke = list(
            bloecke_zum_lesen(
                eintrag.typ, beschlossen.daten, verweise_aus_schnappschuss(beschlossen)
            )
        )
        angezeigter_titel = beschlossen.titel

    # Steht der Arbeitsstand neben einer beschlossenen Fassung, soll das
    # sichtbar sein – sonst hält man den Entwurf für geltendes Recht.
    entwurf_weicht_ab = bool(
        beschlossen is not None
        and eintrag.status != Status.BESCHLOSSEN
        and (eintrag.titel != beschlossen.titel or eintrag.daten != beschlossen.daten)
    )

    angezeigter_status = (
        eintrag.status if zeigt_entwurf or beschlossen is None else beschlossen.status
    )

    return render(
        request,
        "kern/eintrag.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "typ": eintrag.typ,
            "bloecke": bloecke,
            "angezeigter_titel": angezeigter_titel,
            "angezeigter_status": angezeigter_status,
            "angezeigter_status_text": Status(angezeigter_status).label,
            "zeigt_entwurf": zeigt_entwurf,
            "entwurf_weicht_ab": entwurf_weicht_ab,
            "baum": _gliederungsbaum(eintrag.dokument, request.user),
            "beschlossene_version": beschlossen,
            "beschluss": beschlossen.beschluss if beschlossen else None,
            "rueckverweise": _ruckverweise(eintrag),
            "kommentare": eintrag.kommentare.select_related("autor"),
            "kommentar_formular": KommentarFormular(),
            "anhang_formular": AnhangFormular(),
            "offene_pflichtfelder": offene_pflichtfelder,
            "darf_bearbeiten": rechte.darf_bearbeiten(request.user, eintrag),
            "darf_kommentieren": rechte.darf_kommentieren(request.user, eintrag),
        },
    )


@login_required
def eintrag_bearbeiten(request, schluessel: str, kennung: str):
    eintrag = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied(
            "Diesen Eintrag darf nur die verantwortliche Arbeitsgruppe oder die "
            "Redaktion bearbeiten."
        )
    if not eintrag.typ_bekannt:
        # Ohne Feldschema lässt sich keine Maske bauen.
        messages.error(
            request,
            f"„{eintrag.kennung}“ trägt den Eintragstyp „{eintrag.eintragstyp}“, "
            "den die App nicht kennt. Die Administration muss ihn in der "
            "Verwaltung richtigstellen.",
        )
        return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)

    if request.method == "POST":
        formular = EintragFormular(request.POST, eintragstyp=eintrag.eintragstyp, eintrag=eintrag)
        if formular.is_valid():
            antwort = _speichern(request, eintrag.dokument, formular, eintrag.kennung, eintrag)
            if antwort is not None:
                return antwort
    else:
        formular = EintragFormular(eintragstyp=eintrag.eintragstyp, eintrag=eintrag)

    return render(
        request,
        "kern/eintrag_bearbeiten.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "typ": eintrag.typ,
            "formular": formular,
            "baum": _gliederungsbaum(eintrag.dokument, request.user),
            # Filter der Kompetenzauswahl.
            "bereiche": Bereich.choices,
            "stufen": Stufe.choices,
        },
    )


@login_required
def eintrag_neu(request, schluessel: str, eintragstyp: str):
    """Neuen Eintrag anlegen. Die Kennung vergibt die App."""
    dokument = get_object_or_404(
        Dokument.objects.select_related("dokumenttyp"), schluessel=schluessel
    )
    if not rechte.darf_anlegen(request.user, dokument):
        raise PermissionDenied("Zum Anlegen von Einträgen fehlt die Rolle „Lehrkraft“.")
    if not registry.bekannt(eintragstyp):
        raise Http404(f"Unbekannter Eintragstyp „{eintragstyp}“.")
    typ = registry.holen(eintragstyp)
    if eintragstyp not in (dokument.dokumenttyp.eintragstypen or []):
        raise Http404(
            f"„{typ.name}“ ist im Dokumenttyp „{dokument.dokumenttyp.name}“ nicht vorgesehen."
        )

    if request.method == "POST":
        formular = EintragFormular(request.POST, eintragstyp=eintragstyp)
        if formular.is_valid():
            kennung = _kennung_vergeben(dokument, typ, formular)
            antwort = _speichern(request, dokument, formular, kennung, None)
            if antwort is not None:
                return antwort
    else:
        formular = EintragFormular(eintragstyp=eintragstyp)

    return render(
        request,
        "kern/eintrag_bearbeiten.html",
        {
            "dokument": dokument,
            "eintrag": None,
            "typ": typ,
            "formular": formular,
            "baum": _gliederungsbaum(dokument, request.user),
            "bereiche": Bereich.choices,
            "stufen": Stufe.choices,
        },
    )


def _kennung_vergeben(dokument, typ, formular) -> str:
    if not typ.kennung_muster:
        # Kapitel bekommen eine fortlaufende Kennung am Ende der Gliederung.
        return dokument.naechste_kennung("K-{nr:02d}")
    if "{jahrgang}" in typ.kennung_muster:
        jahrgang = formular.cleaned_data.get("f_jahrgang") or 1
        return typ.kennung_bauen(dokument, jahrgang=int(jahrgang))
    return typ.kennung_bauen(dokument)


def _speichern(request, dokument, formular, kennung: str, eintrag):
    """Prüft und speichert; gibt eine Weiterleitung zurück oder ``None``."""
    from deutsch import gliederung

    roh = formular.als_rohsatz(kennung)

    if eintrag is not None and roh.status != eintrag.status:
        if not rechte.darf_status_setzen(request.user, eintrag, roh.status):
            formular.add_error(
                "status",
                "Diesen Status darf nur die Redaktion oder die Administration setzen.",
            )
            return None

    befundsatz = dienste.pruefen(dokument, roh)
    if not befundsatz.ok:
        for befund in befundsatz.fehler:
            formular.add_error(None, befund.text)
        return None

    # Der Wechsel auf „abgestimmt in Gruppe“ setzt vollständige Pflichtfelder
    # voraus (SPEC.md §7.4). Die Maske sagt, was fehlt.
    if roh.status == Status.ABGESTIMMT and befundsatz.fehlende_pflichtfelder:
        namen = ", ".join(f.label for f in befundsatz.fehlende_pflichtfelder)
        formular.add_error(
            "status",
            f"„abgestimmt in Gruppe“ geht erst, wenn alle Pflichtfelder gefüllt sind. "
            f"Es fehlt noch: {namen}.",
        )
        return None

    eltern = None
    if eintrag is None and roh.eintragstyp in ("ritual", "vorhaben"):
        eltern = gliederung.sammelkapitel(dokument)

    gespeichert = dienste.speichern(dokument, befundsatz, nutzer=request.user, eltern=eltern)

    if gespeichert.verantwortlich_gruppe_id is None and eintrag is None:
        # Erstanlage: die erste Arbeitsgruppe des Nutzers übernimmt die
        # Verantwortung, damit die Gruppe den Entwurf weiterbearbeiten kann.
        from kern.models import Gruppenart

        gruppe = request.user.groups.filter(profil__art=Gruppenart.ARBEITSGRUPPE).first()
        if gruppe is not None:
            gespeichert.verantwortlich_gruppe = gruppe
            gespeichert.save(update_fields=["verantwortlich_gruppe"])

    if befundsatz.fehlende_pflichtfelder:
        namen = ", ".join(f.label for f in befundsatz.fehlende_pflichtfelder)
        messages.warning(
            request,
            f"Als Entwurf gespeichert. Für „abgestimmt in Gruppe“ fehlt noch: {namen}.",
        )
    else:
        messages.success(request, f"„{gespeichert.titel}“ wurde gespeichert.")

    return redirect("kern:eintrag", schluessel=dokument.schluessel, kennung=gespeichert.kennung)


@login_required
@require_POST
def kommentar_anlegen(request, schluessel: str, kennung: str):
    eintrag = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_kommentieren(request.user, eintrag):
        raise PermissionDenied("Kommentieren darf nur das Kollegium.")

    formular = KommentarFormular(request.POST)
    if formular.is_valid():
        Kommentar.objects.create(
            eintrag=eintrag,
            autor=request.user,
            erstellt_von=request.user,
            text=formular.cleaned_data["text"],
            feld=formular.cleaned_data.get("feld", ""),
        )
        messages.success(request, "Kommentar gespeichert.")
    else:
        messages.error(request, "Der Kommentar war leer.")
    return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)


@login_required
@require_POST
def kommentar_erledigen(request, schluessel: str, kennung: str, kommentar_id: int):
    eintrag = _eintrag_holen(request, schluessel, kennung)
    kommentar = get_object_or_404(Kommentar, pk=kommentar_id, eintrag=eintrag)
    if not rechte.darf_kommentar_erledigen(request.user, kommentar):
        raise PermissionDenied("Erledigen darf die Redaktion oder wer den Kommentar schrieb.")

    kommentar.erledigt = not kommentar.erledigt
    kommentar.erledigt_am = timezone.now() if kommentar.erledigt else None
    kommentar.erledigt_von = request.user if kommentar.erledigt else None
    kommentar.save(update_fields=["erledigt", "erledigt_am", "erledigt_von"])
    return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)


@login_required
@require_POST
def anhang_hochladen(request, schluessel: str, kennung: str):
    eintrag = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Anhänge darf nur anlegen, wer den Eintrag bearbeiten darf.")

    formular = AnhangFormular(request.POST, request.FILES)
    if not formular.is_valid():
        for fehler in formular.errors.values():
            messages.error(request, " ".join(fehler))
        return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)

    datei = formular.cleaned_data.get("datei")
    anhang = Anhang(
        eintrag=eintrag,
        dokument=eintrag.dokument,
        beschreibung=formular.cleaned_data.get("beschreibung", ""),
        nextcloud_link=formular.cleaned_data.get("nextcloud_link") or "",
        erstellt_von=request.user,
    )
    if datei is not None:
        anhang.datei = datei
        anhang.dateiname = datei.name
        anhang.mimetype = getattr(datei, "content_type", "") or ""
        anhang.groesse = datei.size
    else:
        anhang.dateiname = anhang.nextcloud_link.rstrip("/").rsplit("/", 1)[-1] or "Nextcloud"
    anhang.save()

    dienste.suchtext_aktualisieren(eintrag)
    messages.success(request, f"„{anhang.dateiname}“ wurde angehängt.")
    return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)


@login_required
def fassungen(request, schluessel: str, kennung: str):
    """Alle Fassungen eines Eintrags – Grundlage der Diff-Ansicht in Phase 2."""
    eintrag = _eintrag_holen(request, schluessel, kennung)
    return render(
        request,
        "kern/fassungen.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "typ": eintrag.typ,
            "versionen": eintrag.versionen.select_related("autor", "beschluss").all(),
            "baum": _gliederungsbaum(eintrag.dokument, request.user),
        },
    )


def gesundheit(request):
    """Einfacher Endpunkt für Überwachung und Healthcheck."""
    return HttpResponse("ok", content_type="text/plain")


@login_required
def nextcloud_waehlen(request, schluessel: str, kennung: str):
    """Dateiauswahl in der Nextcloud (SPEC.md §10, Stufe 1).

    Zeigt einen Ordner zum Durchklicken. Die gewählte Datei wird als Anhang
    mit Pfad und Link gespeichert – die Datei selbst bleibt in der Nextcloud.
    """
    from kern import nextcloud

    eintrag = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Anhänge darf nur anlegen, wer den Eintrag bearbeiten darf.")

    pfad = (request.GET.get("pfad") or "").strip("/")
    eintraege, fehler = [], ""

    if not nextcloud.ist_eingerichtet():
        fehler = (
            "Es ist kein Nextcloud-Zugang eingerichtet. Die Administration trägt "
            "ihn in der .env ein – siehe DEPLOYMENT.md."
        )
    else:
        try:
            eintraege = nextcloud.auflisten(pfad)
        except nextcloud.NextcloudFehler as problem:
            fehler = str(problem)

    return render(
        request,
        "kern/nextcloud.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": eintrag,
            "pfad": pfad,
            "eintraege": eintraege,
            "brotkrumen": nextcloud.brotkrumen(pfad),
            "fehler": fehler,
        },
    )


@login_required
@require_POST
def nextcloud_verlinken(request, schluessel: str, kennung: str):
    """Die gewählte Nextcloud-Datei als Anhang speichern."""
    from kern import nextcloud

    eintrag = _eintrag_holen(request, schluessel, kennung)
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Anhänge darf nur anlegen, wer den Eintrag bearbeiten darf.")

    pfad = (request.POST.get("pfad") or "").strip("/")
    if not pfad:
        messages.error(request, "Es wurde keine Datei ausgewählt.")
        return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)

    anhang, neu = Anhang.objects.get_or_create(
        eintrag=eintrag,
        nextcloud_pfad=pfad,
        defaults={
            "dokument": eintrag.dokument,
            "dateiname": pfad.rsplit("/", 1)[-1],
            "nextcloud_link": nextcloud.weblink(pfad),
            "mimetype": request.POST.get("mimetype", ""),
            "beschreibung": request.POST.get("beschreibung", ""),
            "erstellt_von": request.user,
        },
    )

    dienste.suchtext_aktualisieren(eintrag)
    if neu:
        messages.success(request, f"„{anhang.dateiname}“ ist jetzt verlinkt.")
    else:
        messages.info(request, f"„{anhang.dateiname}“ war schon verlinkt.")
    return redirect("kern:eintrag", schluessel=schluessel, kennung=kennung)
