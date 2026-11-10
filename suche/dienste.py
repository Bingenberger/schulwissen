"""Die Suche – das Herzstück der App (SPEC.md §9).

Gesucht wird in sechs Gruppen: Schulhandbuch/Formulare, veröffentlichte Abläufe,
Arbeitspläne und Konzepte, Konferenzbeschlüsse, Kompetenzerwartungen und Dateien.
Je Treffer gibt es Titel, Kontext
(„Arbeitsplan Deutsch › 2.1 › V-3-01“), einen Trefferausschnitt mit
Hervorhebung und ein Status-Schild.

Zwei Wege führen zum Treffer:

* **Volltext** über PostgreSQL mit deutschen Stammformen – „Märchen“ findet
  auch „Märchens“. Dafür sorgt ``SearchQuery`` mit der Konfiguration
  ``german``.
* **Ähnlichkeit** über ``pg_trgm``, wenn der Volltext nichts findet. Damit
  verzeiht die Suche Tippfehler, und das ist bei einem Kollegium, das zwischen
  Tür und Angel sucht, wichtiger als Genauigkeit.

Beschlossene Inhalte stehen vorn; Entwürfe sieht nur, wer darf, und sie sind
gekennzeichnet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import nh3
from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
    TrigramWordSimilarity,
)
from django.db import connection
from django.db.models import Case, Count, F, FloatField, Q, Value, When
from django.db.models.functions import Greatest
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from kern import rechte
from kern.models import Anhang, Eintrag, Eintragsversion, Status
from kern.staende import lesekontext, lesemenge, lesestand, sichtbare_anhaenge
from kern.suchindex import KONFIGURATION

#: Ab so vielen Zeichen wird gesucht (SPEC.md §9).
MINDESTLAENGE = 2

#: Je Gruppe höchstens so viele Treffer auf der Ergebnisseite.
TREFFER_JE_GRUPPE = 20

#: Ab dieser Ähnlichkeit gilt ein Wort als Tippfehler-Treffer.
AEHNLICHKEIT = 0.35


@dataclass
class Treffer:
    titel: str
    url: str
    kontext: str = ""
    ausschnitt: str = ""
    kennung: str = ""
    status: str = ""
    status_text: str = ""
    zusatz: str = ""
    vorschau_url: str = ""
    original_url: str = ""

    @property
    def ist_entwurf(self) -> bool:
        return bool(self.status) and self.status != Status.BESCHLOSSEN


@dataclass
class Gruppe:
    schluessel: str
    name: str
    treffer: list[Treffer] = field(default_factory=list)
    gesamt: int = 0

    @property
    def mehr(self) -> int:
        return max(0, self.gesamt - len(self.treffer))


@dataclass
class Ergebnis:
    begriff: str
    gruppen: list[Gruppe] = field(default_factory=list)
    ueber_aehnlichkeit: bool = False
    """Wahr, wenn nur die Tippfehlersuche etwas gefunden hat."""
    nur_wortlaut: bool = False
    """Wahr, wenn die Eingabe nur aus Füllwörtern bestand."""

    @property
    def gesamt(self) -> int:
        return sum(g.gesamt for g in self.gruppen)

    @property
    def leer(self) -> bool:
        return self.gesamt == 0

    @property
    def gefuellte_gruppen(self) -> list[Gruppe]:
        return [g for g in self.gruppen if g.treffer]


def hat_suchbegriffe(begriff: str) -> bool:
    """Bleibt von der Eingabe nach dem Wörterbuch etwas übrig?

    Die deutsche Konfiguration wirft Füllwörter weg. „Es war einmal“ besteht
    nur aus solchen – die Volltextanfrage wäre leer und fände nichts, ohne dass
    jemand merkt, warum. Für diese Fälle wird nach dem genauen Wortlaut gesucht.
    """
    with connection.cursor() as zeiger:
        zeiger.execute(
            "SELECT websearch_to_tsquery(%s::regconfig, %s)::text", [KONFIGURATION, begriff]
        )
        return bool((zeiger.fetchone() or [""])[0])


def wortlaut_ausschnitt(text: str, begriff: str, umfeld: int = 90) -> str:
    """Trefferausschnitt für die Suche nach dem genauen Wortlaut."""
    if not text:
        return ""
    stelle = text.lower().find(begriff.lower())
    if stelle < 0:
        return escape(text[: umfeld * 2])
    von = max(0, stelle - umfeld)
    bis = min(len(text), stelle + len(begriff) + umfeld)
    davor = ("… " if von else "") + escape(text[von:stelle])
    danach = escape(text[stelle + len(begriff) : bis]) + (" …" if bis < len(text) else "")
    return mark_safe(  # noqa: S308 – alle Teile sind escaped
        f"{davor}<mark>{escape(text[stelle : stelle + len(begriff)])}</mark>{danach}"
    )


def _anfrage(begriff: str) -> SearchQuery:
    """Sucheingabe in eine Volltextanfrage übersetzen.

    ``websearch`` versteht, was Leute aus Suchmaschinen kennen:
    Anführungszeichen für Wortgruppen, ``-`` zum Ausschließen, ``OR``.
    """
    return SearchQuery(begriff, config=KONFIGURATION, search_type="websearch")


def _ausschnitt(feld: str, begriff: str) -> SearchHeadline:
    return SearchHeadline(
        feld,
        _anfrage(begriff),
        config=KONFIGURATION,
        start_sel="<mark>",
        stop_sel="</mark>",
        max_words=32,
        min_words=12,
        max_fragments=2,
        fragment_delimiter=" … ",
    )


#: Beschlossenes zuerst, dann abgestimmt, dann der Rest (SPEC.md §9).
_STATUS_REIHENFOLGE = Case(
    When(lese_status=Status.BESCHLOSSEN, then=Value(0)),
    When(lese_status=Status.ABGESTIMMT, then=Value(1)),
    When(lese_status=Status.ARCHIVIERT, then=Value(3)),
    default=Value(2),
    output_field=FloatField(),
)


def suchen(
    nutzer,
    begriff: str,
    dokument: str = "",
    status: str = "",
    jahrgang: str = "",
    fach: str = "",
    gruppe: str = "",
) -> Ergebnis:
    """Sucht über alle Gruppen. ``gruppe`` schränkt auf eine davon ein."""
    begriff = (begriff or "").strip()
    ergebnis = Ergebnis(begriff=begriff)
    if len(begriff) < MINDESTLAENGE:
        return ergebnis

    wortlaut = not hat_suchbegriffe(begriff)
    ergebnis.nur_wortlaut = wortlaut

    # Einmal gefiltert, dann von Einträgen und Dateien gemeinsam benutzt:
    # Eine Datei, die an einem Vorhaben aus Jahrgang 3 hängt, darf beim Filter
    # „Jahrgang 1" nicht auftauchen – sonst widersprächen sich die Gruppen.
    grundmenge = _gefiltert(nutzer, dokument, status, jahrgang, fach)
    prozessmenge = _gefiltert(nutzer, dokument, status, jahrgang, fach, prozesse=True)

    bauer = {
        "handbuch": lambda: _handbuch_suchen(nutzer, begriff, dokument, status, jahrgang, fach),
        "prozesse": lambda: _prozesse_suchen(nutzer, prozessmenge, begriff),
        "eintraege": lambda: _eintraege_suchen(nutzer, grundmenge, begriff, wortlaut),
        "beschluesse": lambda: _beschluesse_suchen(nutzer, begriff, wortlaut),
        "kompetenzen": lambda: _kompetenzen_suchen(begriff, fach),
        "dateien": lambda: _dateien_suchen(
            nutzer, grundmenge, begriff, wortlaut, bool(jahrgang or dokument or fach or status)
        ),
    }
    if gruppe in bauer:
        ergebnis.gruppen = [bauer[gruppe]()]
    else:
        ergebnis.gruppen = [b() for b in bauer.values()]

    # Findet der Volltext keinen Eintrag, nach ähnlich geschriebenen suchen.
    #
    # Das hängt bewusst nur an der Gruppe „Arbeitspläne und Konzepte“ und nicht
    # am Gesamtergebnis: Wer sich bei „Märchen“ vertippt, bekommt über die
    # Kompetenzsuche trotzdem ein paar Treffer – und würde ohne diese
    # Unterscheidung nie erfahren, dass es das Vorhaben gibt.
    eintragsgruppe = next((g for g in ergebnis.gruppen if g.schluessel == "eintraege"), None)
    if eintragsgruppe is not None and not eintragsgruppe.treffer:
        aehnlich = _aehnlich_suchen(nutzer, grundmenge, begriff)
        if aehnlich.treffer:
            ergebnis.gruppen = [
                aehnlich if g.schluessel == "eintraege" else g for g in ergebnis.gruppen
            ]
            ergebnis.ueber_aehnlichkeit = True

    return ergebnis


# --- Einträge --------------------------------------------------------------


def _gefiltert(nutzer, dokument: str, status: str, jahrgang: str, fach: str, *, prozesse=False):
    """Alle Einträge, die dieser Nutzer sehen darf, nach den Filtern beschnitten."""
    from kern import prozesse as prozessdienst

    menge = prozessdienst.menge(nutzer) if prozesse else lesemenge(nutzer, Eintrag.objects.all())
    menge = menge.select_related("dokument", "eltern", "eltern__eltern")

    if dokument:
        menge = menge.filter(dokument__schluessel=dokument)
    if status:
        menge = menge.filter(lese_status=status)
    if fach:
        menge = menge.filter(dokument__fach=fach)
    if jahrgang.isdigit():
        # „jahrgang" steht im JSON-Feld „daten" der Vorhaben.
        menge = menge.filter(lese_daten__jahrgang=int(jahrgang))
    return menge


def _eintraege_suchen(nutzer, menge, begriff: str, wortlaut: bool = False) -> Gruppe:
    from kern.handbuch import kanonisch

    menge = menge.exclude(eintragstyp="prozess").exclude(pk__in=kanonisch().values("pk"))
    if wortlaut:
        treffer = (
            menge.filter(Q(lese_titel__icontains=begriff) | Q(lese_suchtext__icontains=begriff))
            .annotate(reihenfolge=_STATUS_REIHENFOLGE)
            .order_by("reihenfolge", "kennung")
        )
    else:
        anfrage = _anfrage(begriff)
        treffer = (
            menge.filter(lese_suchvektor=anfrage)
            .annotate(
                rang=SearchRank(F("lese_suchvektor"), anfrage),
                reihenfolge=_STATUS_REIHENFOLGE,
                ausschnitt=_ausschnitt("lese_suchtext", begriff),
            )
            .order_by("reihenfolge", "-rang", "kennung")
        )

    gruppe = Gruppe("eintraege", "Arbeitspläne und Konzepte", gesamt=treffer.count())
    for eintrag in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=eintrag.lese_titel,
                url=reverse("kern:eintrag", args=[eintrag.dokument.schluessel, eintrag.kennung]),
                kontext=lesekontext(nutzer, eintrag),
                ausschnitt=(
                    wortlaut_ausschnitt(eintrag.lese_suchtext, begriff)
                    if wortlaut
                    else eintrag.ausschnitt
                ),
                kennung=eintrag.kennung,
                status=eintrag.lese_status,
                status_text=Status(eintrag.lese_status).label,
                zusatz=eintrag.typ.name if eintrag.typ else "",
            )
        )
    return gruppe


def _handbuch_suchen(nutzer, begriff, dokument="", status="", jahrgang="", fach=""):
    from kern import handbuch

    menge = handbuch.menge(nutzer).exclude(eintragstyp="prozess")
    if dokument:
        menge = menge.filter(dokument__schluessel=dokument)
    if status:
        menge = menge.filter(lese_status=status)
    if jahrgang.isdigit():
        menge = menge.filter(lese_daten__jahrgang=int(jahrgang))
    if fach:
        menge = menge.filter(dokument__fach=fach)
    treffer = handbuch.suchen(menge, begriff).order_by("lese_titel", "pk")
    gruppe = Gruppe("handbuch", "Schulhandbuch und Formulare", gesamt=treffer.count())
    for e in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=e.lese_titel,
                url=handbuch.leselink(e),
                kontext=e.dokument.titel,
                ausschnitt=escape(e.lese_kurzantwort[:600]),
                kennung=e.kennung,
                status=Status.BESCHLOSSEN,
                status_text="Veröffentlicht",
                zusatz="Handbuch",
            )
        )
    return gruppe


def _prozesse_suchen(nutzer, menge, begriff: str) -> Gruppe:
    from kern import prozesse

    treffer = prozesse.suchen(menge, begriff).order_by("lese_titel", "pk")
    gruppe = Gruppe("prozesse", "Veröffentlichte Abläufe", gesamt=treffer.count())
    for e in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=e.lese_titel,
                url=prozesse.leselink(e),
                kontext=e.dokument.titel,
                ausschnitt=escape(e.lese_daten.get("anlass", "")[:360]),
                kennung=e.kennung,
                status=Status.BESCHLOSSEN,
                status_text="Veröffentlicht",
                zusatz="Prozess",
            )
        )
    return gruppe


# --- Beschlüsse ------------------------------------------------------------


def _beschluesse_suchen(nutzer, begriff: str, wortlaut: bool = False) -> Gruppe:
    if wortlaut:
        treffer = (
            rechte.sichtbare_beschluesse(nutzer)
            .filter(Q(titel__icontains=begriff) | Q(text__icontains=begriff))
            .select_related("gremium")
            .order_by("-datum")
        )
    else:
        anfrage = _anfrage(begriff)
        treffer = (
            rechte.sichtbare_beschluesse(nutzer)
            .filter(suchvektor=anfrage)
            .select_related("gremium")
            .annotate(
                rang=SearchRank(F("suchvektor"), anfrage),
                ausschnitt=_ausschnitt("text", begriff),
            )
            .order_by("-rang", "-datum")
        )

    treffer = treffer.annotate(
        anzahl_fassungen=Count(
            "beschlossene_versionen",
            filter=Q(
                beschlossene_versionen__in=rechte.sichtbare_versionen(
                    nutzer, Eintragsversion.objects.all()
                )
            ),
        )
    )
    gruppe = Gruppe("beschluesse", "Konferenzbeschlüsse", gesamt=treffer.count())
    for beschluss in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=beschluss.titel,
                url=reverse("kern:beschluss", args=[beschluss.pk]),
                kontext=f"{beschluss.gremium} vom {beschluss.datum:%d.%m.%Y}",
                ausschnitt=(
                    wortlaut_ausschnitt(beschluss.text, begriff)
                    if wortlaut
                    else beschluss.ausschnitt
                ),
                zusatz=f"{beschluss.anzahl_fassungen} Fassungen",
            )
        )
    return gruppe


# --- Kompetenzen -----------------------------------------------------------


def _kompetenzen_suchen(begriff: str, fach: str = "") -> Gruppe:
    from fachdaten.suche import kompetenzen_finden

    treffer = kompetenzen_finden(begriff, fach=fach)

    gruppe = Gruppe("kompetenzen", "Kompetenzerwartungen", gesamt=treffer.count())
    for erwartung in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=erwartung.text,
                url=f"{reverse('fachdaten:uebersicht')}?q={erwartung.pk}&fach={erwartung.fach}",
                kontext=f"{erwartung.bereich_name} › {erwartung.schwerpunkt_voll}",
                ausschnitt=escape(erwartung.klammer),
                kennung=erwartung.pk,
                zusatz=erwartung.stufe_klartext,
            )
        )
    return gruppe


# --- Dateien ---------------------------------------------------------------


def _dateien_suchen(
    nutzer, menge, begriff: str, wortlaut: bool = False, nur_an_eintraegen: bool = False
) -> Gruppe:
    erlaubt = Anhang.objects.filter(eintrag__in=menge)
    if not nur_an_eintraegen:
        # Ohne Filter dürfen auch Anhänge ohne Eintrag erscheinen.
        erlaubt = Anhang.objects.filter(Q(eintrag__isnull=True) | Q(eintrag__in=menge))

    erlaubt = sichtbare_anhaenge(nutzer, erlaubt)
    if wortlaut:
        treffer = (
            erlaubt.filter(
                Q(dateiname__icontains=begriff)
                | Q(beschreibung__icontains=begriff)
                | Q(extrahierter_text__icontains=begriff)
            )
            .select_related("eintrag", "eintrag__dokument", "dokument", "nextcloud_ordner")
            .order_by("dateiname")
        )
    else:
        anfrage = _anfrage(begriff)
        treffer = (
            erlaubt.filter(suchvektor=anfrage)
            .select_related("eintrag", "eintrag__dokument", "dokument", "nextcloud_ordner")
            .annotate(
                rang=SearchRank(F("suchvektor"), anfrage),
                ausschnitt=_ausschnitt("extrahierter_text", begriff),
            )
            .order_by("-rang", "dateiname")
        )

    gruppe = Gruppe("dateien", "Dateien", gesamt=treffer.count())
    for anhang in treffer[:TREFFER_JE_GRUPPE]:
        if anhang.eintrag_id:
            url = reverse(
                "kern:eintrag", args=[anhang.eintrag.dokument.schluessel, anhang.eintrag.kennung]
            )
            stand = lesestand(nutzer, anhang.eintrag)
            kontext = f"Anhang zu {stand.kennung} {stand.titel}"
        else:
            url = anhang.datei.url if anhang.datei else anhang.nextcloud_link
            kontext = anhang.dokument.titel if anhang.dokument else "Freier Anhang"
            if anhang.nextcloud_ordner_id:
                kontext = f"Nextcloud › {anhang.nextcloud_ordner.name} › {anhang.nextcloud_pfad}"

        gruppe.treffer.append(
            Treffer(
                titel=anhang.dateiname,
                url=url,
                kontext=kontext,
                ausschnitt=(
                    wortlaut_ausschnitt(anhang.extrahierter_text, begriff)
                    if wortlaut
                    else (
                        mark_safe(nh3.clean(anhang.ausschnitt, tags={"mark"}, attributes={}))
                        if anhang.extrahierter_text
                        else escape(anhang.beschreibung)
                    )
                ),
                zusatz="Nextcloud" if anhang.nextcloud_link and not anhang.datei else "",
                vorschau_url=reverse("kern:anhang_vorschau", args=[anhang.pk]),
                original_url=anhang.datei.url if anhang.datei else anhang.nextcloud_link,
            )
        )
    return gruppe


# --- Tippfehlersuche -------------------------------------------------------


def _aehnlich_suchen(nutzer, menge, begriff: str) -> Gruppe:
    """Letzter Versuch: ähnlich geschriebene Titel und Kennungen."""
    from kern.handbuch import kanonisch

    treffer = (
        menge.exclude(eintragstyp="prozess")
        .exclude(pk__in=kanonisch().values("pk"))
        .annotate(
            naehe=Greatest(
                TrigramWordSimilarity(begriff, "lese_titel"),
                TrigramWordSimilarity(begriff, "kennung"),
                TrigramWordSimilarity(begriff, "lese_suchtext"),
            )
        )
        .filter(naehe__gte=AEHNLICHKEIT)
        .order_by("-naehe")
    )

    gruppe = Gruppe(
        "eintraege", "Arbeitspläne und Konzepte (ähnlich geschrieben)", gesamt=treffer.count()
    )
    for eintrag in treffer[:TREFFER_JE_GRUPPE]:
        gruppe.treffer.append(
            Treffer(
                titel=eintrag.lese_titel,
                url=reverse("kern:eintrag", args=[eintrag.dokument.schluessel, eintrag.kennung]),
                kontext=lesekontext(nutzer, eintrag),
                kennung=eintrag.kennung,
                status=eintrag.lese_status,
                status_text=Status(eintrag.lese_status).label,
            )
        )
    return gruppe


# --- Autovervollständigung -------------------------------------------------


def vorschlaege(nutzer, begriff: str, anzahl: int = 8) -> list[Treffer]:
    """Kurze Liste für die Autovervollständigung (SPEC.md §9).

    Gesucht wird über Titel, Kennungen, Kompetenz-Kennungen, Kapitel und
    Beschlusstitel – tippfehlertolerant über ``pg_trgm``.
    """
    from fachdaten.models import Kompetenzerwartung

    begriff = (begriff or "").strip()
    if len(begriff) < MINDESTLAENGE:
        return []

    from kern import handbuch, prozesse

    gefunden = _handbuch_suchen(nutzer, begriff).treffer[:anzahl]
    gefunden.extend(
        _prozesse_suchen(nutzer, prozesse.menge(nutzer), begriff).treffer[: anzahl - len(gefunden)]
    )

    eintraege = (
        lesemenge(
            nutzer,
            Eintrag.objects.exclude(eintragstyp="prozess").exclude(
                pk__in=handbuch.kanonisch().values("pk")
            ),
        )
        .select_related("dokument", "eltern")
        .annotate(
            naehe=Greatest(
                TrigramWordSimilarity(begriff, "lese_titel"),
                TrigramWordSimilarity(begriff, "kennung"),
            ),
            reihenfolge=_STATUS_REIHENFOLGE,
        )
        .filter(
            Q(lese_titel__icontains=begriff)
            | Q(kennung__istartswith=begriff)
            | Q(naehe__gte=AEHNLICHKEIT)
        )
        .order_by("reihenfolge", "-naehe")[: anzahl - len(gefunden)]
    )
    for eintrag in eintraege:
        gefunden.append(
            Treffer(
                titel=eintrag.lese_titel,
                url=reverse("kern:eintrag", args=[eintrag.dokument.schluessel, eintrag.kennung]),
                kontext=lesekontext(nutzer, eintrag),
                kennung=eintrag.kennung,
                status=eintrag.lese_status,
                status_text=Status(eintrag.lese_status).label,
            )
        )

    rest = anzahl - len(gefunden)
    if rest > 0:
        for erwartung in Kompetenzerwartung.objects.filter(
            Q(id__istartswith=begriff) | Q(text__icontains=begriff)
        ).order_by("id")[:rest]:
            gefunden.append(
                Treffer(
                    titel=erwartung.text,
                    url=f"{reverse('fachdaten:uebersicht')}?q={erwartung.pk}&fach={erwartung.fach}",
                    kontext=erwartung.schwerpunkt_voll,
                    kennung=erwartung.pk,
                    zusatz="Kompetenz",
                )
            )

    rest = anzahl - len(gefunden)
    if rest > 0:
        for beschluss in (
            rechte.sichtbare_beschluesse(nutzer)
            .filter(titel__icontains=begriff)
            .select_related("gremium")[:rest]
        ):
            gefunden.append(
                Treffer(
                    titel=beschluss.titel,
                    url=reverse("kern:beschluss", args=[beschluss.pk]),
                    kontext=f"{beschluss.gremium} vom {beschluss.datum:%d.%m.%Y}",
                    zusatz="Beschluss",
                )
            )

    return gefunden[:anzahl]
