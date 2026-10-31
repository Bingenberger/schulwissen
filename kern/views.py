"""Ansichten des Kerns: Startseite, Dokument, Eintrag lesen und bearbeiten."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from eintragstypen import dienste
from eintragstypen.formulare import AnhangFormular, EintragFormular, KommentarFormular
from eintragstypen.registry import registry
from fachdaten.faecher import bereiche_fuer
from fachdaten.models import Stufe
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
from kern.schreibschutz import Schreibkonflikt, token_fuer_eintrag, token_lesen
from kern.staende import (
    lesekontext,
    lesemenge,
    lesestand,
    mit_lesefassungen,
    sichtbare_anhaenge,
    sichtbare_beschlussmetadaten,
    sichtbare_verweise,
)


@login_required
def anhang_datei(request, pfad):
    """Auch bekannte Medien-URLs durch dieselben Leserechte schützen."""
    anhang = get_object_or_404(sichtbare_anhaenge(request.user, Anhang.objects.all()), datei=pfad)
    try:
        antwort = FileResponse(
            anhang.datei.open("rb"), as_attachment=True, filename=anhang.dateiname
        )
    except FileNotFoundError as fehler:
        raise Http404("Die Datei ist nicht verfügbar.") from fehler
    antwort["Cache-Control"] = "private, no-store"
    return antwort


@login_required
def startseite(request):
    """Großes Suchfeld, darunter wenige Einstiege (SPEC.md §9).

    Die Suche selbst kommt in Phase 2; das Feld steht schon hier, damit das
    Kollegium von Anfang an denselben Einstieg sieht.
    """
    sichtbar = lesemenge(request.user, Eintrag.objects.all())

    zuletzt_beschlossen = (
        sichtbar.filter(lese_status=Status.BESCHLOSSEN)
        .select_related("dokument")
        .order_by("-geaendert_am")[:5]
    )
    eigene_entwuerfe = (
        sichtbar.filter(
            status__in=(Status.IDEE, Status.ENTWURF),
        )
        .filter(Q(erstellt_von=request.user) | Q(verantwortlich_person=request.user))
        .select_related("dokument")
        .order_by("-geaendert_am", "pk")
        if rechte.ist_lehrkraft(request.user)
        else Eintrag.objects.none()
    )

    return render(
        request,
        "kern/startseite.html",
        {
            "dokumente": rechte.sichtbare_dokumente(request.user)
            .select_related("dokumenttyp")
            .annotate(anzahl=Count("eintraege", filter=Q(eintraege__in=sichtbar)))
            .order_by("titel", "pk")[:6],
            "dokumente_gesamt": rechte.sichtbare_dokumente(request.user).count(),
            "eigene_entwuerfe_gesamt": eigene_entwuerfe.count(),
            "zuletzt_beschlossen": [lesestand(request.user, e) for e in zuletzt_beschlossen],
            "eigene_entwuerfe": eigene_entwuerfe[:5],
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
    alle_eintraege = list(mit_lesefassungen(dokument.eintraege.order_by("position", "kennung")))
    sichtbare = set(
        rechte.sichtbare_eintraege(nutzer, dokument.eintraege.all()).values_list("pk", flat=True)
    )

    staende = {e.pk: lesestand(nutzer, e) for e in alle_eintraege}

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
                    "eintrag": staende[eintrag.pk] or eintrag,
                    "tiefe": tiefe,
                    "titel": staende[eintrag.pk].titel
                    if staende[eintrag.pk]
                    else "Noch nicht freigegeben",
                    "lesbar": eintrag.pk in sichtbare,
                    "daten": staende[eintrag.pk].daten if staende[eintrag.pk] else {},
                    "status": staende[eintrag.pk].status if staende[eintrag.pk] else Status.ENTWURF,
                }
            )
            zeilen.extend(bauen(eintrag.pk, tiefe + 1))
        return zeilen

    return bauen(None)


@login_required
def dokument_ansehen(request, schluessel: str):
    dokument = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_related("dokumenttyp"),
        schluessel=schluessel,
    )
    baum = _gliederungsbaum(dokument, request.user)
    karten = {}
    for zeile in baum:
        if zeile["eintrag"].eintragstyp in ("vorhaben", "ritual") and zeile["lesbar"]:
            daten = zeile["daten"]
            gruppe = (
                "Rituale"
                if zeile["eintrag"].eintragstyp == "ritual"
                else (
                    f"Jahrgang {daten['jahrgang']}"
                    if daten.get("jahrgang")
                    else "Jahrgang noch offen"
                )
            )
            karten.setdefault(gruppe, []).append(
                {**zeile, "status_text": Status(zeile["status"]).label}
            )
    return render(
        request,
        "kern/dokument.html",
        {
            "dokument": dokument,
            "darf_protokoll_beschliessen": rechte.darf_beschliessen(request.user, dokument),
            "baum": baum,
            "protokoll_hat_entwuerfe": dokument.eintraege.exclude(status=Status.ARCHIVIERT)
            .exclude(status=Status.BESCHLOSSEN)
            .exists(),
            "kartengruppen": sorted(
                karten.items(), key=lambda gruppe: (gruppe[0] != "Rituale", gruppe[0])
            ),
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


def _ruckverweise(nutzer, eintrag: Eintrag):
    """Rückverweise aus der sichtbaren Fassung, einschließlich entfernter Altverweise."""
    from types import SimpleNamespace

    ziel = {"ziel_typ": Zieltyp.EINTRAG, "ziel_id": str(eintrag.pk)}
    kandidaten = (
        Eintrag.objects.filter(
            Q(verlinkungen__ziel_typ=Zieltyp.EINTRAG, verlinkungen__ziel_id=str(eintrag.pk))
            | Q(versionen__verlinkungen__contains=[ziel])
        )
        .distinct()
        .select_related("dokument")
        .order_by("kennung")
    )
    ergebnis = []
    for quelle in rechte.sichtbare_eintraege(nutzer, kandidaten):
        stand = lesestand(nutzer, quelle)
        for verweis in stand.verweise:
            if verweis.get("ziel_typ") == Zieltyp.EINTRAG and verweis.get("ziel_id") == str(
                eintrag.pk
            ):
                art = verweis.get("art", "")
                ergebnis.append(
                    SimpleNamespace(
                        von_eintrag=stand,
                        get_art_display=dict(Verlinkung._meta.get_field("art").choices).get(
                            art, art
                        ),
                    )
                )
    return ergebnis


def bloecke_zum_lesen(typ, daten: dict, verweise_je_feld: dict | None = None):
    """Blöcke mit gefüllten Feldern – für Leseansicht und alte Fassungen.

    ``verweise_je_feld`` bildet einen Feldschlüssel auf die Liste seiner
    Verweise ab. Für einen Eintrag kommen die aus der Datenbank, für eine
    gespeicherte Fassung aus ihrem Schnappschuss.
    """
    from eintragstypen.registry import Feldtyp

    verweise_je_feld = verweise_je_feld or {}
    daten = daten or {}
    from fachdaten.models import Kompetenzerwartung

    kompetenzen = Kompetenzerwartung.objects.in_bulk(
        {v.ziel_id for ziele in verweise_je_feld.values() for v in ziele}
    )

    for block, felder in typ.bloecke_mit_feldern(daten):
        zeilen = []
        for feld in felder:
            if feld.ist_verlinkung:
                ziele = verweise_je_feld.get(feld.schluessel) or []
                if ziele:
                    gruppen = {}
                    if feld.zieltyp == "kompetenz":
                        for ziel in ziele:
                            erwartung = kompetenzen.get(ziel.ziel_id)
                            name = erwartung.bereich_name if erwartung else "Weitere Kompetenzen"
                            gruppen.setdefault(name, []).append(ziel)
                    zeilen.append(
                        {"feld": feld, "verweise": ziele, "verweisgruppen": list(gruppen.items())}
                    )
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


def _felder_zum_lesen(eintrag: Eintrag, nutzer):
    """Blöcke des aktuellen Standes eines Eintrags."""
    verweise: dict[str, list] = {}
    from types import SimpleNamespace

    for verlinkung in sichtbare_verweise(
        nutzer, [v.als_schnappschuss() for v in eintrag.verlinkungen.order_by("ziel_id")]
    ):
        verweise.setdefault(verlinkung.get("feld", ""), []).append(SimpleNamespace(**verlinkung))
    return bloecke_zum_lesen(eintrag.typ, eintrag.daten, verweise)


def verweise_aus_schnappschuss(version, nutzer=None) -> dict[str, list]:
    """Die Verweise einer gespeicherten Fassung, nach Feld geordnet.

    Sie kommen aus dem Schnappschuss, nicht aus der Datenbank – sonst zeigte
    eine alte Fassung die heutigen Kompetenzen.
    """
    from types import SimpleNamespace

    verweise: dict[str, list] = {}
    gespeichert = version.verlinkungen or []
    for verweis in sichtbare_verweise(nutzer, gespeichert) if nutzer is not None else gespeichert:
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
    stand = lesestand(request.user, eintrag)

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
                "eintrag": stand,
                "baum": _gliederungsbaum(eintrag.dokument, request.user),
                "ist_administration": rechte.ist_administration(request.user),
            },
        )

    if stand.version is None:
        bloecke = list(_felder_zum_lesen(eintrag, request.user))
    else:
        bloecke = list(
            bloecke_zum_lesen(
                eintrag.typ, stand.daten, verweise_aus_schnappschuss(stand.version, request.user)
            )
        )

    from kern.wissenspflege import kontext as pflegekontext

    pflege = pflegekontext(request.user, stand)
    prozess = None
    if eintrag.eintragstyp == "prozess":
        from kern import prozesslesen

        prozess = prozesslesen.aufbereiten(eintrag, stand.daten, request.user, stand.version)
        bloecke = prozesslesen.ohne_ablauf(bloecke)

    # Steht der Arbeitsstand neben einer beschlossenen Fassung, soll das
    # sichtbar sein – sonst hält man den Entwurf für geltendes Recht.
    entwurf_weicht_ab = bool(
        beschlossen is not None
        and eintrag.status != Status.BESCHLOSSEN
        and (eintrag.titel != beschlossen.titel or eintrag.daten != beschlossen.daten)
    )

    return render(
        request,
        "kern/eintrag.html",
        {
            "dokument": eintrag.dokument,
            "eintrag": stand,
            "lesekontext": lesekontext(request.user, eintrag),
            "anzahl_fassungen": rechte.sichtbare_versionen(
                request.user, eintrag.versionen.all()
            ).count(),
            "anhaenge": sichtbare_anhaenge(request.user, eintrag.anhaenge.all()),
            "typ": eintrag.typ,
            "bloecke": bloecke,
            "pflege": pflege,
            "prozess": prozess,
            "darf_prozess_freigeben": rechte.darf_beschliessen(request.user, eintrag.dokument),
            "angezeigter_titel": stand.titel,
            "angezeigter_status": stand.status,
            "angezeigter_status_text": stand.get_status_display(),
            "zeigt_entwurf": zeigt_entwurf,
            "entwurf_weicht_ab": entwurf_weicht_ab,
            "baum": _gliederungsbaum(eintrag.dokument, request.user),
            "beschlossene_version": beschlossen,
            "beschluss": sichtbare_beschlussmetadaten(
                request.user, stand.version or beschlossen
            ).beschluss
            if stand.version or beschlossen
            else None,
            "rueckverweise": _ruckverweise(request.user, eintrag),
            "kommentare": eintrag.kommentare.select_related("autor") if zeigt_entwurf else [],
            "kommentar_formular": KommentarFormular(),
            "anhang_formular": AnhangFormular(),
            "offene_pflichtfelder": offene_pflichtfelder,
            "darf_bearbeiten": rechte.darf_bearbeiten(request.user, eintrag),
            "darf_kommentieren": rechte.darf_kommentieren(request.user, eintrag),
        },
    )


@login_required
def eintrag_bearbeiten(request, schluessel: str, kennung: str):
    try:
        eintrag = _eintrag_holen(request, schluessel, kennung)
    except Http404:
        if request.method != "POST":
            raise
        dokument = get_object_or_404(
            rechte.sichtbare_dokumente(request.user), schluessel=schluessel
        )
        try:
            alt = token_lesen(
                request.POST.get("ausgangsstand"), request.user, dokument, kennung=kennung
            )
        except Schreibkonflikt as fehler:
            raise Http404("Dieser Eintrag ist nicht vorhanden.") from fehler
        if not rechte.darf_anlegen(request.user, dokument) or not registry.bekannt(
            alt["eintragstyp"]
        ):
            raise PermissionDenied(
                "Die Bearbeitungsberechtigung ist nicht mehr vorhanden."
            ) from None
        eintrag = Eintrag(
            pk=alt["eintrag"],
            dokument=dokument,
            kennung=kennung,
            eintragstyp=alt["eintragstyp"],
            erstellt_von=request.user,
        )
        eintrag.entfernt = True
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
        formular = EintragFormular(
            request.POST, eintragstyp=eintrag.eintragstyp, eintrag=eintrag, nutzer=request.user
        )
        gueltig = formular.is_valid()
        if getattr(eintrag, "entfernt", False):
            _entfernt_anzeigen(formular)
        elif gueltig:
            antwort = _speichern(request, eintrag.dokument, formular, eintrag.kennung, eintrag)
            if antwort is not None:
                return antwort
    else:
        formular = EintragFormular(
            eintragstyp=eintrag.eintragstyp, eintrag=eintrag, nutzer=request.user
        )
        formular.initial["ausgangsstand"] = token_fuer_eintrag(request.user, eintrag)

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
            "bereiche": bereiche_fuer(eintrag.dokument.fach or "deutsch"),
            "stufen": Stufe.choices,
        },
        status=409 if getattr(formular, "schreibkonflikt", False) else 200,
    )


@login_required
def eintrag_neu(request, schluessel: str, eintragstyp: str):
    """Neuen Eintrag anlegen. Die Kennung vergibt die App."""
    dokument = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_related("dokumenttyp"),
        schluessel=schluessel,
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
        formular = EintragFormular(
            request.POST, eintragstyp=eintragstyp, dokument=dokument, nutzer=request.user
        )
        if formular.is_valid():
            antwort = _speichern(request, dokument, formular, None, None)
            if antwort is not None:
                return antwort
    else:
        formular = EintragFormular(eintragstyp=eintragstyp, dokument=dokument, nutzer=request.user)

    return render(
        request,
        "kern/eintrag_bearbeiten.html",
        {
            "dokument": dokument,
            "eintrag": None,
            "typ": typ,
            "formular": formular,
            "baum": _gliederungsbaum(dokument, request.user),
            "bereiche": bereiche_fuer(dokument.fach or "deutsch"),
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


@transaction.atomic
def _speichern(request, dokument, formular, kennung: str, eintrag):
    """Prüft und speichert; gibt eine Weiterleitung zurück oder ``None``."""
    from deutsch import gliederung

    Dokument.objects.select_for_update().get(pk=dokument.pk)
    if eintrag is None:
        kennung = _kennung_vergeben(dokument, formular.typ, formular)
    roh = formular.als_rohsatz(kennung)

    if roh.status != (eintrag.status if eintrag is not None else Status.ENTWURF):
        pruefeintrag = eintrag or Eintrag(dokument=dokument, erstellt_von=request.user)
        if not rechte.darf_status_setzen(request.user, pruefeintrag, roh.status):
            formular.add_error(
                "status",
                "Diesen Status darf nur die Redaktion oder die Administration setzen.",
            )
            return None

    befundsatz = dienste.pruefen(dokument, roh, nutzer=request.user)
    if not befundsatz.ok:
        if roh.eintragstyp == "prozess":
            from kern.prozesseditor import meldungen

            formular.fields["f_ablauf"].widget.meldungen = meldungen(
                [b.text for b in befundsatz.fehler], befundsatz.daten.get("ablauf")
            )
        if roh.eintragstyp == "prozess":
            for meldung in formular.fields["f_ablauf"].widget.meldungen:
                formular.add_error(None, meldung["text"])
        else:
            for befund in befundsatz.fehler:
                formular.add_error(None, befund.text)
        return None

    # Der Wechsel auf „abgestimmt in Gruppe“ setzt vollständige Pflichtfelder
    # voraus (SPEC.md §7.4). Die Maske sagt, was fehlt.
    if roh.status == Status.ABGESTIMMT and befundsatz.fehlende_pflichtfelder:
        for feld in befundsatz.fehlende_pflichtfelder:
            name = ("v_" if feld.ist_verlinkung else "f_") + feld.schluessel
            if name in formular.fields:
                formular.add_error(name, f"Bitte fülle „{feld.label}“ aus.")
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

    try:
        erwartet = None
        if eintrag is not None:
            token = formular.cleaned_data.get("ausgangsstand")
            if request.POST.get("aktion") == "konflikt_loesen":
                if request.POST.get("konflikt_geprueft") != "on":
                    raise Schreibkonflikt(
                        "Bitte vergleiche die Änderungen und bestätige deine geprüfte Eingabe."
                    )
                token = request.POST.get("aktueller_stand")
            erwartet = token_lesen(token, request.user, dokument, eintrag)["stand"]
        gespeichert = dienste.speichern(
            dokument, befundsatz, nutzer=request.user, eltern=eltern, erwarteter_stand=erwartet
        )
    except Schreibkonflikt as fehler:
        _schreibkonflikt_anzeigen(request, eintrag, formular, befundsatz, fehler)
        return None
    except ValidationError as fehler:
        formular.add_error(None, " ".join(fehler.messages))
        return None

    if gespeichert.verantwortlich_gruppe_id is None and eintrag is None:
        # Erstanlage: die erste Arbeitsgruppe des Nutzers übernimmt die
        # Verantwortung, damit die Gruppe den Entwurf weiterbearbeiten kann.
        from kern.models import Gruppenart

        gruppe = request.user.groups.filter(profil__art=Gruppenart.ARBEITSGRUPPE).first()
        if gruppe is not None:
            gespeichert.verantwortlich_gruppe = gruppe
            gespeichert.save(update_fields=["verantwortlich_gruppe"])

    if befundsatz.fehlende_pflichtfelder:
        for feld in befundsatz.fehlende_pflichtfelder:
            name = ("v_" if feld.ist_verlinkung else "f_") + feld.schluessel
            if name in formular.fields:
                formular.add_error(name, f"Bitte fülle „{feld.label}“ aus.")
        namen = ", ".join(f.label for f in befundsatz.fehlende_pflichtfelder)
        messages.warning(
            request,
            f"Als Entwurf gespeichert. Für „abgestimmt in Gruppe“ fehlt noch: {namen}.",
        )
    else:
        messages.success(request, f"„{gespeichert.titel}“ wurde gespeichert.")

    return redirect("kern:eintrag", schluessel=dokument.schluessel, kennung=gespeichert.kennung)


def _schreibkonflikt_anzeigen(request, eintrag, formular, befundsatz, fehler):
    from types import SimpleNamespace

    from kern import vergleich

    formular.add_error(None, str(fehler))
    formular.schreibkonflikt = True
    if eintrag is None:
        return
    try:
        eintrag.refresh_from_db()
    except Eintrag.DoesNotExist:
        _entfernt_anzeigen(formular)
        return
    if not rechte.darf_bearbeiten(request.user, eintrag):
        raise PermissionDenied("Die Bearbeitungsberechtigung ist nicht mehr vorhanden.")
    formular.konfliktstand = token_fuer_eintrag(request.user, eintrag)
    verweise = []
    for feld in eintrag.typ.verlinkungsfelder:
        for ziel in befundsatz.verweise.get(feld.schluessel, []):
            if feld.zieltyp == Zieltyp.EINTRAG:
                anderes = eintrag.dokument.eintraege.filter(kennung=ziel).first()
                if anderes is None:
                    continue
                ziel = str(anderes.pk)
            verweise.append(
                {
                    "ziel_typ": feld.zieltyp,
                    "ziel_id": ziel,
                    "art": feld.verlinkungsart,
                    "feld": feld.schluessel,
                }
            )
    aktuell = SimpleNamespace(
        eintrag=eintrag,
        titel=eintrag.titel,
        daten=eintrag.daten,
        verlinkungen=[v.als_schnappschuss() for v in eintrag.verlinkungen.all()],
    )
    eingabe = SimpleNamespace(
        eintrag=eintrag, titel=befundsatz.roh.titel, daten=befundsatz.daten, verlinkungen=verweise
    )
    formular.konfliktvergleich = vergleich.vergleichen(aktuell, eingabe, request.user)


def _entfernt_anzeigen(formular):
    formular.schreibkonflikt = True
    formular.eintrag_entfernt = True
    formular.add_error(
        None,
        "Dieser Eintrag wurde inzwischen entfernt. Deine Eingabe bleibt hier erhalten; "
        "es wurde nichts gespeichert.",
    )


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
            fehlerhinweis=bool(request.POST.get("fehlerhinweis")),
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
            "versionen": [
                sichtbare_beschlussmetadaten(request.user, v)
                for v in rechte.sichtbare_versionen(
                    request.user, eintrag.versionen.select_related("autor", "beschluss")
                )
            ],
            "angezeigter_titel": (
                eintrag.titel
                if rechte.zeigt_entwurf(request.user)
                else eintrag.beschlossene_version().titel
                if eintrag.beschlossene_version()
                else "Freigegebene Fassungen"
            ),
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
