import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kern", "0013_eintrag_aufgabe_eintrag_kurzantwort_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="NextcloudOrdner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("erstellt_am", models.DateTimeField(auto_now_add=True, verbose_name="erstellt am")),
                ("geaendert_am", models.DateTimeField(auto_now=True, verbose_name="geändert am")),
                ("name", models.CharField(max_length=200, verbose_name="Name")),
                ("pfad", models.CharField(
                    max_length=500, unique=True, verbose_name="Nextcloud-Ordnerpfad",
                    help_text="Relativ zum technischen Konto, z. B. Kollegium/Konzepte. Keine URL.",
                )),
                ("unterordner", models.BooleanField(default=True, verbose_name="Unterordner einbeziehen")),
                ("aktiv", models.BooleanField(default=True, verbose_name="Indexierung aktiv")),
                ("kollegiumsweit", models.BooleanField(
                    default=False, verbose_name="Für alle aktiven Schulkonten sichtbar",
                    help_text="Andernfalls sehen nur die ausgewählten Gruppen und die Administration die Dateien.",
                )),
                ("geprueft_am", models.DateTimeField(blank=True, null=True, verbose_name="Zuletzt geprüft")),
                ("index_stand", models.DateTimeField(blank=True, null=True, verbose_name="Ordner zuletzt vollständig eingelesen")),
                ("index_fehler", models.CharField(blank=True, max_length=500, verbose_name="Indexierungsfehler")),
                ("erstellt_von", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="erstellt von",
                )),
                ("gruppen", models.ManyToManyField(
                    blank=True, related_name="nextcloud_ordner", to="auth.group",
                    verbose_name="Berechtigte Gruppen",
                    help_text="Ohne Gruppen und ohne schulweite Freigabe sieht nur die Administration die Dateien.",
                )),
            ],
            options={
                "verbose_name": "Nextcloud-Suchordner",
                "verbose_name_plural": "Nextcloud-Suchordner",
                "ordering": ["name", "pk"],
            },
        ),
        migrations.AddField(
            model_name="anhang", name="nextcloud_ordner",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="dateien", to="kern.nextcloudordner", verbose_name="Nextcloud-Suchordner",
            ),
        ),
        migrations.AddField(
            model_name="anhang", name="nextcloud_verfuegbar",
            field=models.BooleanField(default=True, verbose_name="In Nextcloud verfügbar"),
        ),
        migrations.AddField(
            model_name="anhang", name="nextcloud_inventur_etag",
            field=models.CharField(blank=True, max_length=500, verbose_name="ETag der Ordnerinventur"),
        ),
        migrations.AddConstraint(
            model_name="anhang",
            constraint=models.UniqueConstraint(
                fields=("nextcloud_ordner", "nextcloud_pfad"),
                condition=models.Q(nextcloud_ordner__isnull=False),
                name="nextcloud_ordner_dateipfad",
            ),
        ),
    ]
