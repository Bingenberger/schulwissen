"""URL-Zuordnung des Kerns."""

from django.contrib.auth import views as auth_views
from django.urls import path

from kern import (
    anhaenge,
    arbeitsablauf,
    beschluss_views,
    dateifassungen,
    dokument_views,
    export_views,
    funktionen,
    gestaltung,
    handbuch,
    import_views,
    oidc,
    planung,
    prozesse,
    prozesseditor,
    prozesslesen,
    uebersichten,
    views,
    wissenspflege,
)

app_name = "kern"

urlpatterns = [
    path("handbuch", handbuch.verzeichnis, name="handbuch"),
    path("formulare", handbuch.formulare, name="formulare"),
    path("wissenspflege", wissenspflege.uebersicht, name="wissenspflege"),
    path("dateifassung/<int:pk>", dateifassungen.download, name="dateifassung"),
    path(
        "d/<slug:schluessel>/<str:kennung>/pflege",
        wissenspflege.bearbeiten,
        name="wissenspflege_bearbeiten",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/anlage/<int:pk>",
        wissenspflege.anlage,
        name="anlage_pflegen",
    ),
    path("prozesse", prozesse.verzeichnis, name="prozesse"),
    path(
        "d/<slug:schluessel>/<str:kennung>/freigeben", prozesse.freigeben, name="prozess_freigeben"
    ),
    path("d/<slug:schluessel>/<str:kennung>/prozess.pdf", prozesslesen.pdf, name="prozess_pdf"),
    path("d/<slug:schluessel>/prozess-pruefen", prozesseditor.pruefen, name="prozess_pruefen"),
    path("d/<slug:schluessel>/prozess-ziele", prozesseditor.ziele, name="prozess_ziele"),
    path("funktionen", funktionen.verzeichnis, name="funktionen"),
    path("funktionen/<slug:schluessel>", funktionen.detail, name="funktion"),
    path("medien/<path:pfad>", views.anhang_datei, name="anhang_datei"),
    path("anhang/<int:pk>/vorschau", anhaenge.vorschau, name="anhang_vorschau"),
    path(
        "d/<slug:schluessel>/<str:kennung>/anhang/<int:pk>/loeschen",
        anhaenge.loeschen,
        name="anhang_loeschen",
    ),
    path(
        "d/<slug:schluessel>/anhangauswahl/vorschau",
        anhaenge.nextcloud_vorschau,
        name="nextcloud_vorschau",
    ),
    path("", views.startseite, name="startseite"),
    path("dokumente", uebersichten.dokumente, name="dokumente"),
    path("meine-entwuerfe", uebersichten.eigene_entwuerfe, name="eigene_entwuerfe"),
    path(
        "d/<slug:schluessel>/protokoll-beschliessen",
        arbeitsablauf.protokoll_beschliessen,
        name="protokoll_beschliessen",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/loeschen",
        arbeitsablauf.eintrag_loeschen,
        name="eintrag_loeschen",
    ),
    path("styleguide", gestaltung.styleguide, name="styleguide"),
    path("anmelden/nextcloud", oidc.anmelden, name="oidc_anmelden"),
    path("anmelden/nextcloud/callback", oidc.callback, name="oidc_callback"),
    path("konto/nextcloud-verbinden", oidc.verbinden, name="oidc_verbinden"),
    path("meine-planung", planung.planung, name="planung"),
    path("dokument-neu", dokument_views.dokument_neu, name="dokument_neu"),
    path("d/<slug:schluessel>/export/<str:format>", export_views.export, name="export"),
    path("d/<slug:schluessel>/import", import_views.json_import, name="json_import"),
    path("beschluesse/vorlage.pdf", export_views.vorlage_pdf, name="vorlage_pdf"),
    path("gesundheit", views.gesundheit, name="gesundheit"),
    # --- Anmeldung ---
    path(
        "anmelden",
        auth_views.LoginView.as_view(
            template_name="kern/anmelden.html", redirect_authenticated_user=True
        ),
        name="anmelden",
    ),
    path("abmelden", auth_views.LogoutView.as_view(), name="abmelden"),
    path(
        "passwort-vergessen",
        auth_views.PasswordResetView.as_view(
            template_name="kern/passwort_vergessen.html",
            email_template_name="kern/passwort_vergessen_mail.txt",
            subject_template_name="kern/passwort_vergessen_betreff.txt",
            success_url="/passwort-vergessen/gesendet",
        ),
        name="passwort_zuruecksetzen",
    ),
    path(
        "passwort-vergessen/gesendet",
        auth_views.PasswordResetDoneView.as_view(template_name="kern/passwort_gesendet.html"),
        name="password_reset_done",
    ),
    path(
        "passwort-neu/<uidb64>/<token>",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="kern/passwort_neu.html", success_url="/passwort-neu/fertig"
        ),
        name="password_reset_confirm",
    ),
    path(
        "passwort-neu/fertig",
        auth_views.PasswordResetCompleteView.as_view(template_name="kern/passwort_fertig.html"),
        name="password_reset_complete",
    ),
    path(
        "passwort-aendern",
        auth_views.PasswordChangeView.as_view(
            template_name="kern/passwort_aendern.html", success_url="/"
        ),
        name="passwort_aendern",
    ),
    # --- Dokumente und Einträge ---
    path("d/<slug:schluessel>", views.dokument_ansehen, name="dokument"),
    path("d/<slug:schluessel>/neu/<str:eintragstyp>", views.eintrag_neu, name="eintrag_neu"),
    path(
        "d/<slug:schluessel>/anhangauswahl/nextcloud",
        views.nextcloud_erfassung,
        name="nextcloud_erfassung",
    ),
    # Diese feste Route muss vor „<str:kennung>" stehen, sonst gilt
    # „aenderungen" als Kennung eines Eintrags.
    path("d/<slug:schluessel>/aenderungen", beschluss_views.aenderungen, name="aenderungen"),
    path("d/<slug:schluessel>/<str:kennung>", views.eintrag_ansehen, name="eintrag"),
    path(
        "d/<slug:schluessel>/<str:kennung>/bearbeiten",
        views.eintrag_bearbeiten,
        name="eintrag_bearbeiten",
    ),
    path("d/<slug:schluessel>/<str:kennung>/fassungen", views.fassungen, name="fassungen"),
    path(
        "d/<slug:schluessel>/<str:kennung>/kommentar",
        views.kommentar_anlegen,
        name="kommentar_anlegen",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/kommentar/<int:kommentar_id>/erledigt",
        views.kommentar_erledigen,
        name="kommentar_erledigen",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/anhang",
        views.anhang_hochladen,
        name="anhang_hochladen",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/nextcloud",
        views.nextcloud_waehlen,
        name="nextcloud_waehlen",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/nextcloud/verlinken",
        views.nextcloud_verlinken,
        name="nextcloud_verlinken",
    ),
    # --- Fassungen und Vergleich ---
    path(
        "d/<slug:schluessel>/<str:kennung>/vergleich",
        beschluss_views.fassungen_vergleichen,
        name="vergleich",
    ),
    path(
        "d/<slug:schluessel>/<str:kennung>/fassung/<int:nummer>",
        beschluss_views.version_ansehen,
        name="version",
    ),
    # --- Beschlüsse ---
    path("beschluesse", beschluss_views.beschluesse_liste, name="beschluesse"),
    path("beschluesse/neu", beschluss_views.beschluss_anlegen, name="beschluss_anlegen"),
    path("beschluesse/vorlage", beschluss_views.beschlussvorlage, name="beschlussvorlage"),
    path(
        "beschluesse/vorlage/<slug:schluessel>",
        beschluss_views.beschlussvorlage,
        name="beschlussvorlage_dokument",
    ),
    path("beschluesse/<int:beschluss_id>", beschluss_views.beschluss_ansehen, name="beschluss"),
    path(
        "beschluesse/<int:beschluss_id>/zuruecknehmen",
        beschluss_views.beschluss_zuruecknehmen,
        name="beschluss_zuruecknehmen",
    ),
]
