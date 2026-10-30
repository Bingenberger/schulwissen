from django.db import migrations


def anlegen(apps, schema_editor):
    apps.get_model("kern", "Dokumenttyp").objects.using(
        schema_editor.connection.alias
    ).get_or_create(
        schluessel="arbeitsplan",
        defaults={
            "name": "Arbeitsplan",
            "eintragstypen": ["grundlagenkapitel", "ritual", "vorhaben"],
        },
    )


class Migration(migrations.Migration):
    dependencies = [("kern", "0005_anhang_index_fehler_anhang_nextcloud_etag_and_more")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
