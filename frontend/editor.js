/*
 * Rich-Text-Editor der Schulwissen-Plattform.
 *
 * Hängt sich an jedes <textarea data-editor="richtext">, baut darüber eine
 * Werkzeugleiste und schreibt das Ergebnis beim Tippen in das Textfeld zurück.
 * Ohne JavaScript bleibt das Textfeld bedienbar – dann steht dort HTML.
 *
 * Erlaubt wird nur, was der Server in eintragstypen/html.py durchlässt:
 * Überschriften (h2–h4), Listen, einfache Tabellen, Fettung, Kursivierung,
 * Zitate und Links.
 *
 * Diese Datei wird mit „npm run build" zu ../dateien/vendor/editor.js
 * gebündelt. Das Ergebnis ist mitversioniert – für den Betrieb ist kein
 * npm nötig.
 */
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";

/** Die Werkzeugleiste: Beschriftung, Titel für Tastatur und Vorlesen, Aktion. */
const WERKZEUGE = [
  {
    beschriftung: "F",
    titel: "Fett (Strg+B)",
    stil: "font-weight:700",
    aktiv: "bold",
    tun: (e) => e.chain().focus().toggleBold().run(),
  },
  {
    beschriftung: "K",
    titel: "Kursiv (Strg+I)",
    stil: "font-style:italic",
    aktiv: "italic",
    tun: (e) => e.chain().focus().toggleItalic().run(),
  },
  { trenner: true },
  {
    beschriftung: "Ü1",
    titel: "Überschrift, große Ebene",
    aktiv: ["heading", { level: 2 }],
    tun: (e) => e.chain().focus().toggleHeading({ level: 2 }).run(),
  },
  {
    beschriftung: "Ü2",
    titel: "Überschrift, mittlere Ebene",
    aktiv: ["heading", { level: 3 }],
    tun: (e) => e.chain().focus().toggleHeading({ level: 3 }).run(),
  },
  { trenner: true },
  {
    beschriftung: "• Liste",
    titel: "Aufzählung",
    aktiv: "bulletList",
    tun: (e) => e.chain().focus().toggleBulletList().run(),
  },
  {
    beschriftung: "1. Liste",
    titel: "Nummerierte Liste",
    aktiv: "orderedList",
    tun: (e) => e.chain().focus().toggleOrderedList().run(),
  },
  { trenner: true },
  {
    beschriftung: "Tabelle",
    titel: "Tabelle mit 3 Spalten einfügen",
    tun: (e) =>
      e
        .chain()
        .focus()
        .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
        .run(),
  },
  {
    beschriftung: "+ Zeile",
    titel: "Zeile unten anfügen",
    nurInTabelle: true,
    tun: (e) => e.chain().focus().addRowAfter().run(),
  },
  {
    beschriftung: "+ Spalte",
    titel: "Spalte rechts anfügen",
    nurInTabelle: true,
    tun: (e) => e.chain().focus().addColumnAfter().run(),
  },
  {
    beschriftung: "Zeile löschen",
    titel: "Aktuelle Zeile löschen",
    nurInTabelle: true,
    tun: (e) => e.chain().focus().deleteRow().run(),
  },
  {
    beschriftung: "Spalte löschen",
    titel: "Aktuelle Spalte löschen",
    nurInTabelle: true,
    tun: (e) => e.chain().focus().deleteColumn().run(),
  },
  { trenner: true },
  {
    beschriftung: "Link",
    titel: "Link einfügen oder entfernen",
    aktiv: "link",
    tun: (editor) => {
      if (editor.isActive("link")) {
        editor.chain().focus().unsetLink().run();
        return;
      }
      const adresse = window.prompt("Adresse des Links (https://…)");
      if (!adresse) return;
      editor.chain().focus().setLink({ href: adresse }).run();
    },
  },
  {
    beschriftung: "Format entfernen",
    titel: "Auszeichnung der Auswahl entfernen",
    tun: (e) => e.chain().focus().unsetAllMarks().clearNodes().run(),
  },
];

