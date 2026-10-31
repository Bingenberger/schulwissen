"""Autorenkomponente: sichere Optionen, schreibfreie Prüfung und Zielauswahl."""

import json
import re

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from kern import funktionen, prozessdaten, rechte
from kern.models import (
    Anhang,
    Eintrag,
    Funktionsbereich,
    Funktionsbesetzung,
    Schulfunktion,
)
from kern.staende import lesemenge, sichtbare_anhaenge

LEER = {"schema_version": 1, "knoten": [], "verbindungen": []}


def meldungen(texte, graph=None):
    """Alte Domänenmeldungen mit stabilen Sprungzielen für den Editor versehen."""
    kanten = {v["id"]: v for v in (graph or {}).get("verbindungen", [])}
    nummern = {k["id"]: i + 1 for i, k in enumerate((graph or {}).get("knoten", []))}
    ergebnis = []
    for text in texte:
        knoten = re.search(r"Schritt ([a-zA-Z0-9_-]+):", text)
        kante = re.search(r"Verbindung ([a-zA-Z0-9_-]+):", text)
        ziel = knoten.group(1) if knoten else ""
        if not ziel and kante:
            ziel = kanten.get(kante.group(1), {}).get("von", "")
        if not ziel and graph:
            if "genau einen Start" in text:
                starts = [k["id"] for k in graph["knoten"] if k["art"] == "start"]
                ziel = starts[1] if len(starts) > 1 else ""
            elif "nicht ausdrücklich markierten Rücksprung" in text:
                vor = {k["id"]: [] for k in graph["knoten"]}
                reihenfolge = {k["id"]: i for i, k in enumerate(graph["knoten"])}
                vorwaerts = [
                    v
                    for v in graph["verbindungen"]
                    if not v.get("ruecksprung") and v["von"] in vor and v["nach"] in vor
                ]
                for v in vorwaerts:
                    vor[v["von"]].append(v["nach"])
                kreise = [
                    v for v in vorwaerts if v["von"] in prozessdaten._erreichbar([v["nach"]], vor)
                ]
                bevorzugt = [v for v in kreise if reihenfolge[v["nach"]] <= reihenfolge[v["von"]]]
                if bevorzugt or kreise:
                    ziel = (bevorzugt or kreise)[0]["von"]
        if knoten and knoten.group(1) in nummern:
            text = (
                text[: knoten.start()]
                + f"Schritt {nummern[knoten.group(1)]}:"
                + text[knoten.end() :]
            )
        elif kante and ziel in nummern:
            verbindung = kanten.get(kante.group(1), {})
            schritt_kanten = [v for v in kanten.values() if v.get("von") == ziel]
            nr = schritt_kanten.index(verbindung) + 1 if verbindung in schritt_kanten else 1
            text = (
                text[: kante.start()]
                + f"Verbindung {nr} bei Schritt {nummern[ziel]}:"
                + text[kante.end() :]
            )
        elif kante:
            nr = list(kanten).index(kante.group(1)) + 1 if kante.group(1) in kanten else 1
            text = text[: kante.start()] + f"Verbindung {nr}:" + text[kante.end() :]
        elif ziel in nummern:
            text = f"Schritt {nummern[ziel]}: {text}"
        ergebnis.append(
            {"text": text, "schritt": ziel, "verbindung": kante.group(1) if kante else ""}
        )
    return ergebnis


def _quellzugang(request, schluessel):
    d = get_object_or_404(
        rechte.sichtbare_dokumente(request.user).select_related("dokumenttyp"),
        schluessel=schluessel,
    )
    kennung = (request.POST if request.method == "POST" else request.GET).get("kennung", "")
    e = get_object_or_404(Eintrag, dokument=d, kennung=kennung) if kennung else None
    if "prozess" not in (d.dokumenttyp.eintragstypen or []) or (
        e is not None and e.eintragstyp != "prozess"
    ):
        raise PermissionDenied("Dieses Dokument sieht hier keinen Prozess vor.")
    if not (rechte.darf_bearbeiten(request.user, e) if e else rechte.darf_anlegen(request.user, d)):
        raise PermissionDenied("Die Bearbeitungsberechtigung fehlt.")
    return d, e


def optionen():
    bereiche = list(Funktionsbereich.objects.order_by("name").values("schluessel", "name"))
    rollen = []
    menge = Schulfunktion.objects.filter(archiviert=False).prefetch_related(
        Prefetch(
            "besetzungen",
            queryset=Funktionsbesetzung.objects.select_related("person", "bereich"),
            to_attr="_editor_besetzungen",
        )
    )
    for f in menge:
        besetzungen = f._editor_besetzungen
        kontexte = {
            "": None,
            **{b.bereich.schluessel: b.bereich for b in besetzungen if b.bereich_id},
        }
        kontakte = {}
        for schluessel, bereich in kontexte.items():
            a = funktionen.aufloesen(f, bereich=bereich, besetzungen=besetzungen)
            namen = [
                b.person.anzeigename or b.person.kuerzel or "Kontoname ergänzen"
                for b in a.zustaendige
            ]
            kontakte[schluessel] = a.status_text + (": " + ", ".join(namen) if namen else "")
        rollen.append(
            {"schluessel": f.schluessel, "name": f.name, "aufgabe": f.aufgabe, "kontakte": kontakte}
        )
    return {"funktionen": rollen, "bereiche": bereiche}


