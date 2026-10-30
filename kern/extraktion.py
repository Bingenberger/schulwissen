"""Text aus Anhängen holen, damit die Suche ihn findet (SPEC.md §9).

Unterstützt PDF, DOCX, ODT und einfachen Text. Was sich nicht lesen lässt,
bleibt ohne Text – die Datei ist dann über Dateiname und Beschreibung
auffindbar, nur nicht über ihren Inhalt.

Die Extraktion läuft **nicht** beim Hochladen, sondern im Hintergrund
(``manage.py anhaenge_indexieren``). Ein 200-seitiges PDF soll das Kollegium
nicht warten lassen.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

#: Mehr Text als das braucht kein Suchindex – und PostgreSQL begrenzt einen
#: tsvector ohnehin auf etwa 1 MB.
HOECHSTLAENGE = 400_000

#: Welche Dateiendung mit welcher Funktion gelesen wird.
LESER_JE_ENDUNG = {
    ".pdf": "_aus_pdf",
    ".docx": "_aus_docx",
    ".odt": "_aus_odt",
    ".ods": "_aus_odt",
    ".odp": "_aus_odt",
    ".txt": "_aus_text",
    ".md": "_aus_text",
    ".csv": "_aus_text",
}


class NichtLesbar(Exception):
    """Die Datei lässt sich nicht als Text lesen."""


def ist_lesbar(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in LESER_JE_ENDUNG


def aufraeumen(text: str) -> str:
    """Mehrfache Leerzeichen und Umbrüche zusammenfassen."""
    return re.sub(r"\s+", " ", text or "").strip()[:HOECHSTLAENGE]


def text_holen(pfad: Path, dateiname: str = "") -> str:
    """Liest den Text einer Datei. Wirft ``NichtLesbar``, wenn es nicht geht."""
    endung = Path(dateiname or pfad).suffix.lower()
    name = LESER_JE_ENDUNG.get(endung)
    if name is None:
        raise NichtLesbar(f"Für „{endung or 'ohne Endung'}“ gibt es keinen Leser.")
    try:
        return aufraeumen(globals()[name](Path(pfad)))
    except NichtLesbar:
        raise
    except Exception as fehler:  # noqa: BLE001 – kaputte Datei darf nichts abbrechen
        raise NichtLesbar(f"{type(fehler).__name__}: {fehler}") from fehler


def _aus_pdf(pfad: Path) -> str:
    from pypdf import PdfReader

    leser = PdfReader(str(pfad))
    if leser.is_encrypted:
        # Manche PDFs sind mit leerem Passwort verschlüsselt – das geht.
        try:
            leser.decrypt("")
        except Exception as fehler:  # noqa: BLE001
            raise NichtLesbar("Das PDF ist mit einem Passwort geschützt.") from fehler

    seiten = []
    for nummer, seite in enumerate(leser.pages, start=1):
        try:
            seiten.append(seite.extract_text() or "")
        except Exception as fehler:  # noqa: BLE001
            logger.warning("Seite %s von %s nicht lesbar: %s", nummer, pfad.name, fehler)
        if sum(len(s) for s in seiten) > HOECHSTLAENGE:
            break

    text = " ".join(seiten)
    if not text.strip():
        # Eingescannte PDFs enthalten nur Bilder. Texterkennung ist in Phase 1
        # bis 4 nicht vorgesehen (SPEC.md §9 nennt sie nicht).
        raise NichtLesbar(
            "Das PDF enthält keinen Text – vermutlich ein Scan. "
            "Bitte im Feld „Beschreibung“ angeben, worum es geht."
        )
    return text


def _aus_docx(pfad: Path) -> str:
    import docx

    dokument = docx.Document(str(pfad))
    teile = [absatz.text for absatz in dokument.paragraphs]
    # Die Arbeitspläne der Schule stecken bisher in Word-Tabellen – die sind
    # der eigentliche Inhalt und dürfen nicht fehlen.
    for tabelle in dokument.tables:
        for zeile in tabelle.rows:
            teile.extend(zelle.text for zelle in zeile.cells)
    return " ".join(teile)


def _aus_odt(pfad: Path) -> str:
    from odf import teletype
    from odf import text as odf_text
    from odf.opendocument import load

    dokument = load(str(pfad))
    absaetze = dokument.getElementsByType(odf_text.P)
    ueberschriften = dokument.getElementsByType(odf_text.H)
    return " ".join(teletype.extractText(k) for k in (*ueberschriften, *absaetze))


def _aus_text(pfad: Path) -> str:
    rohdaten = pfad.read_bytes()[: HOECHSTLAENGE * 4]
    for kodierung in ("utf-8", "cp1252", "latin-1"):
        try:
            return rohdaten.decode(kodierung)
        except UnicodeDecodeError:
            continue
    raise NichtLesbar("Die Zeichenkodierung ließ sich nicht bestimmen.")
