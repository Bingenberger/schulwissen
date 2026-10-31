"""Lesefassung eines Prozesses mit aktuellen, rechtegebundenen Kontakten/Ressourcen."""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from kern import funktionen, prozessdaten, rechte
from kern.models import Anhang, Eintrag, Funktionsbereich, Funktionsbesetzung, Schulfunktion, Status
from kern.staende import gueltige_versionen, lesestand, mit_lesefassungen, sichtbare_anhaenge

ARTEN = {"start": "Start", "handlung": "Handlung", "entscheidung": "Entscheidung", "ende": "Ende"}


def _sichere_url(url, intern=False):
    try:
        teile = urlsplit(url)
        if (
            teile.scheme in ("http", "https")
            and teile.hostname
            and not teile.username
            and not teile.password
        ):
            return url
        if (
            intern
            and url.startswith("/")
            and not url.startswith("//")
            and not teile.scheme
            and not teile.netloc
        ):
            return url
    except (ValueError, TypeError):
        pass
    return ""


def aufbereiten(eintrag, daten, nutzer, version=None):
    """Nur den ausgewählten Schnappschuss verarbeiten, keine fremden Rohreferenzen ausgeben."""
    try:
        graph = prozessdaten.normalisieren(
            daten.get(
                "ablauf",
                {
                    "schema_version": 1,
                    "knoten": [],
                    "verbindungen": [],
                },
            )
        )
    except (ValidationError, AttributeError):
        return {"fehler": "Dieser Ablauf ist derzeit nicht lesbar. Bitte frage die Redaktion."}
    quelle = version
    if quelle is None and eintrag.status == Status.BESCHLOSSEN:
        quelle = eintrag.beschlossene_version()
    gueltig = bool(
        quelle
        and quelle.status in (Status.BESCHLOSSEN, Status.ARCHIVIERT)
        and (quelle.freigegeben_am or quelle.beschluss_id)
    )
    historisch = bool(version and version.status == Status.ARCHIVIERT and gueltig)
    fassung = (
        f"Historische Prozessfassung {version.versionsnummer}"
        if historisch
        else f"Prozessfassung {version.versionsnummer}"
        if version
        else "Beschlossener Ablauf"
        if gueltig
        else "Arbeitsstand – noch nicht beschlossen"
    )
    bereiche = {
        b.schluessel: b
        for b in Funktionsbereich.objects.filter(
            schluessel__in={k["bereich"] for k in graph["knoten"] if k.get("bereich")}
        )
    }
    rollen = {
        f.schluessel: f
        for f in Schulfunktion.objects.filter(
            schluessel__in={k["funktion"] for k in graph["knoten"] if k.get("funktion")}
        ).prefetch_related(
            Prefetch(
                "besetzungen",
                queryset=Funktionsbesetzung.objects.select_related("person", "bereich"),
                to_attr="_lesebesetzungen",
            )
        )
    }
    kontakte = {}
    q = Q(pk__in=[])
    ids = set()
    for k in graph["knoten"]:
        for v in k["verweise"]:
            if v["typ"] == "eintrag":
                q |= Q(dokument__schluessel=v["dokument"], kennung=v["kennung"])
            else:
                ids.add(v["id"])
    ziele = {
        (e.dokument.schluessel, e.kennung): e
        for e in mit_lesefassungen(
            rechte.sichtbare_eintraege(nutzer, Eintrag.objects.filter(q)).select_related("dokument")
        )
    }
    anhaenge = {
        a.pk: a
        for a in sichtbare_anhaenge(nutzer, Anhang.objects.filter(pk__in=ids))
        .select_related("eintrag")
        .prefetch_related(
            Prefetch(
                "eintrag__versionen", queryset=gueltige_versionen(), to_attr="_gueltige_fassungen"
            )
        )
    }
    nummern = {k["id"]: i + 1 for i, k in enumerate(graph["knoten"])}
    knoten = []
    for k in graph["knoten"]:
        neu = {s: k[s] for s in ("id", "art", "titel", "text")}
        neu.update(
            {
                "nummer": nummern[k["id"]],
                "art_text": ARTEN[k["art"]],
                "kontakt": None,
                "materialien": [],
            }
        )
        if k.get("funktion"):
            key = (k["funktion"], k.get("bereich", ""))
            if key not in kontakte:
                f = rollen.get(key[0])
                b = bereiche.get(key[1]) if key[1] else None
                kontakt = {
                    "name": "Funktion derzeit nicht verfügbar",
                    "personen": [],
                    "status": "Besetzung bitte prüfen",
                    "bereich": "",
                    "hinweis": "",
                    "email": "",
                    "telefon": "",
                    "anlaufstelle": "",
                }
                if f is not None:
                    kontakt["name"] = f.name
                    if key[1] and b is None:
                        kontakt["status"] = "Zuständigkeitsbereich nicht verfügbar"
                    else:
                        a = funktionen.aufloesen(f, bereich=b, besetzungen=f._lesebesetzungen)
                        kontakt.update(
                            {
                                "bereich": b.name if b else "Allgemein",
                                "status": a.status_text,
                                "personen": [
                                    x.person.anzeigename or x.person.kuerzel or "Kontoname ergänzen"
                                    for x in a.zustaendige
                                ],
                                "hinweis": a.hinweis,
                            }
                        )
                        if not f.archiviert:
                            from django.core.validators import validate_email

                            try:
                                if f.dienst_email:
                                    validate_email(f.dienst_email)
                                    kontakt["email"] = f.dienst_email
                            except ValidationError:
                                pass
                            kontakt.update(
                                {"telefon": f.dienst_telefon, "anlaufstelle": f.kontakt_hinweis}
                            )
                kontakte[key] = kontakt
            neu["kontakt"] = kontakte[key]
        for v in k["verweise"]:
            material = {
                "label": "Wissensverweis derzeit nicht verfügbar"
                if v["typ"] == "eintrag"
                else "Datei derzeit nicht verfügbar",
                "url": "",
                "art": "",
            }
            if v["typ"] == "eintrag":
                e = ziele.get((v["dokument"], v["kennung"]))
                if e and e.status != Status.ARCHIVIERT:
                    zielversion = e.beschlossene_version() if gueltig else None
                    stand = lesestand(nutzer, e) if not gueltig else None
                    if gueltig and zielversion:
                        material = {
                            "label": f"{e.kennung} · {zielversion.titel}",
                            "art": "Beschlossener Wissenseintrag",
                            "url": reverse(
                                "kern:version",
                                args=[e.dokument.schluessel, e.kennung, zielversion.versionsnummer],
                            ),
                        }
                    elif stand is not None:
                        material = {
                            "label": f"{e.kennung} · {stand.titel}",
                            "art": "Wissenseintrag",
                            "url": reverse("kern:eintrag", args=[e.dokument.schluessel, e.kennung]),
                        }
            else:
                a = anhaenge.get(v["id"])
                unveraendert = True
                if a and gueltig:
                    referenzzeit = quelle.freigegeben_am
                    if a.eintrag_id:
                        zielversion = a.eintrag.beschlossene_version()
                        referenzzeit = zielversion.freigegeben_am if zielversion else None
                    unveraendert = bool(referenzzeit and a.geaendert_am <= referenzzeit)
                if a and unveraendert:
                    url = ""
                    if a.datei:
                        url = reverse("kern:anhang_datei", args=[a.datei.name])
                    elif a.nextcloud_link:
                        url = _sichere_url(a.nextcloud_link)
                    elif a.nextcloud_pfad and settings.NEXTCLOUD_URL:
                        from kern.nextcloud import weblink

                        url = _sichere_url(weblink(a.nextcloud_pfad))
                    if url:
                        material = {
                            "label": a.dateiname or "Datei",
                            "url": url,
                            "art": "Verknüpfte Datei",
                            "pruefhinweis": (
                                "Veränderlicher Materiallink – die externe Dateifassung ist "
                                "nicht an diese Prozessfreigabe gebunden."
                                if not a.datei
                                else "Registrierte Änderungen seit Freigabe werden zurückgehalten."
                                if gueltig
                                else "Arbeitsstand: Materialfassung vor Freigabe prüfen."
                            ),
                        }
                elif a and not unveraendert:
                    material["label"] = (
                        "Datei seit der Freigabe geändert oder nicht mehr freigegeben"
                    )
            neu["materialien"].append(material)
        neu["folgen"] = []
        for v in graph["verbindungen"]:
            if v["von"] == k["id"]:
                ziel = next((z for z in graph["knoten"] if z["id"] == v["nach"]), None)
                neu["folgen"].append(
                    {
                        **v,
                        "ziel_nummer": nummern.get(v["nach"]),
                        "ziel_titel": ziel["titel"] if ziel else "Folgeschritt fehlt",
                    }
                )
        knoten.append(neu)
    params = f"?fassung={version.versionsnummer}" if version else ""
    return {
        "graph": {"schema_version": 1, "knoten": knoten, "verbindungen": graph["verbindungen"]},
        "knoten": knoten,
        "unvollstaendig": bool(prozessdaten.freigabehindernisse(graph)),
        "fassung_text": fassung,
        "historisch": historisch,
        "kontaktstand": timezone.now(),
        "pdf_url": reverse("kern:prozess_pdf", args=[eintrag.dokument.schluessel, eintrag.kennung])
        + params,
    }


