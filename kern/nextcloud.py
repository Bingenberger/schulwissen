"""Nextcloud-Dateien verlinken (SPEC.md §10, Stufe 1).

Die Nextcloud bleibt die Dateiablage. Diese App verlinkt nur: ein technisches
Konto (App-Passwort in ``.env``) darf die Ordner lesen, damit sich eine Datei
im Browser durchklicken lässt. Gespeichert werden der Pfad und ein Link.

**Welcher Link?** Bewusst *kein* öffentlicher Freigabe-Link, sondern die
Adresse der Datei in der Nextcloud-Oberfläche. Wer darauf klickt, muss sich
mit dem eigenen Konto anmelden und sieht nur, was er ohnehin sehen darf. Ein
öffentlicher Link wäre für jeden erreichbar, der ihn kennt – bei
Konferenzprotokollen und Konzepten ist das nicht gewollt.

Stufe 2 (Phase 4) holt zusätzlich den Text dieser Dateien und indexiert ihn.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import quote, urljoin
from xml.etree import ElementTree

from django.conf import settings

logger = logging.getLogger(__name__)

DAV = "{DAV:}"

#: Dateiendungen, die im Browser ein passendes Zeichen bekommen.
ZEICHEN_JE_ENDUNG = {
    "pdf": "PDF",
    "doc": "DOC",
    "docx": "DOC",
    "odt": "ODT",
    "xls": "XLS",
    "xlsx": "XLS",
    "ods": "ODS",
    "ppt": "PPT",
    "pptx": "PPT",
    "odp": "ODP",
    "jpg": "BILD",
    "jpeg": "BILD",
    "png": "BILD",
    "gif": "BILD",
    "txt": "TXT",
    "md": "TXT",
    "zip": "ZIP",
}


class NextcloudFehler(Exception):
    """Die Nextcloud ließ sich nicht erreichen oder antwortete unerwartet."""

    def __init__(self, text="", status=None):
        super().__init__(text)
        self.status = status


@dataclass
class Eintrag:
    """Eine Datei oder ein Ordner in der Nextcloud."""

    name: str
    pfad: str
    ist_ordner: bool
    groesse: int = 0
    mimetype: str = ""
    etag: str = ""

    @property
    def endung(self) -> str:
        return self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""

    @property
    def zeichen(self) -> str:
        if self.ist_ordner:
            return "ORDNER"
        return ZEICHEN_JE_ENDUNG.get(self.endung, self.endung.upper() or "DATEI")


def ist_eingerichtet() -> bool:
    """Steht ein Nextcloud-Zugang in der Konfiguration?"""
    return bool(
        getattr(settings, "NEXTCLOUD_URL", "")
        and getattr(settings, "NEXTCLOUD_NUTZER", "")
        and getattr(settings, "NEXTCLOUD_PASSWORT", "")
    )


def _dav_wurzel() -> str:
    basis = settings.NEXTCLOUD_URL.rstrip("/") + "/"
    return urljoin(basis, f"remote.php/dav/files/{quote(settings.NEXTCLOUD_NUTZER, safe='')}/")


def weblink(pfad: str) -> str:
    """Adresse der Datei in der Nextcloud-Oberfläche.

    Wer sie öffnet, meldet sich mit dem eigenen Konto an – die Rechte der
    Nextcloud gelten also weiter.
    """
    basis = settings.NEXTCLOUD_URL.rstrip("/")
    pfad = pfad.strip("/")
    if "/" in pfad:
        ordner, name = pfad.rsplit("/", 1)
    else:
        ordner, name = "", pfad
    return f"{basis}/apps/files/?dir=/{quote(ordner)}&scrollto={quote(name)}"


def _pfad_saeubern(pfad: str) -> str:
    """Verhindert, dass jemand über ``..`` aus dem Wurzelordner herauskommt."""
    teile = [t for t in (pfad or "").split("/") if t and t not in (".", "..")]
    return "/".join(teile)


def auflisten(pfad: str = "", zeitgrenze: float = 15.0) -> list[Eintrag]:
    """Listet einen Ordner der Nextcloud per WebDAV auf."""
    import httpx

    if not ist_eingerichtet():
        raise NextcloudFehler(
            "Es ist kein Nextcloud-Zugang eingerichtet. "
            "SW_NEXTCLOUD_URL, SW_NEXTCLOUD_NUTZER und SW_NEXTCLOUD_PASSWORT "
            "gehören in die .env – siehe DEPLOYMENT.md."
        )

    pfad = _pfad_saeubern(pfad)
    wurzel = _dav_wurzel()
    adresse = urljoin(wurzel, quote(pfad) + "/" if pfad else "")

    anfrage = (
        '<?xml version="1.0"?>'
        '<d:propfind xmlns:d="DAV:">'
        "<d:prop>"
        "<d:displayname/><d:resourcetype/><d:getcontentlength/>"
        "<d:getcontenttype/><d:getetag/>"
        "</d:prop>"
        "</d:propfind>"
    )

    try:
        antwort = httpx.request(
            "PROPFIND",
            adresse,
            content=anfrage,
            headers={"Depth": "1", "Content-Type": "application/xml"},
            auth=(settings.NEXTCLOUD_NUTZER, settings.NEXTCLOUD_PASSWORT),
            timeout=zeitgrenze,
        )
    except httpx.HTTPError as fehler:
        raise NextcloudFehler(f"Die Nextcloud ist nicht erreichbar: {fehler}") from fehler

    if antwort.status_code == 401:
        raise NextcloudFehler("Die Nextcloud hat die Anmeldung abgelehnt. Stimmt das App-Passwort?")
    if antwort.status_code == 404:
        raise NextcloudFehler(f"Den Ordner „{pfad or '/'}“ gibt es nicht.", status=404)
    if antwort.status_code in (403, 410):
        raise NextcloudFehler(
            "Dieser Nextcloud-Ordner ist nicht mehr zugänglich.", status=antwort.status_code,
        )
    if antwort.status_code != 207:
        raise NextcloudFehler(f"Unerwartete Antwort der Nextcloud: {antwort.status_code}.")

    return _antwort_lesen(antwort.text, wurzel, pfad)


def _antwort_lesen(xml: str, wurzel: str, pfad: str) -> list[Eintrag]:
    from urllib.parse import unquote, urlparse

    wurzelpfad = urlparse(wurzel).path
    eigener_pfad = f"{wurzelpfad}{quote(pfad)}/" if pfad else wurzelpfad

    eintraege: list[Eintrag] = []
    for antwortknoten in ElementTree.fromstring(xml).findall(f"{DAV}response"):
        href = antwortknoten.findtext(f"{DAV}href") or ""
        if unquote(href.rstrip("/")) == unquote(eigener_pfad.rstrip("/")):
            # Der Ordner selbst steht auch in der Antwort.
            continue

        eigenschaften = antwortknoten.find(f"{DAV}propstat/{DAV}prop")
        if eigenschaften is None:
            continue

        ist_ordner = eigenschaften.find(f"{DAV}resourcetype/{DAV}collection") is not None
        relativ = unquote(href)[len(wurzelpfad) :].strip("/")
        name = eigenschaften.findtext(f"{DAV}displayname") or relativ.rsplit("/", 1)[-1]
        laenge = eigenschaften.findtext(f"{DAV}getcontentlength") or "0"

        eintraege.append(
            Eintrag(
                name=name,
                pfad=relativ,
                ist_ordner=ist_ordner,
                groesse=int(laenge) if laenge.isdigit() else 0,
                mimetype=eigenschaften.findtext(f"{DAV}getcontenttype") or "",
                etag=(eigenschaften.findtext(f"{DAV}getetag") or "").strip('"'),
            )
        )

    # Ordner zuerst, dann alphabetisch – so wie man es aus dem Dateimanager kennt.
    return sorted(eintraege, key=lambda e: (not e.ist_ordner, e.name.lower()))


def brotkrumen(pfad: str) -> list[tuple[str, str]]:
    """``[(Name, Pfad), …]`` für den Weg zurück nach oben."""
    teile = _pfad_saeubern(pfad).split("/") if _pfad_saeubern(pfad) else []
    weg = [("Nextcloud", "")]
    gesammelt: list[str] = []
    for teil in teile:
        gesammelt.append(teil)
        weg.append((teil, "/".join(gesammelt)))
    return weg


@dataclass
class Download:
    status: int
    etag: str = ""
    mimetype: str = ""
    groesse: int = 0


def herunterladen(pfad, ziel, etag=""):
    """Lädt eine verlinkte Datei begrenzt und ohne Weiterleitungen per WebDAV."""
    import httpx

    if not ist_eingerichtet():
        raise NextcloudFehler("Es ist kein Nextcloud-Zugang eingerichtet.")
    adresse = _dav_wurzel() + quote(_pfad_saeubern(pfad), safe="/")
    headers = {"If-None-Match": etag} if etag else {}
    try:
        with httpx.stream(
            "GET",
            adresse,
            auth=(settings.NEXTCLOUD_NUTZER, settings.NEXTCLOUD_PASSWORT),
            headers=headers,
            timeout=30,
            follow_redirects=False,
        ) as antwort:
            if antwort.status_code in (304, 403, 404, 410):
                return Download(antwort.status_code)
            if antwort.status_code != 200:
                raise NextcloudFehler(f"Nextcloud antwortet mit Status {antwort.status_code}.")
            laenge = antwort.headers.get("Content-Length", "")
            if laenge.isdigit() and int(laenge) > settings.NEXTCLOUD_MAX_BYTES:
                raise NextcloudFehler("Die Datei überschreitet die eingestellte Größenbegrenzung.")
            groesse = 0
            with ziel.open("wb") as datei:
                for teil in antwort.iter_bytes():
                    groesse += len(teil)
                    if groesse > settings.NEXTCLOUD_MAX_BYTES:
                        raise NextcloudFehler(
                            "Die Datei überschreitet die eingestellte Größenbegrenzung."
                        )
                    datei.write(teil)
            return Download(
                200,
                antwort.headers.get("ETag", "")[:500],
                antwort.headers.get("Content-Type", "").split(";")[0][:120],
                groesse,
            )
    except httpx.HTTPError as fehler:
        raise NextcloudFehler("Die Nextcloud ist vorübergehend nicht erreichbar.") from fehler
