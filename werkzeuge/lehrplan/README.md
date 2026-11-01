# Lehrplan-Sammelband einlesen

Diese drei Dateien haben die Dateien in `lehrplan/` erzeugt. Sie laufen
**einmalig**, nicht im Betrieb: die App liest die fertigen JSON-Dateien.

Sie liegen hier, damit der Datenbestand nachvollziehbar und wiederholbar
bleibt – wer an einer Kompetenzerwartung zweifelt, kann die Stelle im PDF
nachschlagen und den Lauf wiederholen.

| Datei | Aufgabe |
| --- | --- |
| `lesen.py` | Tabellen eines Fachs aus dem PDF lesen (Bereich, Schwerpunkt, Spalte) |
| `englisch.py` | Englisch, das ohne Tabellen gesetzt ist |
| `bauen.py` | Kennungen, Stufen, Klammerzusätze und die Dateien je Fach |

## Lauf

`pdfplumber` ist **keine** Abhängigkeit der App – die Werkzeuge bekommen eine
eigene Umgebung:

```bash
uv venv --python 3.12 /tmp/lehrplanumgebung
uv pip install --python /tmp/lehrplanumgebung/bin/python pdfplumber
/tmp/lehrplanumgebung/bin/python werkzeuge/lehrplan/bauen.py lehrplan
```

Erwartet wird `ps_lp_sammelband_2025_03_18_0.pdf` im Projektverzeichnis.
Der Lauf meldet, welche Deutsch-Angaben er gegenüber dem vorhandenen Datensatz
berichtigt; die Kennungen bleiben dabei unverändert.

Wie die Stufen aus den Zellrahmen des PDF gelesen werden und welche
Besonderheiten Englisch, Kunst, Musik und Mathematik haben, steht in
[docs/KOMPETENZDATEN.md](../../docs/KOMPETENZDATEN.md).
