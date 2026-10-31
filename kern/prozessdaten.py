"""Begrenztes Prozessschema, Graphprüfung und rechtegebundene Referenzen (AP05).

Keine eigene Fassungstabelle: Der Graph gehört zu Eintrag.daten und damit zu
Eintragsversion. Namen fremder Ziele werden weder kopiert noch indexiert.
"""

import json
import re
from collections import deque

from django.core.exceptions import ValidationError
from django.db import transaction

MAX_KNOTEN = 200
MAX_VERBINDUNGEN = 600
MAX_BYTES = 250_000
ARTEN = {"start", "handlung", "entscheidung", "ende"}
KENNUNG = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
FELD = "prozess_ablauf"


def _objekt(wert, erlaubt, ort):
    if not isinstance(wert, dict) or set(wert) - erlaubt:
        raise ValidationError(f"{ort}: Objekt mit den vorgesehenen Feldern erwartet.")


def _text(wert, grenze, ort, kennung=False):
    if not isinstance(wert, str) or len(wert) > grenze:
        raise ValidationError(f"{ort}: Text mit höchstens {grenze} Zeichen erwartet.")
    wert = wert.strip()
    if kennung and not KENNUNG.fullmatch(wert):
        raise ValidationError(f"{ort}: stabile Kennung aus Buchstaben, Ziffern, _ und - erwartet.")
    return wert


