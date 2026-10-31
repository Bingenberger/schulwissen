"""Generischer, atomarer JSON-Import mit schreibfreier Vorschau."""

from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from eintragstypen.dienste import Befundsatz, Rohsatz, pruefen, speichern
from eintragstypen.registry import registry
from kern.models import Dokument, Eintrag, Status


@dataclass
class Importbericht:
    saetze: list[Befundsatz] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)
    geschrieben: int = 0

    @property
    def ok(self):
        return not self.fehler and all(s.ok for s in self.saetze)

    def als_text(self):
        zeilen = list(self.fehler)
        for satz in self.saetze:
            zeilen.append(f"{satz.roh.kennung}: {satz.roh.titel}")
            zeilen.extend(f"  [{b.schwere}] {b.text}" for b in satz.befunde)
        zeilen.append(f"{len(self.saetze)} Einträge geprüft, {self.geschrieben} geschrieben.")
        return "\n".join(zeilen)


def pruefen_json(inhalt, dokument, nutzer=None):
    bericht = Importbericht()
    if not isinstance(inhalt, dict) or inhalt.get("dokument") != dokument.schluessel:
        bericht.fehler.append("Der Dokument-Schlüssel passt nicht zum Zieldokument.")
        return bericht
    if inhalt.get("schema_version", 1) != 1:
        bericht.fehler.append("Diese Schema-Version wird nicht unterstützt.")
        return bericht
    zeilen = inhalt.get("eintraege")
    if not isinstance(zeilen, list):
        bericht.fehler.append("„eintraege“ muss eine Liste sein.")
        return bericht
    kennungen = set()
    for zeile in zeilen:
        if not isinstance(zeile, dict):
            bericht.fehler.append("Jeder Eintrag muss ein JSON-Objekt sein.")
            continue
        kennung = zeile.get("kennung")
        if not isinstance(kennung, str) or not kennung.strip() or len(kennung) > 40:
            bericht.fehler.append("Eine Kennung muss Text mit 1 bis 40 Zeichen sein.")
        elif kennung in kennungen:
            bericht.fehler.append(f"Die Kennung „{kennung}“ kommt mehrfach vor.")
        else:
            kennungen.add(kennung)
    if bericht.fehler:
        return bericht

    vorhanden = {e.kennung: e for e in dokument.eintraege.all()}
    eltern = {k: e.eltern.kennung if e.eltern else None for k, e in vorhanden.items()}
    for zeile in zeilen:
        kennung = zeile["kennung"]
        typname = zeile.get("eintragstyp")
        if not isinstance(typname, str) or not registry.bekannt(typname):
            bericht.fehler.append(f"{kennung}: unbekannter Eintragstyp.")
            continue
        typ = registry.holen(typname)
        erlaubt = {
            "kennung",
            "eintragstyp",
            "titel",
            "status",
            "daten",
            "eltern",
            "position",
            "verantwortlich_text",
            "fassung_stand",
            "fassungen",
            "anhaenge",
            "verlinkungen",
            *[f.schluessel for f in typ.verlinkungsfelder],
        }
        unbekannt = set(zeile) - erlaubt
        if unbekannt:
            bericht.fehler.append(f"{kennung}: unbekannte Felder: {', '.join(sorted(unbekannt))}.")
        if not isinstance(zeile.get("daten", {}), dict):
            bericht.fehler.append(f"{kennung}: „daten“ muss ein Objekt sein.")
            continue
        if not isinstance(zeile.get("titel"), str) or len(zeile["titel"]) > 300:
            bericht.fehler.append(f"{kennung}: Titel als Text mit höchstens 300 Zeichen erwartet.")
            continue
        if not isinstance(zeile.get("status", Status.ENTWURF), str):
            bericht.fehler.append(f"{kennung}: ungültiger Status.")
            continue
        if (
            not isinstance(zeile.get("verantwortlich_text", ""), str)
            or len(zeile.get("verantwortlich_text", "")) > 200
        ):
            bericht.fehler.append(f"{kennung}: ungültige Verantwortlichenangabe.")
            continue
        verweise = {}
        for feld in typ.verlinkungsfelder:
            if feld.schluessel in zeile:
                wert = zeile[feld.schluessel]
                if not isinstance(wert, list) or any(not isinstance(z, str) for z in wert):
                    bericht.fehler.append(
                        f"{kennung}: {feld.schluessel} muss eine Liste von Kennungen sein."
                    )
                else:
                    verweise[feld.schluessel] = wert
        stand = zeile.get("fassung_stand")
        if stand is not None and stand != "":
            try:
                stand = date.fromisoformat(stand)
            except (TypeError, ValueError):
                bericht.fehler.append(f"{kennung}: ungültiges Fassungsdatum.")
                continue
        roh = Rohsatz(
            kennung=kennung,
            eintragstyp=typname,
            titel=zeile["titel"],
            status=zeile.get("status", Status.ENTWURF),
            daten=zeile.get("daten", {}),
            verweise=verweise,
            verantwortlich_text=zeile.get("verantwortlich_text", ""),
            fassung_stand=stand,
            quelle="JSON-Import",
        )
        satz = pruefen(dokument, roh, entstehende_kennungen=kennungen, nutzer=nutzer)
        # Ein Import darf die Vollständigkeitsprüfung beim Abstimmen nicht umgehen.
        if (
            roh.status in (Status.ABGESTIMMT, Status.BESCHLOSSEN, Status.ARCHIVIERT)
            and satz.fehlende_pflichtfelder
        ):
            bericht.fehler.append(f"{kennung}: Für „abgestimmt“ fehlen Pflichtfelder.")
        bericht.saetze.append(satz)
        if "eltern" in zeile:
            ziel = zeile["eltern"]
            if ziel is not None and (
                not isinstance(ziel, str) or ziel not in kennungen | set(vorhanden)
            ):
                bericht.fehler.append(f"{kennung}: unbekanntes übergeordnetes Kapitel.")
            else:
                eltern[kennung] = ziel
        if "position" in zeile and (
            type(zeile["position"]) is not int or not 0 <= zeile["position"] <= 2147483647
        ):
            bericht.fehler.append(f"{kennung}: Position muss eine nichtnegative ganze Zahl sein.")
    for kennung in eltern:
        gesehen = set()
        knoten = kennung
        while knoten is not None:
            if knoten in gesehen:
                bericht.fehler.append(f"{kennung}: Die Gliederung enthält einen Kreis.")
                break
            gesehen.add(knoten)
            knoten = eltern.get(knoten)
    return bericht


