"""Kernmodell der Schulwissen-Plattform.

Die Modulnamen folgen der Django-Konvention (``models.py``), die fachlichen
Klassen- und Feldnamen sind deutsch wie in SPEC.md – damit Import, Export und
Dokumentation zusammenpassen.

Der Kern kennt keine Fachlichkeit: er weiß, dass ein Dokument aus Einträgen
besteht, dass jede Speicherung eine Version erzeugt und dass ein Beschluss
Versionen gültig macht. *Welche* Felder ein Eintrag hat, steht in der Registry
der App ``eintragstypen``.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, PermissionsMixin
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

# --- Rollen ----------------------------------------------------------------

ROLLE_ADMINISTRATION = "Administration"
ROLLE_REDAKTION = "Redaktion"
ROLLE_LEHRKRAFT = "Lehrkraft"
ROLLE_LESEND = "Lesend"


def eintragstyp_auswahl():
    """Die Eintragstypen für das Auswahlfeld.

    Als Funktion, weil die Registry erst gefüllt ist, wenn alle Apps geladen
    sind. Django ruft sie bei Bedarf auf, nicht beim Import.
    """
    from eintragstypen.registry import registry

    return registry.auswahl()


ROLLEN = (
    (ROLLE_ADMINISTRATION, "Nutzer, Dokumenttypen, Stammdaten, Beschlüsse, Import und Export"),
    (ROLLE_REDAKTION, "Einträge bearbeiten, Status bis „abgestimmt“, Beschlussvorlagen"),
    (ROLLE_LEHRKRAFT, "lesen, Entwürfe anlegen und bearbeiten, kommentieren, eigene Planung"),
    (ROLLE_LESEND, "nur beschlossene Inhalte lesen"),
)


# --- Basisklassen ----------------------------------------------------------


class Zeitstempel(models.Model):
    """Gemeinsame Spalten aller Tabellen laut SPEC.md §6."""

    erstellt_am = models.DateTimeField("erstellt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("geändert am", auto_now=True)
    erstellt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="erstellt von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


# --- Nutzer und Gruppen ----------------------------------------------------


class NutzerVerwaltung(BaseUserManager):
    """Anmeldung per E-Mail statt per Benutzername."""

    use_in_migrations = True

    def _anlegen(self, email: str, passwort: str | None, **felder):
        if not email:
            raise ValueError("Ohne E-Mail-Adresse kann kein Konto angelegt werden.")
        nutzer = self.model(email=self.normalize_email(email).lower(), **felder)
        if passwort:
            nutzer.set_password(passwort)
        else:
            # Kein Passwort: Anmeldung erst nach „Passwort vergessen“ möglich.
            nutzer.set_unusable_password()
        nutzer.save(using=self._db)
        return nutzer

    def create_user(self, email: str, password: str | None = None, **felder):
        felder.setdefault("is_staff", False)
        felder.setdefault("is_superuser", False)
        return self._anlegen(email, password, **felder)

    def create_superuser(self, email: str, password: str | None = None, **felder):
        felder["is_staff"] = True
        felder["is_superuser"] = True
        return self._anlegen(email, password, **felder)


class Nutzer(AbstractBaseUser, PermissionsMixin):
    """Konto einer Lehrkraft. Die App speichert keine Schülerdaten (SPEC.md §2.5)."""

    email = models.EmailField("E-Mail", unique=True)
    anzeigename = models.CharField("Anzeigename", max_length=120)
    kuerzel = models.CharField(
        "Kürzel", max_length=10, blank=True, help_text="Wie im Stundenplan, z. B. „FOE“."
    )
    is_active = models.BooleanField("aktiv", default=True)
    is_staff = models.BooleanField(
        "Zugang zur Verwaltung", default=False, help_text="Darf die Django-Verwaltung öffnen."
    )
    date_joined = models.DateTimeField("angelegt am", default=timezone.now)

    objects = NutzerVerwaltung()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["anzeigename"]

    class Meta:
        verbose_name = "Nutzer"
        verbose_name_plural = "Nutzer"
        ordering = ["anzeigename"]

    def __str__(self) -> str:
        return self.anzeigename or self.email

    def get_full_name(self) -> str:
        return self.anzeigename or self.email

    def get_short_name(self) -> str:
        return self.kuerzel or self.anzeigename or self.email

    @property
    def rollen(self) -> set[str]:
        return {gruppe.name for gruppe in self.groups.all()}

    def hat_rolle(self, *namen: str) -> bool:
        return bool(self.rollen & set(namen))


class Gruppenart(models.TextChoices):
    ROLLE = "rolle", "Rolle"
    ARBEITSGRUPPE = "arbeitsgruppe", "Arbeitsgruppe"


class Gruppenprofil(models.Model):
    """Unterscheidet Rollen von Arbeitsgruppen.

    Beides sind Django-Gruppen (so steht es in SPEC.md §6), aber eine Rolle
    vergibt Rechte, eine Arbeitsgruppe wie „Jahrgang 1“ ordnet Einträge zu.
    Ohne diese Unterscheidung stünde beides ungetrennt in derselben Liste.
    """

    gruppe = models.OneToOneField(
        Group, verbose_name="Gruppe", on_delete=models.CASCADE, related_name="profil"
    )
    art = models.CharField("Art", max_length=20, choices=Gruppenart)
    beschreibung = models.CharField("Beschreibung", max_length=250, blank=True)

    class Meta:
        verbose_name = "Gruppenprofil"
        verbose_name_plural = "Gruppenprofile"
        ordering = ["art", "gruppe__name"]

    def __str__(self) -> str:
        return f"{self.gruppe.name} ({self.get_art_display()})"


# --- Dokumente -------------------------------------------------------------


class Dokumenttyp(Zeitstempel):
    """Art eines Dokuments, z. B. ``arbeitsplan_deutsch`` oder ``konzept``.

    Die erlaubten Eintragstypen stehen als Schlüsselliste hier und als Schema im
    Code (App ``eintragstypen``). Ein neuer Dokumenttyp ist damit ein neues
    Modul, kein Umbau des Kerns.
    """

    schluessel = models.SlugField("Schlüssel", max_length=60, unique=True)
    name = models.CharField("Name", max_length=150)
    beschreibung = models.TextField("Beschreibung", blank=True)
    eintragstypen = models.JSONField(
        "erlaubte Eintragstypen",
        default=list,
        blank=True,
        help_text="Schlüssel der Eintragstypen, die in diesem Dokumenttyp vorkommen dürfen.",
    )

    class Meta:
        verbose_name = "Dokumenttyp"
        verbose_name_plural = "Dokumenttypen"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Dokument(Zeitstempel):
    schluessel = models.SlugField(
        "Schlüssel",
        max_length=80,
        unique=True,
        help_text="Kurzname für Adresse und Import, z. B. „arbeitsplan-deutsch“.",
    )
    titel = models.CharField("Titel", max_length=250)
    dokumenttyp = models.ForeignKey(
        Dokumenttyp, verbose_name="Dokumenttyp", on_delete=models.PROTECT, related_name="dokumente"
    )
    fach = models.CharField("Fach", max_length=60, blank=True)
    beschreibung = models.TextField("Beschreibung", blank=True)
    gueltig_ab_schuljahr = models.CharField(
        "gültig ab Schuljahr", max_length=12, blank=True, help_text="z. B. „2027/28“."
    )
    einstellungen = models.JSONField(
        "Einstellungen",
        default=dict,
        blank=True,
        help_text="Dokumentweite Werte, z. B. Deutschstunden pro Woche je Jahrgang.",
    )

    class Meta:
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumente"
        ordering = ["titel"]

    def __str__(self) -> str:
        return self.titel

    @property
    def ist_arbeitsplan(self):
        return self.dokumenttyp.schluessel in ("arbeitsplan_deutsch", "arbeitsplan")

    def naechste_kennung(self, muster: str, **teile) -> str:
        """Nächste freie Kennung für ein Muster wie ``R-{nr:02d}``.

        Zählt immer von der höchsten je vergebenen Kennung hoch, auch wenn
        Einträge archiviert wurden: Kennungen werden laut SPEC.md §6 nie neu
        vergeben.
        """
        nummern = []
        praefix = muster.split("{nr")[0].format(**teile)
        vergeben = list(
            self.eintraege.filter(kennung__startswith=praefix).values_list("kennung", flat=True)
        )
        vergeben += list(
            self.reservierte_kennungen.filter(kennung__startswith=praefix).values_list(
                "kennung", flat=True
            )
        )
        for kennung in vergeben:
            rest = kennung[len(praefix) :]
            if rest.isdigit():
                nummern.append(int(rest))
        return muster.format(nr=max(nummern, default=0) + 1, **teile)


class ReservierteKennung(models.Model):
    """Eine gelöschte Kennung bleibt vergeben, ohne ihren Inhalt aufzubewahren."""

    dokument = models.ForeignKey(
        Dokument, on_delete=models.CASCADE, related_name="reservierte_kennungen"
    )
    kennung = models.CharField(max_length=40)
    geloescht_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dokument", "kennung"], name="reservierte_kennung_je_dokument"
            )
        ]

    def __str__(self):
        return f"{self.dokument_id}: {self.kennung}"


# --- Einträge --------------------------------------------------------------


class Status(models.TextChoices):
    IDEE = "idee", "Idee"
    ENTWURF = "entwurf", "Entwurf"
    ABGESTIMMT = "abgestimmt", "abgestimmt in Gruppe"
    BESCHLOSSEN = "beschlossen", "beschlossen"
    ARCHIVIERT = "archiviert", "archiviert"


#: Status, die eine Lehrkraft oder die Redaktion selbst setzen darf.
STATUS_VOR_BESCHLUSS = (Status.IDEE, Status.ENTWURF, Status.ABGESTIMMT)


class Eintrag(Zeitstempel):
    """Ein Kapitel, ein Ritual, ein Vorhaben – der Baustein jedes Dokuments."""

    dokument = models.ForeignKey(
        Dokument, verbose_name="Dokument", on_delete=models.CASCADE, related_name="eintraege"
    )
    eintragstyp = models.CharField(
        "Eintragstyp",
        max_length=60,
        choices=eintragstyp_auswahl,
        help_text="Bestimmt, welche Felder der Eintrag hat.",
    )
    kennung = models.CharField(
        "Kennung",
        max_length=40,
        help_text="Lesbare, dauerhafte Nummer, z. B. „R-01“, „V-3-01“ oder „2.4“.",
    )
    titel = models.CharField("Titel", max_length=300)
    eltern = models.ForeignKey(
        "self",
        verbose_name="übergeordneter Eintrag",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="kinder",
    )
    position = models.PositiveIntegerField("Position", default=0)
    status = models.CharField("Status", max_length=20, choices=Status, default=Status.ENTWURF)
    daten = models.JSONField("Daten", default=dict, blank=True)

    verantwortlich_gruppe = models.ForeignKey(
        Group,
        verbose_name="verantwortliche Arbeitsgruppe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verantwortlich_fuer",
    )
    verantwortlich_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="verantwortliche Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verantwortlich_fuer",
    )
    verantwortlich_text = models.CharField(
        "Verantwortlich (Freitext)",
        max_length=200,
        blank=True,
        help_text="Wird beim Import aus der Arbeitsmappe gefüllt, solange keine Gruppe passt.",
    )
    fassung_stand = models.DateField("Fassung / Stand", null=True, blank=True)

    suchtext = models.TextField("Suchtext", blank=True, editable=False)
    suchvektor = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = "Eintrag"
        verbose_name_plural = "Einträge"
        ordering = ["dokument", "position", "kennung"]
        constraints = [
            models.UniqueConstraint(
                fields=["dokument", "kennung"], name="eintrag_kennung_je_dokument"
            )
        ]
        indexes = [
            GinIndex(fields=["suchvektor"], name="eintrag_suchvektor"),
            models.Index(fields=["dokument", "eintragstyp"], name="eintrag_dokument_typ"),
            models.Index(fields=["status"], name="eintrag_status"),
        ]

    def __str__(self) -> str:
        return f"{self.kennung} {self.titel}".strip()

    def save(self, *args, **kwargs):
        if self._state.adding and self.dokument_id:
            with transaction.atomic():
                Dokument.objects.select_for_update().get(pk=self.dokument_id)
                if ReservierteKennung.objects.filter(
                    dokument_id=self.dokument_id, kennung=self.kennung
                ).exists():
                    raise ValidationError(
                        "Diese Kennung wurde gelöscht und bleibt dauerhaft reserviert."
                    )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def typ(self):
        """Das Schema dieses Eintrags aus der Registry.

        Ist der Typ unbekannt, kommt ein Platzhalter zurück statt eines
        Fehlers – ein einzelner kaputter Datensatz soll nicht das ganze
        Dokument unlesbar machen. ``typ_bekannt`` sagt, ob es ein echter ist.
        """
        from eintragstypen.registry import registry

        return registry.holen_oder_platzhalter(self.eintragstyp)

    @property
    def typ_bekannt(self) -> bool:
        from eintragstypen.registry import registry

        return registry.bekannt(self.eintragstyp)

    def clean(self) -> None:
        """Prüft den Eintragstyp, bevor etwas Unbrauchbares gespeichert wird.

        Eine Prüfung in der Datenbank wäre hier falsch: Eintragstypen stehen im
        Code, und jeder neue Typ bräuchte sonst eine Migration – genau das soll
        er nicht (Leitprinzip 3).
        """
        from eintragstypen.registry import registry

        super().clean()
        if not registry.bekannt(self.eintragstyp):
            bekannt = ", ".join(f"„{s}“" for s, _ in registry.auswahl()) or "(noch keine)"
            raise ValidationError(
                {
                    "eintragstyp": (
                        f"„{self.eintragstyp}“ ist kein Eintragstyp. Möglich sind: {bekannt}."
                    )
                }
            )

        if (
            self.dokument_id
            and ReservierteKennung.objects.filter(
                dokument_id=self.dokument_id, kennung=self.kennung
            ).exists()
        ):
            raise ValidationError(
                {"kennung": "Diese Kennung wurde gelöscht und bleibt reserviert."}
            )
        if not self.dokument_id:
            # Ohne Dokument hat Django schon einen Fehler dafür gemeldet.
            return

        erlaubt = self.dokument.dokumenttyp.eintragstypen or []
        if erlaubt and self.eintragstyp not in erlaubt:
            raise ValidationError(
                {
                    "eintragstyp": (
                        f"„{registry.holen(self.eintragstyp).name}“ ist im Dokumenttyp "
                        f"„{self.dokument.dokumenttyp.name}“ nicht vorgesehen."
                    )
                }
            )

    @property
    def ist_beschlossen(self) -> bool:
        return self.status == Status.BESCHLOSSEN

    @property
    def anzeige_nummer(self) -> str:
        """Nummer aus der Baumstellung – kann von ``kennung`` abweichen.

        ``kennung`` bleibt für immer gleich. Wird ein Kapitel verschoben, ändert
        sich nur die angezeigte Nummer. Einträge mit eigener Kennung wie „R-01“
        behalten diese auch als Anzeige.
        """
        if self.eintragstyp != "grundlagenkapitel":
            return self.kennung
        if not re.fullmatch(r"\d+(\.\d+)*", self.kennung):
            # Kapitel mit einer Kennung wie „A" (Anhang) werden nicht
            # mitgezählt – sie heißen so, wie sie heißen.
            return self.kennung
        kette = []
        knoten = self
        while knoten is not None:
            geschwister = list(
                knoten.dokument.eintraege.filter(
                    eltern=knoten.eltern, eintragstyp="grundlagenkapitel"
                ).order_by("position", "kennung")
            )
            stellen = [g.pk for g in geschwister]
            kette.append(str(stellen.index(knoten.pk) + 1) if knoten.pk in stellen else "?")
            knoten = knoten.eltern
        return ".".join(reversed(kette))

    @property
    def pfad(self) -> list[Eintrag]:
        """Die Kette der übergeordneten Einträge, von oben nach unten.

        Daraus baut die Suche den Kontext eines Treffers:
        „Arbeitsplan Deutsch › 2.1 Unterrichtsvorhaben › V-3-01“ (SPEC.md §9).
        """
        kette: list[Eintrag] = []
        knoten = self.eltern
        while knoten is not None and len(kette) < 10:
            kette.append(knoten)
            knoten = knoten.eltern
        return list(reversed(kette))

    @property
    def kontext(self) -> str:
        teile = [self.dokument.titel]
        teile += [f"{k.anzeige_nummer} {k.titel}" for k in self.pfad]
        return " › ".join(teile)

    def beschlossene_version(self):
        """Letzte durch einen Beschluss freigegebene Fassung – oder ``None``."""
        return (
            self.versionen.filter(status=Status.BESCHLOSSEN, beschluss__isnull=False)
            .order_by("-versionsnummer")
            .first()
        )

    def letzte_version(self):
        return self.versionen.order_by("-versionsnummer").first()

    def version_anlegen(self, autor=None) -> Eintragsversion:
        """Schreibt den aktuellen Stand als neue, unveränderliche Version fort."""
        letzte = self.letzte_version()
        return Eintragsversion.objects.create(
            eintrag=self,
            versionsnummer=(letzte.versionsnummer + 1) if letzte else 1,
            titel=self.titel,
            status=self.status,
            daten=self.daten,
            verlinkungen=[v.als_schnappschuss() for v in self.verlinkungen.all()],
            autor=autor,
        )


class Eintragsversion(models.Model):
    """Schnappschuss eines Eintrags. Beschlossene Versionen sind unveränderlich."""

    eintrag = models.ForeignKey(
        Eintrag, verbose_name="Eintrag", on_delete=models.CASCADE, related_name="versionen"
    )
    versionsnummer = models.PositiveIntegerField("Fassung")
    titel = models.CharField("Titel", max_length=300)
    status = models.CharField("Status", max_length=20, choices=Status)
    daten = models.JSONField("Daten", default=dict, blank=True)
    verlinkungen = models.JSONField("Verlinkungen", default=list, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Autor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    zeitpunkt = models.DateTimeField("Zeitpunkt", auto_now_add=True)
    beschluss = models.ForeignKey(
        "kern.Beschluss",
        verbose_name="Beschluss",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beschlossene_versionen",
    )

    class Meta:
        verbose_name = "Eintragsversion"
        verbose_name_plural = "Eintragsversionen"
        ordering = ["eintrag", "-versionsnummer"]
        constraints = [
            models.UniqueConstraint(
                fields=["eintrag", "versionsnummer"], name="version_nummer_je_eintrag"
            )
        ]

    def __str__(self) -> str:
        return f"{self.eintrag.kennung} – Fassung {self.versionsnummer}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            vorher = Eintragsversion.objects.filter(pk=self.pk).values("status").first()
            if vorher and vorher["status"] == Status.BESCHLOSSEN:
                # Nachvollziehbarkeit (SPEC.md §2.4): eine beschlossene Fassung
                # bleibt genau so, wie die Konferenz sie beschlossen hat.
                # Änderungen gehören in eine neue Fassung.
                raise ValidationError(
                    f"Fassung {self.versionsnummer} von {self.eintrag.kennung} ist beschlossen "
                    "und kann nicht geändert werden. Bearbeiten erzeugt eine neue Fassung."
                )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == Status.BESCHLOSSEN:
            raise ValidationError(
                f"Fassung {self.versionsnummer} von {self.eintrag.kennung} ist beschlossen "
                "und kann nicht gelöscht werden."
            )
        return super().delete(*args, **kwargs)


# --- Beschlüsse ------------------------------------------------------------


class Gremium(Zeitstempel):
    name = models.CharField("Name", max_length=120, unique=True)
    reihenfolge = models.PositiveIntegerField("Reihenfolge", default=100)

    class Meta:
        verbose_name = "Gremium"
        verbose_name_plural = "Gremien"
        ordering = ["reihenfolge", "name"]

    def __str__(self) -> str:
        return self.name


class Beschluss(Zeitstempel):
    """Macht ausgewählte Fassungen gültig (SPEC.md §8)."""

    datum = models.DateField("Datum")
    gremium = models.ForeignKey(
        Gremium, verbose_name="Gremium", on_delete=models.PROTECT, related_name="beschluesse"
    )
    titel = models.CharField("Titel", max_length=250)
    text = models.TextField("Beschlusstext", blank=True)
    protokoll_eintrag = models.ForeignKey(
        Eintrag,
        verbose_name="Protokoll (Eintrag)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="protokollierte_beschluesse",
    )
    protokoll_anhang = models.ForeignKey(
        "kern.Anhang",
        verbose_name="Protokoll (Anhang)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="protokollierte_beschluesse",
    )

    suchvektor = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = "Beschluss"
        verbose_name_plural = "Beschlüsse"
        ordering = ["-datum", "titel"]
        indexes = [GinIndex(fields=["suchvektor"], name="beschluss_suchvektor")]

    def __str__(self) -> str:
        return f"{self.gremium} vom {self.datum:%d.%m.%Y}: {self.titel}"

    def save(self, *args, **kwargs):
        ergebnis = super().save(*args, **kwargs)
        from kern.suchindex import beschluss_indexieren

        beschluss_indexieren(self)
        return ergebnis

    @property
    def herkunft(self) -> str:
        """Der Satz, der über jedem beschlossenen Eintrag steht (SPEC.md §8.5)."""
        return f"Gilt seit Beschluss der {self.gremium} vom {self.datum:%d.%m.%Y}"


# --- Verlinkung ------------------------------------------------------------


class Zieltyp(models.TextChoices):
    EINTRAG = "eintrag", "Eintrag"
    KOMPETENZ = "kompetenz", "Kompetenzerwartung"
    ANHANG = "anhang", "Anhang"
    BESCHLUSS = "beschluss", "Beschluss"
    NEXTCLOUD = "nextcloud", "Nextcloud-Datei"


class Verlinkungsart(models.TextChoices):
    VERWEIST_AUF = "verweist_auf", "verweist auf"
    NUTZT = "nutzt", "nutzt"
    ERSETZT = "ersetzt", "ersetzt"
    KOMPETENZ_SCHWERPUNKT = "kompetenz_schwerpunkt", "Kompetenz: Schwerpunkt"
    KOMPETENZ_BERUEHRT = "kompetenz_beruehrt", "Kompetenz: berührt"
    BEZUG_RITUAL = "bezug_ritual", "Bezug zu Ritual"


class Verlinkung(Zeitstempel):
    """Gerichtete Verbindung von einem Eintrag zu irgendetwas anderem.

    ``ziel_id`` ist absichtlich Text: Einträge und Anhänge haben Zahlen als
    Schlüssel, Kompetenzerwartungen aber Kennungen wie ``SC1.02S``.
    """

    von_eintrag = models.ForeignKey(
        Eintrag, verbose_name="von Eintrag", on_delete=models.CASCADE, related_name="verlinkungen"
    )
    ziel_typ = models.CharField("Zieltyp", max_length=20, choices=Zieltyp)
    ziel_id = models.CharField("Ziel", max_length=250)
    art = models.CharField("Art", max_length=40, choices=Verlinkungsart)
    feld = models.CharField(
        "Feld",
        max_length=60,
        blank=True,
        help_text="Aus welchem Feld der Verweis stammt – für die Anzeige am Feld.",
    )
    beschriftung = models.CharField("Beschriftung", max_length=250, blank=True)

    class Meta:
        verbose_name = "Verlinkung"
        verbose_name_plural = "Verlinkungen"
        ordering = ["von_eintrag", "art", "ziel_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["von_eintrag", "ziel_typ", "ziel_id", "art"], name="verlinkung_eindeutig"
            )
        ]
        indexes = [
            models.Index(fields=["ziel_typ", "ziel_id"], name="verlinkung_ziel"),
            models.Index(fields=["art"], name="verlinkung_art"),
        ]

    def __str__(self) -> str:
        return f"{self.von_eintrag.kennung} –{self.get_art_display()}→ {self.ziel_id}"

    def als_schnappschuss(self) -> dict:
        return {
            "ziel_typ": self.ziel_typ,
            "ziel_id": self.ziel_id,
            "art": self.art,
            "feld": self.feld,
            "beschriftung": self.beschriftung,
        }


# --- Anhänge ---------------------------------------------------------------


def anhang_pfad(anhang: Anhang, dateiname: str) -> str:
    return f"anhaenge/{timezone.now():%Y/%m}/{dateiname}"


class Anhang(Zeitstempel):
    """Hochgeladene Datei oder Verweis auf eine Datei in der Nextcloud."""

    dokument = models.ForeignKey(
        Dokument,
        verbose_name="Dokument",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="anhaenge",
    )
    eintrag = models.ForeignKey(
        Eintrag,
        verbose_name="Eintrag",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="anhaenge",
    )
    datei = models.FileField("Datei", upload_to=anhang_pfad, blank=True)
    nextcloud_pfad = models.CharField("Nextcloud-Pfad", max_length=500, blank=True)
    nextcloud_etag = models.CharField("Nextcloud-ETag", max_length=500, blank=True)
    nextcloud_geprueft_am = models.DateTimeField("Nextcloud geprüft am", null=True, blank=True)
    index_fehler = models.CharField("Indexierung: letzter Fehler", max_length=500, blank=True)
    nextcloud_link = models.URLField("Nextcloud-Link", max_length=500, blank=True)

    dateiname = models.CharField("Dateiname", max_length=300)
    mimetype = models.CharField("Dateityp", max_length=120, blank=True)
    groesse = models.BigIntegerField("Größe in Byte", null=True, blank=True)
    beschreibung = models.CharField("Beschreibung", max_length=300, blank=True)

    extrahierter_text = models.TextField("extrahierter Text", blank=True, editable=False)
    index_stand = models.DateTimeField("indexiert am", null=True, blank=True, editable=False)
    suchvektor = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = "Anhang"
        verbose_name_plural = "Anhänge"
        ordering = ["dateiname"]
        indexes = [GinIndex(fields=["suchvektor"], name="anhang_suchvektor")]

    def __str__(self) -> str:
        return self.dateiname

    def save(self, *args, **kwargs):
        ergebnis = super().save(*args, **kwargs)
        from kern.suchindex import anhang_indexieren

        anhang_indexieren(self)
        return ergebnis

    def clean(self) -> None:
        if not self.datei and not self.nextcloud_pfad and not self.nextcloud_link:
            raise ValidationError(
                "Ein Anhang braucht entweder eine hochgeladene Datei oder einen Nextcloud-Verweis."
            )


# --- Kommentare ------------------------------------------------------------


class Kommentar(Zeitstempel):
    eintrag = models.ForeignKey(
        Eintrag, verbose_name="Eintrag", on_delete=models.CASCADE, related_name="kommentare"
    )
    feld = models.CharField("Feld", max_length=60, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Autor",
        null=True,
        on_delete=models.SET_NULL,
        related_name="kommentare",
    )
    text = models.TextField("Kommentar")
    erledigt = models.BooleanField("erledigt", default=False)
    erledigt_am = models.DateTimeField("erledigt am", null=True, blank=True)
    erledigt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="erledigt von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "Kommentar"
        verbose_name_plural = "Kommentare"
        ordering = ["erledigt", "erstellt_am"]

    def __str__(self) -> str:
        return f"Kommentar zu {self.eintrag.kennung}"


# --- Persönliche Planung ---------------------------------------------------


class PersoenlicherFortschritt(Zeitstempel):
    """Abhaken und Notizen je Lehrkraft (SPEC.md §12 „Meine Planung“).

    ``klasse`` ist absichtlich Freitext wie „3b“ – die App bietet bewusst kein
    Feld an, das zu personenbezogenen Schülerdaten einlädt (SPEC.md §2.5).
    """

    nutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Nutzer",
        on_delete=models.CASCADE,
        related_name="fortschritt",
    )
    eintrag = models.ForeignKey(
        Eintrag, verbose_name="Eintrag", on_delete=models.CASCADE, related_name="fortschritt"
    )
    schuljahr = models.CharField("Schuljahr", max_length=12)
    klasse = models.CharField("Klasse", max_length=10, blank=True)
    erledigt = models.BooleanField("erledigt", default=False)
    erledigt_am = models.DateTimeField("erledigt am", null=True, blank=True)
    notiz = models.TextField("Notiz", blank=True)

    class Meta:
        verbose_name = "persönlicher Fortschritt"
        verbose_name_plural = "persönlicher Fortschritt"
        ordering = ["schuljahr", "klasse", "eintrag"]
        constraints = [
            models.UniqueConstraint(
                fields=["nutzer", "eintrag", "schuljahr", "klasse"], name="fortschritt_eindeutig"
            )
        ]

    def __str__(self) -> str:
        return f"{self.nutzer} – {self.eintrag.kennung} ({self.schuljahr})"


class OIDCIdentitaet(Zeitstempel):
    """Feste Zuordnung einer externen Identität zu einem bestehenden Schulkonto."""

    nutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oidc_identitaeten"
    )
    issuer = models.URLField("Anbieter (Issuer)", max_length=500)
    subject = models.CharField("Externe Kennung (sub)", max_length=255)

    class Meta:
        verbose_name = "Nextcloud-Anmeldung"
        verbose_name_plural = "Nextcloud-Anmeldungen"
        constraints = [
            models.UniqueConstraint(fields=["issuer", "subject"], name="oidc_identitaet_eindeutig"),
            models.UniqueConstraint(fields=["nutzer", "issuer"], name="oidc_konto_je_anbieter"),
        ]

    def __str__(self):
        return f"{self.nutzer} · {self.issuer}"
