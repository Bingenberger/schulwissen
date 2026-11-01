"""Kompetenzbereiche als geordnete Liste statt als Objekt.

PostgreSQL speichert ``jsonb`` und sortiert die Schlüssel eines Objekts um.
Die Reihenfolge der Bereiche ist aber fachlich: Mathematik beginnt im Lehrplan
mit „Problemlösen“, nicht mit „Argumentieren“. Eine Liste bleibt geordnet.
"""

from django.db import migrations, models

from fachdaten.lehrplan import faecher


def zu_listen(apps, schema_editor):
    Fach = apps.get_model("fachdaten", "Fach")
    menge = Fach.objects.using(schema_editor.connection.alias)
    folge = {eintrag["schluessel"]: eintrag["bereiche"] for eintrag in faecher()}
    for fach in menge.all():
        if fach.schluessel in folge:
            fach.bereiche = folge[fach.schluessel]
        elif isinstance(fach.bereiche, dict):
            fach.bereiche = sorted([kuerzel, name] for kuerzel, name in fach.bereiche.items())
        else:
            continue
        fach.save(update_fields=["bereiche"])


def zu_objekten(apps, schema_editor):
    Fach = apps.get_model("fachdaten", "Fach")
    for fach in Fach.objects.using(schema_editor.connection.alias).all():
        if isinstance(fach.bereiche, list):
            fach.bereiche = {paar[0]: paar[1] for paar in fach.bereiche if len(paar) == 2}
            fach.save(update_fields=["bereiche"])


class Migration(migrations.Migration):
    dependencies = [("fachdaten", "0006_lehrplan_faecher")]
    operations = [
        migrations.AlterField(
            model_name="fach",
            name="bereiche",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Liste aus Kürzel und Name in der Reihenfolge des Lehrplans, "
                'z. B. [["ZA", "Zahlen"], ["RF", "Raum und Form"]]. '
                'Ein Objekt {"ZA": "Zahlen"} geht auch, wird dann aber alphabetisch sortiert.',
                verbose_name="Kompetenzbereiche",
            ),
        ),
        migrations.RunPython(zu_listen, zu_objekten),
    ]
