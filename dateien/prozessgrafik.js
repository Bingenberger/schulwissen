/* Gemeinsame native SVG-Zeichnung für Autoren und Lesende. */
(() => {
  'use strict';
  const ARTEN = {start:'Start', handlung:'Handlung', entscheidung:'Entscheidung', ende:'Ende'};
  const svgEl = (tag, attrs = {}, text) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  window.SchulwissenGrafik = {zeichnen(graph, {auswahl='', prefix='prozess', aktion='bearbeiten', ziel='#prozess-editor-titel', waehlen=()=>{}} = {}) {
    const name = k => k.titel?.trim() || `${ARTEN[k.art]} – Titel ergänzen`;
      const knoten = graph.knoten;
      const ids = new Set(knoten.map(k => k.id));
      const kanten = graph.verbindungen.filter(v => ids.has(v.von) && ids.has(v.nach));
      const grad = new Map(knoten.map(k => [k.id, 0])); const nachbarn = new Map(knoten.map(k => [k.id, []]));
      for (const v of kanten) if (!v.ruecksprung) { grad.set(v.nach, grad.get(v.nach) + 1); nachbarn.get(v.von).push(v.nach); }
      const offen = knoten.filter(k => !grad.get(k.id)).map(k => k.id); const rang = new Map(knoten.map(k => [k.id, 0])); const gesehen = new Set();
      for (let i = 0; i < offen.length; i++) {
        const id = offen[i]; gesehen.add(id);
        for (const ziel of nachbarn.get(id)) { rang.set(ziel, Math.max(rang.get(ziel), rang.get(id) + 1)); grad.set(ziel, grad.get(ziel) - 1); if (!grad.get(ziel)) offen.push(ziel); }
      }
      // Auch unvollständige Kreise zeichnen, ohne sie automatisch zu durchlaufen.
      let extra = Math.max(0, ...rang.values());
      for (const k of knoten) if (!gesehen.has(k.id)) rang.set(k.id, ++extra);
      const gruppen = new Map();
      for (const k of knoten) { const r = rang.get(k.id); if (!gruppen.has(r)) gruppen.set(r, []); gruppen.get(r).push(k); }
      const spalten = Math.max(1, ...Array.from(gruppen.values(), g => g.length));
      const breite = spalten * 270 + 170; const hoehe = (Math.max(0, ...rang.values()) + 1) * 190 + 40;
      const pos = new Map();
      for (const [r, gruppe] of gruppen) gruppe.forEach((k, i) => pos.set(k.id, {x: 135 + i * 270 + (spalten - gruppe.length) * 135, y: 80 + r * 190}));
      const svg = svgEl('svg', {viewBox: `0 0 ${breite} ${hoehe}`, width: breite, height: hoehe, role: 'group', 'aria-label': 'Automatische Ablaufvorschau'});
      const defs = svgEl('defs'); const marker = svgEl('marker', {id: prefix + '-pfeil', markerWidth: 10, markerHeight: 10, refX: 8, refY: 3, orient: 'auto', markerUnits: 'strokeWidth'});
      marker.append(svgEl('path', {d: 'M0,0 L0,6 L9,3 z', class: 'prozess-pfeil'})); defs.append(marker); svg.append(defs);
      const text = (x, y, wert, klasse, max = 28, zeilen = 3) => {
        const t = svgEl('text', {x, y, 'text-anchor': 'middle', class: klasse});
        const woerter = String(wert).match(new RegExp(`.{1,${max}}(?:\\s|$)|.{1,${max}}`, 'g')) || [''];
        for (const [i, zeile] of woerter.slice(0, zeilen).entries()) t.append(svgEl('tspan', {x, dy: i ? '19' : '0'}, zeile.trim() + (i === zeilen - 1 && woerter.length > zeilen ? '…' : '') + ' '));
        return t;
      };
      for (const [index, v] of kanten.entries()) {
        const a = pos.get(v.von), b = pos.get(v.nach); const rueck = v.ruecksprung || b.y <= a.y;
        let d, lx, ly;
        if (rueck) {
          const seite = breite - 70 + (index % 3) * 15;
          d = `M${a.x + 112},${a.y} C${seite},${a.y + 65} ${seite},${b.y - 65} ${b.x + 112},${b.y}`;
          lx = seite - 50; ly = (a.y + b.y) / 2 - 25;
        } else {
          d = `M${a.x},${a.y + 53} C${a.x},${a.y + 105} ${b.x},${b.y - 105} ${b.x},${b.y - 53}`;
          lx = (a.x + b.x) / 2; ly = (a.y + b.y) / 2 - 2;
        }
        svg.append(svgEl('path', {d, class: 'prozess-kante' + (rueck ? ' ist-ruecksprung' : ''), 'marker-end': `url(#${prefix}-pfeil)`}));
        if (v.beschriftung || rueck) svg.append(text(lx, Math.max(18, ly), (v.ruecksprung ? '↩ ' : '') + (v.beschriftung || 'Weiter'), 'prozess-kantenlabel', 19));
      }
      for (const [index, k] of knoten.entries()) {
        const p = pos.get(k.id); const a = svgEl('a', {href: ziel, 'aria-labelledby': `${prefix}-grafik-${k.id}-art ${prefix}-grafik-${k.id}-titel`, 'aria-describedby': `${prefix}-grafik-${k.id}-beschreibung`, 'data-vorschau-schritt': k.id, class: 'prozess-knoten' + (k.id === auswahl ? ' ist-gewaehlt' : '')});
        if (k.id === auswahl) a.setAttribute('aria-current', 'step');
        a.addEventListener('click', e => { e.preventDefault(); waehlen(k.id); });
        a.append(svgEl('desc', {id: `${prefix}-grafik-${k.id}-beschreibung`}, `Schritt ${index + 1} ${aktion}: ${name(k)}`));
        a.append(k.art === 'entscheidung' ? svgEl('polygon', {points: `${p.x},${p.y - 56} ${p.x + 116},${p.y} ${p.x},${p.y + 56} ${p.x - 116},${p.y}`})
          : svgEl('rect', {x: p.x - 112, y: p.y - 53, width: 224, height: 106, rx: k.art === 'start' || k.art === 'ende' ? 34 : 8}));
        const artText = text(p.x, p.y - 25, ARTEN[k.art], 'prozess-svg-art'); artText.id = `${prefix}-grafik-${k.id}-art`; a.append(artText);
        const titelText = text(p.x, p.y - 2, name(k), 'prozess-svg-titel', k.art === 'entscheidung' ? 17 : 27, k.art === 'entscheidung' ? 2 : 3); titelText.id = `${prefix}-grafik-${k.id}-titel`; a.append(titelText);
        svg.append(a);
      }
      return svg;
  }};
})();