function knopfBauen(werkzeug, editor) {
  if (werkzeug.trenner) {
    const trenner = document.createElement("span");
    trenner.className = "editor-trenner";
    trenner.setAttribute("aria-hidden", "true");
    return trenner;
  }
  const knopf = document.createElement("button");
  knopf.type = "button";
  knopf.className = "editor-knopf";
  knopf.textContent = werkzeug.beschriftung;
  knopf.title = werkzeug.titel;
  knopf.setAttribute("aria-label", werkzeug.titel);
  if (werkzeug.stil) knopf.setAttribute("style", werkzeug.stil);
  knopf.addEventListener("click", (ereignis) => {
    ereignis.preventDefault();
    werkzeug.tun(editor);
  });
  return knopf;
}

function editorAufbauen(textfeld) {
  if (textfeld.dataset.editorFertig === "ja") return;
  textfeld.dataset.editorFertig = "ja";

  const rahmen = document.createElement("div");
  rahmen.className = "editor";
  const leiste = document.createElement("div");
  leiste.className = "editor-leiste";
  leiste.setAttribute("role", "toolbar");
  leiste.setAttribute("aria-label", "Textformatierung");
  const flaeche = document.createElement("div");
  flaeche.className = "editor-flaeche";

  rahmen.append(leiste, flaeche);
  textfeld.parentNode.insertBefore(rahmen, textfeld);
  // Das Textfeld bleibt im Formular und trägt den Wert – nur unsichtbar.
  textfeld.classList.add("editor-quelle");
  textfeld.setAttribute("tabindex", "-1");
  textfeld.setAttribute("aria-hidden", "true");

  const editor = new Editor({
    element: flaeche,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        // Codeblöcke und waagerechte Linien braucht ein Arbeitsplan nicht.
        codeBlock: false,
        horizontalRule: false,
      }),
      Link.configure({ openOnClick: false, autolink: false }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: textfeld.value || "",
    onUpdate: ({ editor: aktuell }) => {
      const inhalt = aktuell.getHTML();
      // Leeren Absatz nicht als Inhalt zurückschreiben, sonst gilt ein leeres
      // Pflichtfeld als gefüllt.
      textfeld.value = inhalt === "<p></p>" ? "" : inhalt;
    },
  });

  const knoepfe = WERKZEUGE.map((werkzeug) => {
    const knopf = knopfBauen(werkzeug, editor);
    leiste.append(knopf);
    return { werkzeug, knopf };
  });

  function leisteAuffrischen() {
    const inTabelle = editor.isActive("table");
    knoepfe.forEach(({ werkzeug, knopf }) => {
      if (werkzeug.trenner) return;
      if (werkzeug.nurInTabelle) {
        knopf.hidden = !inTabelle;
      }
      if (werkzeug.aktiv) {
        const pruefung = Array.isArray(werkzeug.aktiv)
          ? editor.isActive(...werkzeug.aktiv)
          : editor.isActive(werkzeug.aktiv);
        knopf.classList.toggle("ist-aktiv", pruefung);
        knopf.setAttribute("aria-pressed", pruefung ? "true" : "false");
      }
    });
  }

  editor.on("selectionUpdate", leisteAuffrischen);
  editor.on("transaction", leisteAuffrischen);
  leisteAuffrischen();

  // Vor dem Abschicken sicherstellen, dass der letzte Stand im Feld steht.
  const formular = textfeld.closest("form");
  if (formular) {
    formular.addEventListener("submit", () => {
      const inhalt = editor.getHTML();
      textfeld.value = inhalt === "<p></p>" ? "" : inhalt;
    });
  }
}

function alleAufbauen(wurzel) {
  (wurzel || document)
    .querySelectorAll('textarea[data-editor="richtext"]')
    .forEach(editorAufbauen);
}

document.addEventListener("DOMContentLoaded", () => alleAufbauen(document));
// Nach dem Nachladen eines Formularteils per HTMX erneut aufbauen.
document.body &&
  document.body.addEventListener("htmx:afterSwap", (ereignis) =>
    alleAufbauen(ereignis.target),
  );

window.SchulwissenEditor = { alleAufbauen };
