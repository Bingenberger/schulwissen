/* Geführte Lektüre: Auswahl nur im Arbeitsspeicher, keine Verlaufsübertragung. */
(() => {
  'use strict';
  const root = document.querySelector('[data-prozess-leser]');
  if (!root || !document.getElementById('prozess-lesedaten')) return;
  const graph = JSON.parse(document.getElementById('prozess-lesedaten').textContent);
  const knoten = new Map(graph.knoten.map(k => [k.id, k]));
  const vorlagen = new Map([...root.querySelectorAll('[data-leseschritt]')].map(e => [e.dataset.leseschritt, e]));
  const starts = graph.knoten.filter(k => k.art === 'start');
  const start = starts.length === 1 ? starts[0].id : '';
  let aktuell = start, auswahl = '', weg = [], zoom = 1, svg = null;
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag); if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); return node;
  };
  const kopie = id => {
    const node = vorlagen.get(id)?.cloneNode(true);
    if (!node) return el('p', 'Dieser Schritt ist nicht vorhanden. Bitte frage die Redaktion.');
    node.removeAttribute('data-leseschritt'); node.querySelector('h4')?.remove();
    return node;
  };
  const inhalt = (target, id, folgen = false) => {
    const node = kopie(id);
    // Der statische Folgetext bleibt in der Textalternative; die Führung nutzt die gleichen Kanten.
    if (!folgen) {
      const marker = [...node.querySelectorAll('p')].find(p => p.textContent === 'Danach weiter');
      if (marker) { marker.nextElementSibling?.remove(); marker.remove(); }
    }
    target.replaceChildren(node);
  };
  function modus(wert, fokus = false) {
    for (const name of ['gefuehrt', 'grafik', 'text']) {
      root.querySelector(name === 'grafik' ? '[data-lesegrafik]' : name === 'text' ? '[data-lesetext]' : '[data-gefuehrt]').hidden = name !== wert;
      root.querySelector(`[data-modus="${name}"]`).setAttribute('aria-pressed', String(name === wert));
    }
    if (wert === 'gefuehrt') zeigen(fokus);
    if (wert === 'grafik') { zeichnen(); if (fokus) root.querySelector('[data-lesegrafik-rahmen]').focus(); }
    if (wert === 'text' && fokus) root.querySelector('[data-lesetext] h3').focus();
  }
  function zeigen(fokus = false) {
    const k = knoten.get(aktuell);
    const titel = root.querySelector('[data-gefuehrt-titel]');
    titel.textContent = k ? `Schritt ${k.nummer} · ${k.art_text}: ${k.titel || 'Titel noch offen'}` : 'Noch kein eindeutiger Start vorhanden';
    const panel = root.querySelector('[data-gefuehrt-inhalt]');
    if (k) inhalt(panel, k.id); else panel.replaceChildren(el('p', 'Bitte nutze die Textansicht und frage die Redaktion nach dem Start.'));
    const antworten = root.querySelector('[data-antworten]'); antworten.replaceChildren();
    for (const v of k?.folgen || []) {
      const ziel = knoten.get(v.nach);
      const b = el('button', `${v.ruecksprung ? '↩ Rücksprung · ' : ''}${v.beschriftung || 'Weiter'}${ziel ? ' → ' + ziel.titel : ' · Folgeschritt fehlt'}`, {type: 'button', class: 'knopf'});
      b.disabled = !ziel;
      b.addEventListener('click', () => {
        weg.push(aktuell); if (weg.length > 1000) weg.shift(); aktuell = v.nach; zeigen(true);
      }); antworten.append(b);
    }
    root.querySelector('[data-zurueck]').disabled = !weg.length;
    root.querySelector('[data-neustart]').disabled = !start;
    if (fokus) titel.focus();
  }
  function zeichnen() {
    const rahmen = root.querySelector('[data-lesegrafik-rahmen]');
    svg = window.SchulwissenGrafik.zeichnen(graph, {auswahl, prefix: 'lesen', aktion: 'ansehen', ziel: '#prozess-auswahl-titel', waehlen: id => {
      auswahl = id; zeichnen(); const k = knoten.get(id);
      const panel = root.querySelector('[data-grafik-auswahl]'); panel.hidden = false;
      const titel = root.querySelector('[data-auswahl-titel]'); titel.textContent = `Schritt ${k.nummer} · ${k.art_text}: ${k.titel || 'Titel noch offen'}`;
      inhalt(root.querySelector('[data-auswahl-inhalt]'), id, true); titel.focus();
    }});
    rahmen.replaceChildren(svg); skalieren();
  }
  function skalieren() {
    if (!svg) return;
    const box = svg.viewBox.baseVal; svg.style.width = `${box.width * zoom}px`; svg.style.height = `${box.height * zoom}px`;
  }
  root.querySelector('[data-lese-werkzeuge]').hidden = false;
  root.querySelector('[data-lesetext] h3').tabIndex = -1;
  root.querySelectorAll('[data-modus]').forEach(b => b.addEventListener('click', () => modus(b.dataset.modus, true)));
  root.querySelector('[data-zurueck]').addEventListener('click', () => { if (weg.length) { aktuell = weg.pop(); zeigen(true); } });
  root.querySelector('[data-neustart]').addEventListener('click', () => { weg = []; aktuell = start; root.querySelector('[data-verlaufstatus]').textContent = 'Neu begonnen. Deine bisherige Auswahl wurde verworfen.'; zeigen(true); });
  root.querySelector('[data-prozess-drucken]').addEventListener('click', () => window.print());
  root.querySelectorAll('[data-zoom]').forEach(b => b.addEventListener('click', () => { zoom = Math.max(0.3, Math.min(2.5, zoom * Number(b.dataset.zoom))); skalieren(); }));
  root.querySelector('[data-einpassen]').addEventListener('click', () => { zoom = Math.min(1, Math.max(0.3, (root.querySelector('[data-lesegrafik-rahmen]').clientWidth - 8) / svg.viewBox.baseVal.width)); skalieren(); });
  modus(start ? 'gefuehrt' : 'text'); root.dataset.bereit = 'true';
})();