def _ressourcen(nutzer, eintraege, anhaenge, *, lesefassung=False, limit=20):
    antwort = []
    if not lesefassung:
        eintraege = lesemenge(nutzer, eintraege)
    for e in eintraege.select_related("dokument").order_by("kennung")[:limit]:
        antwort.append(
            {
                "wert": {"typ": "eintrag", "dokument": e.dokument.schluessel, "kennung": e.kennung},
                "label": f"{e.dokument.titel} · {e.kennung} {e.lese_titel}",
            }
        )
    for a in sichtbare_anhaenge(nutzer, anhaenge).order_by("dateiname")[:limit]:
        if (a.dokument_id or a.eintrag_id) and (a.datei or a.nextcloud_link or a.nextcloud_pfad):
            antwort.append({"wert": {"typ": "anhang", "id": a.pk}, "label": a.dateiname or "Datei"})
    return antwort


def referenztexte(nutzer, graph):
    if nutzer is None:
        return []
    auswahl = Q(pk__in=[])
    ids = []
    for k in graph.get("knoten", []):
        for v in k.get("verweise", []):
            if v.get("typ") == "eintrag":
                auswahl |= Q(dokument__schluessel=v["dokument"], kennung=v["kennung"])
            elif v.get("typ") == "anhang":
                ids.append(v["id"])
    # Nur tatsächlich benötigte Ziele; die sichtbaren Metadaten werden nicht gespeichert.
    return _ressourcen(
        nutzer, Eintrag.objects.filter(auswahl), Anhang.objects.filter(pk__in=ids), limit=400
    )


class ProzessWidget(forms.HiddenInput):
    template_name = "kern/widgets/prozesseditor.html"
    nutzer = None
    dokument = None
    eintrag = None
    meldungen = ()

    def get_context(self, name, value, attrs):
        kontext = super().get_context(name, value, attrs)
        graph = None
        try:
            graph = prozessdaten.normalisieren(
                json.loads(value) if isinstance(value, str) else value
            )
        except (ValidationError, ValueError, TypeError):
            pass
        daten = optionen()
        daten.update(
            {
                "meldungen": list(self.meldungen),
                "ressourcen": referenztexte(self.nutzer, graph or LEER),
            }
        )
        if self.dokument is not None:
            daten["pruefen_url"] = reverse("kern:prozess_pruefen", args=[self.dokument.schluessel])
            daten["ziele_url"] = reverse("kern:prozess_ziele", args=[self.dokument.schluessel])
        daten["kennung"] = self.eintrag.kennung if self.eintrag else ""
        kontext["widget"]["optionen"] = daten
        kontext["widget"]["optionen_id"] = kontext["widget"]["attrs"]["id"] + "-optionen"
        return kontext


class ProzessFeld(forms.JSONField):
    widget = ProzessWidget

    def clean(self, value):
        wert = super().clean(value)
        if wert is None:
            # Ein fehlendes Eingabefeld darf bestehende Abläufe nicht unbemerkt leeren.
            raise ValidationError("Die Ablaufdaten fehlen. Bitte lade den Editor erneut.")
        return prozessdaten.normalisieren(wert)


@login_required
@require_POST
def pruefen(request, schluessel):
    from eintragstypen import dienste
    from eintragstypen.formulare import EintragFormular

    d, e = _quellzugang(request, schluessel)
    f = EintragFormular(
        request.POST, eintragstyp="prozess", eintrag=e, nutzer=request.user, dokument=d
    )
    if not f.is_valid():
        texte = [str(text) for liste in f.errors.values() for text in liste]
        return JsonResponse({"ok": False, "meldungen": meldungen(texte)})
    roh = f.als_rohsatz(e.kennung if e else "PR-VORSCHAU")
    roh.status = "abgestimmt"  # Nur prüfen, niemals schreiben oder einen Status verändern.
    b = dienste.pruefen(d, roh, nutzer=request.user)
    texte = [x.text for x in b.fehler]
    return JsonResponse({"ok": b.ok, "meldungen": meldungen(texte, b.daten.get("ablauf"))})


@login_required
@require_GET
def ziele(request, schluessel):
    _, e = _quellzugang(request, schluessel)
    begriff = (request.GET.get("q") or "").strip()[:150]
    if len(begriff) < 2:
        return JsonResponse({"treffer": []})
    # Fassungswahl und Zugangsfilter erfolgen vor Suche, Zählung und Ausgabe.
    menge = lesemenge(request.user, Eintrag.objects.all()).filter(
        Q(lese_titel__icontains=begriff) | Q(kennung__icontains=begriff)
    )
    if e is not None:
        menge = menge.exclude(pk=e.pk)
    anhaenge = Anhang.objects.filter(
        Q(dateiname__icontains=begriff) | Q(beschreibung__icontains=begriff)
    )
    return JsonResponse({"treffer": _ressourcen(request.user, menge, anhaenge, lesefassung=True)})