@transaction.atomic
def uebernehmen_json(inhalt, dokument, nutzer=None, erwarteter_stand=None):
    # Verhindert konkurrierende Importe in dasselbe Dokument.
    Dokument.objects.select_for_update().get(pk=dokument.pk)
    if erwarteter_stand is not None:
        from django.core.exceptions import PermissionDenied

        from kern import rechte
        from kern.schreibschutz import Schreibkonflikt, dokumentstand

        if nutzer is not None and not rechte.darf_importieren(nutzer):
            raise PermissionDenied("Die Importberechtigung ist nicht mehr vorhanden.")
        if dokumentstand(dokument) != erwarteter_stand:
            raise Schreibkonflikt(
                "Das Dokument wurde seit der Vorschau geändert. "
                "Bitte prüfe die erneuerte Vorschau; es wurde nichts importiert."
            )
    bericht = pruefen_json(inhalt, dokument, nutzer=nutzer)
    if not bericht.ok:
        return bericht
    # Erst alle Kennungen bereitstellen: auch gegenseitige Verweise sind erlaubt.
    for satz in bericht.saetze:
        Eintrag.objects.get_or_create(
            dokument=dokument,
            kennung=satz.roh.kennung,
            defaults={
                "eintragstyp": satz.roh.eintragstyp,
                "titel": satz.roh.titel,
                "erstellt_von": nutzer,
            },
        )
    zuordnung = {e.kennung: e for e in dokument.eintraege.all()}
    rohzeilen = {z["kennung"]: z for z in inhalt["eintraege"]}
    for satz in bericht.saetze:
        frisch = pruefen(dokument, satz.roh, nutzer=nutzer)
        if not frisch.ok:
            raise ValidationError("Der Datensatz ist während des Imports ungültig geworden.")
        eintrag = speichern(dokument, frisch, nutzer=nutzer)
        zeile = rohzeilen[eintrag.kennung]
        if "eltern" in zeile:
            eintrag.eltern = zuordnung.get(zeile["eltern"])
        if "position" in zeile:
            eintrag.position = zeile["position"]
        eintrag.save(update_fields=["eltern", "position"])
        bericht.geschrieben += 1
    return bericht