@login_required
def pdf(request, schluessel, kennung):
    from kern import exporte, views

    e = views._eintrag_holen(request, schluessel, kennung)
    if e.eintragstyp != "prozess":
        raise Http404("Dies ist kein Prozess.")
    v = None
    if "fassung" in request.GET:
        nummer = request.GET["fassung"]
        v = get_object_or_404(
            rechte.sichtbare_versionen(request.user, e.versionen.all()),
            versionsnummer=int(nummer) if nummer.isdigit() and len(nummer) < 10 else -1,
        )
    stand = lesestand(request.user, e)
    v = v or stand.version
    daten = v.daten if v else stand.daten
    prozess = aufbereiten(e, daten, request.user, v)
    titel = v.titel if v else stand.titel
    quelle = render_to_string(
        "kern/prozess_pdf.html", {"prozess": prozess, "titel": titel, "kennung": e.kennung}
    )
    inhalt = exporte.html_pdf(quelle)
    antwort = HttpResponse(inhalt, content_type="application/pdf")
    antwort["Content-Disposition"] = 'attachment; filename="prozess.pdf"'
    antwort["Cache-Control"] = "private, no-store"
    return antwort


def ohne_ablauf(bloecke):
    from eintragstypen.registry import Feldtyp

    ergebnis = []
    for block in bloecke:
        felder = [f for f in block["felder"] if f["feld"].typ != Feldtyp.PROZESSGRAPH]
        if felder:
            ergebnis.append({**block, "felder": felder})
    return ergebnis