def normalisieren(wert):
    """Strukturell sichere Entwürfe; fachliche Vollständigkeit separat prüfen."""
    try:
        groesse = len(json.dumps(wert, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as fehler:
        raise ValidationError("Der Ablauf muss endliche, gültige JSON-Daten enthalten.") from fehler
    if groesse > MAX_BYTES:
        raise ValidationError("Der Ablauf ist zu groß (höchstens 250 KB).")
    _objekt(wert, {"schema_version", "knoten", "verbindungen"}, "Ablauf")
    if type(wert.get("schema_version")) is not int or wert["schema_version"] != 1:
        raise ValidationError("Diese Ablauf-Schema-Version wird nicht unterstützt.")
    for name, grenze in [("knoten", MAX_KNOTEN), ("verbindungen", MAX_VERBINDUNGEN)]:
        if not isinstance(wert.get(name), list) or len(wert[name]) > grenze:
            raise ValidationError(f"{name}: Liste mit höchstens {grenze} Elementen erwartet.")
    ergebnis = {"schema_version": 1, "knoten": [], "verbindungen": []}
    for roh in wert["knoten"]:
        _objekt(roh, {"id", "art", "titel", "text", "funktion", "bereich", "verweise"}, "Schritt")
        k = {
            "id": _text(roh.get("id"), 64, "Schritt-ID", kennung=True),
            "art": _text(roh.get("art"), 20, "Schrittart"),
            "titel": _text(roh.get("titel", ""), 200, "Schritttitel"),
            "text": _text(roh.get("text", ""), 4000, "Schritterklärung"),
        }
        if k["art"] not in ARTEN:
            raise ValidationError("Unbekannte Schrittart.")
        for name in ["funktion", "bereich"]:
            if roh.get(name) not in (None, ""):
                k[name] = _text(roh[name], 80, name)
                if not re.fullmatch(r"[a-z0-9_-]{1,80}", k[name]):
                    raise ValidationError(f"{name}: stabile Kennung erwartet.")
        if "bereich" in k and "funktion" not in k:
            raise ValidationError("Ein Funktionsbereich benötigt eine Funktion.")
        verweise = roh.get("verweise", [])
        if not isinstance(verweise, list) or len(verweise) > 20:
            raise ValidationError("Je Schritt sind höchstens 20 Verweise möglich.")
        k["verweise"] = []
        for verweis in verweise:
            if not isinstance(verweis, dict):
                raise ValidationError("Ein Verweis muss ein Objekt sein.")
            if verweis.get("typ") == "eintrag":
                _objekt(verweis, {"typ", "dokument", "kennung"}, "Wissensverweis")
                ziel = {
                    "typ": "eintrag",
                    "dokument": _text(verweis.get("dokument"), 80, "Dokumentkennung"),
                    "kennung": _text(verweis.get("kennung"), 40, "Eintragskennung"),
                }
                if not ziel["dokument"] or not ziel["kennung"]:
                    raise ValidationError("Der Wissensverweis benötigt Dokument und Kennung.")
            elif verweis.get("typ") == "anhang":
                _objekt(verweis, {"typ", "id"}, "Dateiverweis")
                pk = verweis.get("id")
                if type(pk) is not int or not 0 < pk <= 9223372036854775807:
                    raise ValidationError("Ein Dateiverweis benötigt eine gültige Anlagen-ID.")
                ziel = {"typ": "anhang", "id": pk}
            else:
                raise ValidationError(
                    "Nur Wissenseinträge und registrierte Anlagen sind verlinkbar."
                )
            if ziel not in k["verweise"]:
                k["verweise"].append(ziel)
        ergebnis["knoten"].append(k)
    if sum(len(k["verweise"]) for k in ergebnis["knoten"]) > 400:
        raise ValidationError("Ein Ablauf darf höchstens 400 Ressourcenverweise enthalten.")
    for roh in wert["verbindungen"]:
        _objekt(roh, {"id", "von", "nach", "beschriftung", "ruecksprung"}, "Verbindung")
        v = {"id": _text(roh.get("id"), 64, "Verbindungs-ID", kennung=True)}
        for name in ["von", "nach"]:
            v[name] = _text(roh.get(name, ""), 64, f"Verbindung {name}")
            if v[name] and not KENNUNG.fullmatch(v[name]):
                raise ValidationError("Ein Verbindungsziel benötigt eine gültige Schritt-ID.")
        v["beschriftung"] = _text(roh.get("beschriftung", ""), 200, "Zweigbeschriftung")
        v["ruecksprung"] = roh.get("ruecksprung", False)
        if type(v["ruecksprung"]) is not bool:
            raise ValidationError("Rücksprung muss wahr oder falsch sein.")
        ergebnis["verbindungen"].append(v)
    for name in ["knoten", "verbindungen"]:
        ids = [x["id"] for x in ergebnis[name]]
        if len(set(ids)) != len(ids):
            raise ValidationError(f"Doppelte Kennungen in {name} sind nicht erlaubt.")
    return ergebnis


def _erreichbar(start, nachbarn):
    gesehen = set(start)
    offen = deque(start)
    while offen:
        for ziel in nachbarn.get(offen.popleft(), ()):
            if ziel not in gesehen:
                gesehen.add(ziel)
                offen.append(ziel)
    return gesehen


def freigabehindernisse(graph):
    """Iterative Prüfung, auch für Zyklen; Meldungen nennen stabile Schritt-IDs."""
    knoten = {k["id"]: k for k in graph["knoten"]}
    kanten = graph["verbindungen"]
    fehler = []
    starts = [i for i, k in knoten.items() if k["art"] == "start"]
    enden = [i for i, k in knoten.items() if k["art"] == "ende"]
    if len(starts) != 1:
        fehler.append("Der Ablauf braucht genau einen Start.")
    if not enden:
        fehler.append("Der Ablauf braucht mindestens ein Ende.")
    aus = {i: [] for i in knoten}
    ein = {i: [] for i in knoten}
    vorwaerts = {i: [] for i in knoten}
    for v in kanten:
        if v["von"] not in knoten or v["nach"] not in knoten:
            fehler.append(f"Verbindung {v['id']}: Quell- oder Zielschritt fehlt.")
            continue
        aus[v["von"]].append(v)
        ein[v["nach"]].append(v["von"])
        if not v["ruecksprung"]:
            vorwaerts[v["von"]].append(v["nach"])
        elif not v["beschriftung"]:
            fehler.append(f"Verbindung {v['id']}: Beschrifte den Rücksprung verständlich.")
    for i, k in knoten.items():
        if not k["titel"]:
            fehler.append(f"Schritt {i}: Der Titel fehlt.")
        anzahl = len(aus[i])
        if k["art"] == "start" and (ein[i] or anzahl != 1):
            fehler.append(f"Schritt {i}: Ein Start braucht einen Ausgang und keinen Eingang.")
        if k["art"] == "handlung":
            if anzahl != 1:
                fehler.append(f"Schritt {i}: Eine Handlung braucht genau einen Folgeschritt.")
            if not k.get("funktion"):
                fehler.append(f"Schritt {i}: Wähle die zuständige Funktion.")
        if k["art"] == "entscheidung":
            texte = [v["beschriftung"].casefold() for v in aus[i]]
            if anzahl < 2 or "" in texte or len(set(texte)) != anzahl:
                fehler.append(f"Schritt {i}: Mindestens zwei eindeutig beschriftete Zweige fehlen.")
        if k["art"] == "ende" and anzahl:
            fehler.append(f"Schritt {i}: Ein Ende darf keinen Ausgang haben.")
    nachbarn = {i: [v["nach"] for v in werte] for i, werte in aus.items()}
    if len(starts) == 1:
        for i in sorted(set(knoten) - _erreichbar(starts, nachbarn)):
            fehler.append(f"Schritt {i}: Vom Start nicht erreichbar.")
    for i in sorted(set(knoten) - _erreichbar(enden, ein)):
        fehler.append(
            f"Schritt {i}: Kein Ende erreichbar (Kreis ohne Ausgang oder offener Schritt)."
        )
    # Ohne markierte Rücksprünge muss ein gerichteter azyklischer Graph bleiben.
    grade = {i: 0 for i in knoten}
    for ziele in vorwaerts.values():
        for ziel in ziele:
            grade[ziel] += 1
    offen = deque(i for i, grad in grade.items() if grad == 0)
    besucht = 0
    while offen:
        besucht += 1
        for ziel in vorwaerts[offen.popleft()]:
            grade[ziel] -= 1
            if grade[ziel] == 0:
                offen.append(ziel)
    if besucht != len(knoten):
        fehler.append("Ein Kreis enthält einen nicht ausdrücklich markierten Rücksprung.")
    for v in kanten:
        if v["ruecksprung"] and v["von"] in knoten and v["nach"] in knoten:
            if v["von"] not in _erreichbar([v["nach"]], vorwaerts):
                fehler.append(f"Verbindung {v['id']}: Der Rücksprung führt nicht zurück.")
    return fehler


def referenzen(graph, nutzer=None, freigabe=False):
    """Ziele gesammelt prüfen; keine fremden Titel oder Dateinamen in Fehlern."""
    from django.db.models import Prefetch, Q

    from kern import rechte
    from kern.models import Anhang, Eintrag, Funktionsbereich, Schulfunktion, Status, Zieltyp
    from kern.staende import gueltige_versionen, mit_lesefassungen, sichtbare_anhaenge

    funktionen = {
        f.schluessel: f
        for f in Schulfunktion.objects.filter(
            schluessel__in={k["funktion"] for k in graph["knoten"] if k.get("funktion")},
            archiviert=False,
        )
    }
    bereiche = {
        b.schluessel: b
        for b in Funktionsbereich.objects.filter(
            schluessel__in={k["bereich"] for k in graph["knoten"] if k.get("bereich")}
        )
    }
    dokumente = {}
    anhang_ids = set()
    for k in graph["knoten"]:
        for v in k["verweise"]:
            if v["typ"] == "eintrag":
                dokumente.setdefault(v["dokument"], set()).add(v["kennung"])
            else:
                anhang_ids.add(v["id"])
    auswahl = Q(pk__in=[])
    for dokument, kennungen in dokumente.items():
        auswahl |= Q(dokument__schluessel=dokument, kennung__in=kennungen)
    menge = Eintrag.objects.filter(auswahl).select_related("dokument")
    if nutzer is not None:
        menge = rechte.sichtbare_eintraege(nutzer, menge)
    eintraege = {(e.dokument.schluessel, e.kennung): e for e in mit_lesefassungen(menge)}
    menge = Anhang.objects.filter(pk__in=anhang_ids).select_related("eintrag")
    if nutzer is not None:
        menge = sichtbare_anhaenge(nutzer, menge)
    anhaenge = {
        a.pk: a
        for a in menge.prefetch_related(
            Prefetch(
                "eintrag__versionen", queryset=gueltige_versionen(), to_attr="_gueltige_fassungen"
            )
        )
    }
    ergebnis = set()
    for k in graph["knoten"]:
        if k.get("funktion"):
            f = funktionen.get(k["funktion"])
            if f is None:
                raise ValidationError(f"Schritt {k['id']}: Funktion nicht verfügbar.")
            ergebnis.add((Zieltyp.SCHULFUNKTION, str(f.pk)))
        if k.get("bereich"):
            b = bereiche.get(k["bereich"])
            if b is None:
                raise ValidationError(f"Schritt {k['id']}: Funktionsbereich nicht verfügbar.")
            ergebnis.add((Zieltyp.FUNKTIONSBEREICH, str(b.pk)))
        for verweis in k["verweise"]:
            if verweis["typ"] == "eintrag":
                e = eintraege.get((verweis["dokument"], verweis["kennung"]))
                if (
                    e is None
                    or e.status == Status.ARCHIVIERT
                    or (freigabe and e.beschlossene_version() is None)
                ):
                    raise ValidationError(f"Schritt {k['id']}: Wissensverweis nicht verfügbar.")
                ergebnis.add((Zieltyp.EINTRAG, str(e.pk)))
            else:
                a = anhaenge.get(verweis["id"])
                # Ungebundene Uploads und leere Metadatensätze sind keine Formulare.
                if (
                    a is None
                    or not (a.eintrag_id or a.dokument_id)
                    or not (a.datei or a.nextcloud_link or a.nextcloud_pfad)
                ):
                    raise ValidationError(f"Schritt {k['id']}: Dateiverweis nicht verfügbar.")
                if freigabe and a.eintrag_id and a.eintrag.beschlossene_version() is None:
                    raise ValidationError(
                        f"Schritt {k['id']}: Dateiverweis noch nicht freigegeben."
                    )
                ergebnis.add((Zieltyp.ANHANG, str(a.pk)))
    return ergebnis


@transaction.atomic
def freigabe_pruefen(daten, nutzer=None):
    from eintragstypen.registry import registry

    if not isinstance(daten, dict):
        raise ValidationError("Die Prozessdaten müssen ein Objekt sein.")
    typ = registry.holen("prozess")
    geprueft, feldfehler = typ.daten_pruefen(daten)
    if feldfehler:
        raise ValidationError(list(feldfehler.values()))
    fehlt = typ.fehlende_pflichtfelder(geprueft)
    if fehlt:
        raise ValidationError("Für die Freigabe fehlt: " + ", ".join(f.label for f in fehlt) + ".")
    graph = normalisieren(
        daten.get("ablauf", {"schema_version": 1, "knoten": [], "verbindungen": []})
    )
    from kern.models import Schulfunktion

    list(
        Schulfunktion.objects.select_for_update()
        .filter(schluessel__in={k["funktion"] for k in graph["knoten"] if k.get("funktion")})
        .order_by("pk")
    )
    fehler = freigabehindernisse(graph)
    if fehler:
        raise ValidationError(fehler)
    return referenzen(graph, nutzer=nutzer, freigabe=True)


def verlinkungen_setzen(eintrag, graph, nutzer=None):
    from kern.models import Verlinkung, Verlinkungsart

    ziele = referenzen(graph, nutzer=nutzer)
    eintrag.verlinkungen.filter(feld=FELD).delete()
    Verlinkung.objects.bulk_create(
        [
            Verlinkung(
                von_eintrag=eintrag,
                ziel_typ=typ,
                ziel_id=pk,
                art=Verlinkungsart.PROZESS_BEZUG,
                feld=FELD,
            )
            for typ, pk in sorted(ziele)
        ]
    )


def als_text(graph):
    """Lesbare, escaped auszugebende Eigeninhalte, ohne fremde Metadaten oder IDs."""
    try:
        graph = normalisieren(graph)
    except ValidationError:
        return "Ablauf noch nicht lesbar."
    namen = {k["id"]: k["titel"] or "Unbenannter Schritt" for k in graph["knoten"]}
    zeilen = []
    for k in graph["knoten"]:
        zeilen.append(f"{k['art'].capitalize()}: {namen[k['id']]}")
        if k["text"]:
            zeilen.append(k["text"])
        if k.get("funktion"):
            zeilen.append(
                "Zuständigkeit: "
                + k["funktion"]
                + (" · " + k["bereich"] if k.get("bereich") else "")
            )
        for v in graph["verbindungen"]:
            if v["von"] == k["id"]:
                ziel = namen.get(v["nach"], "Folgeschritt fehlt")
                art = "Rücksprung: " if v["ruecksprung"] else ""
                zeilen.append(f"{art}{v['beschriftung'] or 'Weiter'} → {ziel}")
    return "\n".join(zeilen)


def wird_verwendet(zieltyp, pk, nur_gueltig=False):
    from kern.models import Eintragsversion, Status, Verlinkung

    ziel = {"ziel_typ": zieltyp, "ziel_id": str(pk), "feld": FELD}
    versionen = Eintragsversion.objects.filter(verlinkungen__contains=[ziel])
    if nur_gueltig:
        return versionen.filter(status=Status.BESCHLOSSEN, beschluss__isnull=False).exists()
    return (
        Verlinkung.objects.filter(ziel_typ=zieltyp, ziel_id=str(pk), feld=FELD).exists()
        or versionen.exists()
    )


def schnappschuss_verweise(ziele, bisher):
    from kern.models import Verlinkungsart

    return [v for v in bisher if v.get("feld") != FELD] + [
        {
            "ziel_typ": typ,
            "ziel_id": pk,
            "art": Verlinkungsart.PROZESS_BEZUG,
            "feld": FELD,
            "beschriftung": "",
        }
        for typ, pk in sorted(ziele)
    ]
