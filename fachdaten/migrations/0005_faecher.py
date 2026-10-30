from django.db import migrations


def anlegen(apps, schema_editor):
    fach = apps.get_model("fachdaten", "Fach")
    namen = {
        "deutsch": "Deutsch",
        "mathematik": "Mathematik",
        "sport": "Sport",
        "kunst": "Kunst",
        "musik": "Musik",
        "religion-katholisch": "Religion katholisch",
        "religion-evangelisch": "Religion evangelisch",
        "sachunterricht": "Sachunterricht",
        "englisch": "Englisch",
    }
    for schluessel, name in namen.items():
        fach.objects.using(schema_editor.connection.alias).get_or_create(
            schluessel=schluessel,
            defaults={
                "name": name,
                "bereiche": {
                    "SZ": "Sprechen und Zuhören",
                    "SC": "Schreiben",
                    "LE": "Lesen – mit Texten und Medien umgehen",
                    "SP": "Sprache und Sprachgebrauch untersuchen",
                }
                if schluessel == "deutsch"
                else {},
            },
        )


class Migration(migrations.Migration):
    dependencies = [("fachdaten", "0004_alter_kompetenzerwartung_bereich_fach")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
