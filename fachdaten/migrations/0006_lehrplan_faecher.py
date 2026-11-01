"""Die neun Fächer des Sammelbands mit Bereichen – und Praktische Philosophie.

Die Namen und Bereichskürzel stehen in ``lehrplan/faecher.json``; diese
Migration schreibt sie in die Tabelle. Vorhandene Fächer werden ergänzt, nicht
ersetzt: ``bereiche`` und ``quelle`` kommen aus dem Lehrplan, der Name wird auf
die amtliche Fassung gesetzt („Katholische Religionslehre“ statt „Religion
katholisch“).
"""

from django.db import migrations

from fachdaten.lehrplan import faecher


def anlegen(apps, schema_editor):
    Fach = apps.get_model("fachdaten", "Fach")
    menge = Fach.objects.using(schema_editor.connection.alias)
    for eintrag in faecher():
        fach = menge.filter(schluessel=eintrag["schluessel"]).first()
        if fach is None:
            # Ein gleichnamiges Fach mit anderem Schlüssel darf es nicht geben.
            menge.filter(name=eintrag["name"]).update(name=f"{eintrag['name']} (alt)")
            menge.create(
                schluessel=eintrag["schluessel"],
                name=eintrag["name"],
                bereiche=eintrag["bereiche"],
                quelle=eintrag["quelle"],
            )
            continue
        fach.name = eintrag["name"]
        fach.bereiche = eintrag["bereiche"]
        fach.quelle = eintrag["quelle"]
        fach.save(update_fields=["name", "bereiche", "quelle"])


class Migration(migrations.Migration):
    dependencies = [("fachdaten", "0005_faecher")]
    operations = [migrations.RunPython(anlegen, migrations.RunPython.noop)]
