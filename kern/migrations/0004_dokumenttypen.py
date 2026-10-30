from django.db import migrations


def anlegen(apps, schema_editor):
    typ = apps.get_model("kern", "Dokumenttyp")
    for schluessel, name, eintragstypen in (
        ("konzept", "Konzept", ["grundlagenkapitel"]),
        ("protokoll", "Konferenzprotokoll", ["protokollkopf", "tagesordnungspunkt"]),
    ):
        typ.objects.using(schema_editor.connection.alias).get_or_create(
            schluessel=schluessel, defaults={"name": name, "eintragstypen": eintragstypen}
        )


class Migration(migrations.Migration):
    dependencies = [("kern", "0003_alter_eintrag_eintragstyp")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
