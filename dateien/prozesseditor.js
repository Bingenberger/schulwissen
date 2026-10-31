/* Prozesseditor: ein Graph, sichere DOM-Ausgabe und lokale SVG-Vorschau. */
(() => {
  'use strict';
  const ARTEN = {start: 'Start', handlung: 'Handlung', entscheidung: 'Entscheidung', ende: 'Ende'};
  const kopie = value => JSON.parse(JSON.stringify(value));
  const key = v => v.typ === 'eintrag' ? `eintrag:${v.dokument}:${v.kennung}` : `anhang:${v.id}`;
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    return node;
  };
  const button = (text, action, attrs = {}) => {
    const node = el('button', text, {type: 'button', class: 'knopf knopf-leise', ...attrs});
    node.addEventListener('click', action);
    return node;
  };

  class ProzessEditor {
    constructor(root) {
      this.root = root;
      this.input = root.querySelector('input[type=hidden]');
      this.form = root.closest('form');
      this.opts = JSON.parse(document.getElementById(root.dataset.optionen).textContent);
      this.labels = new Map((this.opts.ressourcen || []).map(x => [key(x.wert), x.label]));
      this.undo = [];
      this.sucheNummer = 0;
      this.pruefNummer = 0;
      this.auswahl = '';
      this.liste = root.querySelector('[data-schrittliste]');
      this.details = root.querySelector('[data-schritt-details]');
      this.vorschau = root.querySelector('[data-vorschau]');
      this.status = root.querySelector('[data-editor-status]');
      try {
        this.graph = JSON.parse(this.input.value);
        if (this.graph.schema_version !== 1 || !Array.isArray(this.graph.knoten) || !Array.isArray(this.graph.verbindungen)
            || this.graph.knoten.length > 200 || this.graph.verbindungen.length > 600
            || this.graph.knoten.some(k => !ARTEN[k.art] || typeof k.id !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(k.id))) throw Error();
      } catch (_) {
        root.querySelector('[data-pruefstatus]').textContent = 'Die Ablaufdaten sind nicht lesbar. Deine Eingabe bleibt erhalten. Bitte lade die letzte gespeicherte Fassung zum Vergleichen in einem neuen Tab.';
        root.querySelectorAll('button').forEach(b => b.disabled = true);
        return;
      }
      this.auswahl = this.graph.knoten[0]?.id || '';
      root.querySelector('[data-schritt-neu]').addEventListener('click', () => this.hinzufuegen());
      root.querySelector('[data-wiederherstellen]').addEventListener('click', () => this.wiederherstellen());
      root.querySelector('[data-pruefen]').addEventListener('click', () => this.pruefen());
      root.querySelector('[data-vorschau-zeigen]').addEventListener('click', () => { this.vorschau.focus(); this.vorschau.scrollIntoView({block: 'center'}); });
      this.form.addEventListener('input', e => {
        if (!e.target.closest('.prozess-pruefung') && e.target !== this.input) this.pruefungVeraltet();
      });
      this.rendern();
      if (this.opts.meldungen?.length) this.meldungen(this.opts.meldungen);
      root.dataset.bereit = 'true';
    }
    id(prefix) {
      let id;
      do {
        id = prefix + (globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`);
      } while ([...this.graph.knoten, ...this.graph.verbindungen].some(x => x.id === id));
      return id;
    }
    name(k) { return k.titel?.trim() || `${ARTEN[k.art]} – Titel ergänzen`; }
    get aktuell() { return this.graph.knoten.find(k => k.id === this.auswahl); }
    kanten(k) { return this.graph.verbindungen.filter(v => v.von === k.id); }
    neuKante(k, text = '') {
      if (this.graph.verbindungen.length >= 600) { this.status.textContent = 'Höchstens 600 Verbindungen sind möglich.'; return; }
      this.graph.verbindungen.push({id: this.id('v-'), von: k.id, nach: '', beschriftung: text, ruecksprung: false});
    }
    hinzufuegen() {
      if (this.graph.knoten.length >= 200) { this.status.textContent = 'Höchstens 200 Schritte sind möglich.'; return; }
      const art = this.root.querySelector('[data-neue-art]').value;
      const k = {id: this.id('s-'), art, titel: '', text: '', verweise: []};
      this.graph.knoten.push(k);
      if (art === 'entscheidung') { this.neuKante(k, 'Ja'); this.neuKante(k, 'Nein'); }
      else if (art !== 'ende') this.neuKante(k);
      this.auswahl = k.id;
      this.sync(); this.rendern(); this.focusTitel();
      this.status.textContent = `${ARTEN[art]} hinzugefügt.`;
    }
    sync() {
      this.input.value = JSON.stringify(this.graph);
      this.input.dispatchEvent(new Event('input', {bubbles: true}));
      this.pruefungVeraltet();
    }
    pruefungVeraltet() {
      this.pruefNummer++;
      const status = this.root.querySelector('[data-pruefstatus]');
      if (status.dataset.geprueft) {
        status.textContent = 'Seit der letzten Prüfung geändert. Prüfe den Ablauf erneut.';
        delete status.dataset.geprueft;
        this.root.querySelector('[data-pruefmeldungen]').replaceChildren();
      }
    }
    waehlen(id) {
      if (!this.graph.knoten.some(k => k.id === id)) return;
      this.auswahl = id;
      this.sucheNummer++;
      this.rendern(); this.focusTitel();
    }
    focusTitel() { (this.details.querySelector('[data-schritttitel]') || this.root.querySelector('[data-schritt-neu]'))?.focus(); }
    rendern() {
      this.renderListe(); this.renderDetails(); this.renderVerwaiste(); this.renderVorschau();
      this.root.querySelector('[data-wiederherstellen]').disabled = !this.undo.length;
    }
    renderVerwaiste() {
      const bereich = this.root.querySelector('[data-verwaiste-verbindungen]');
      bereich.replaceChildren();
      const ids = new Set(this.graph.knoten.map(k => k.id));
      const kanten = this.graph.verbindungen.filter(v => !ids.has(v.von));
      bereich.hidden = !kanten.length;
      if (!kanten.length) return;
      bereich.append(el('h4', 'Verbindungen ohne Ausgangsschritt'), el('p', 'Wähle einen Ausgangsschritt oder entferne die nicht mehr benötigte Verbindung.'));
      for (const v of kanten) {
        const nr = this.graph.verbindungen.indexOf(v) + 1;
        const zeile = el('div', null, {class: 'prozess-verbindung', 'data-verwaist-id': v.id});
        const auswahl = this.select([['', 'Ausgangsschritt wählen'], ...this.graph.knoten.map((k, i) => [k.id, `${i + 1}. ${this.name(k)}`])], '', value => {
          if (!value) return;
          v.von = value; this.auswahl = value; this.sync(); this.rendern(); this.focusTitel();
        });
        this.feld(`Ausgangsschritt für Verbindung ${nr}`, auswahl, zeile);
        if (v.beschriftung) zeile.append(el('p', `Beschriftung: ${v.beschriftung}`));
        zeile.append(button(`Verbindung ${nr} entfernen`, () => {
          this.graph.verbindungen = this.graph.verbindungen.filter(x => x.id !== v.id);
          this.sync(); this.rendern(); this.focusTitel();
        }));
        bereich.append(zeile);
      }
    }
    renderListe() {
      this.liste.replaceChildren();
      this.root.querySelector('[data-leer]').hidden = !!this.graph.knoten.length;
      this.graph.knoten.forEach((k, i) => {
        const b = button(`${i + 1}. ${this.name(k)}`, () => this.waehlen(k.id), {'data-schritt-id': k.id});
        if (k.id === this.auswahl) b.setAttribute('aria-current', 'step');
        b.prepend(el('span', ARTEN[k.art], {class: 'prozess-art'}));
        const li = el('li'); li.append(b); this.liste.append(li);
      });
    }
    feld(label, control, parent = this.details) {
      const id = `prozess-${this.auswahl}-${label.replace(/[^a-zA-Z]/g, '').toLowerCase()}-${this.feldNummer++}`;
      control.id = id;
      const wrap = el('div', null, {class: 'feld'});
      wrap.append(el('label', label, {for: id}), control); parent.append(wrap);
      return wrap;
    }
    select(values, value, change) {
      const s = el('select');
      for (const [v, text] of values) {
        const opt = el('option', text, {value: v}); opt.selected = v === value; s.append(opt);
      }
      s.addEventListener('change', () => change(s.value));
      return s;
    }
    aendern(callback) { callback(); this.sync(); this.renderListe(); this.renderVerwaiste(); this.renderVorschau(); }
    renderDetails() {
      this.feldNummer = 0;
      this.details.replaceChildren();
      const k = this.aktuell;
      if (!k) { this.details.append(el('p', 'Wähle einen Schritt oder füge einen neuen hinzu.')); return; }
      const nummer = this.graph.knoten.indexOf(k) + 1;
      this.details.append(el('h4', `Schritt ${nummer} bearbeiten`));
      this.feld('Schrittart', this.select(Object.entries(ARTEN), k.art, art => {
        k.art = art;
        const kanten = this.kanten(k);
        if (art === 'entscheidung' && kanten.length < 2) {
          if (!kanten.length) this.neuKante(k, 'Ja');
          else if (!kanten[0].beschriftung) kanten[0].beschriftung = 'Ja';
          this.neuKante(k, 'Nein');
        } else if (art !== 'ende' && !kanten.length) this.neuKante(k);
        this.sync(); this.rendern(); this.details.querySelector('select')?.focus();
      }));
      const titel = el('input', null, {type: 'text', maxlength: '200', 'data-schritttitel': ''}); titel.value = k.titel || '';
      titel.addEventListener('input', () => this.aendern(() => k.titel = titel.value));
      this.feld(k.art === 'entscheidung' ? 'Frage' : 'Schritttitel', titel);
      const text = el('textarea', null, {rows: '3', maxlength: '4000'}); text.value = k.text || '';
      text.addEventListener('input', () => this.aendern(() => k.text = text.value));
      this.feld('Erklärung', text);
      const rollen = [['', 'Noch keine Funktion gewählt'], ...(this.opts.funktionen || []).map(f => [f.schluessel, f.name])];
      if (k.art === 'handlung' && !this.opts.funktionen.length) this.details.append(el('p', 'Noch keine Schulfunktionen hinterlegt. Bitte lass die Administration die Funktionen einrichten. Du kannst zunächst als Entwurf speichern.', {class: 'meldung meldung-info'}));
      if (k.funktion && !rollen.some(([s]) => s === k.funktion)) rollen.push([k.funktion, 'Nicht mehr verfügbare Funktion – bitte neu wählen']);
      this.feld('Zuständige Funktion', this.select(rollen, k.funktion || '', value => {
        if (value) k.funktion = value; else { delete k.funktion; delete k.bereich; }
        this.sync(); this.renderDetails(); this.renderVorschau(); this.details.querySelectorAll('select')[1]?.focus();
      }));
      if (k.funktion) {
        const scope = [['', 'Allgemeine Zuständigkeit'], ...(this.opts.bereiche || []).map(b => [b.schluessel, b.name])];
        if (k.bereich && !scope.some(([s]) => s === k.bereich)) scope.push([k.bereich, 'Nicht mehr verfügbarer Bereich']);
        this.feld('Geltungsbereich', this.select(scope, k.bereich || '', value => {
          if (value) k.bereich = value; else delete k.bereich;
          this.sync(); this.renderDetails(); this.renderVorschau(); this.details.querySelectorAll('select')[2]?.focus();
        }));
        const f = this.opts.funktionen.find(f => f.schluessel === k.funktion);
        if (f?.aufgabe) this.details.append(el('p', f.aufgabe, {class: 'klein leise'}));
        this.details.append(el('p', f ? 'Aktuell: ' + (f.kontakte[k.bereich || ''] || 'Derzeit nicht besetzt') : 'Bitte wähle eine verfügbare Funktion.', {class: 'meldung meldung-info'}));
      }
      const folgen = el('fieldset', null, {class: 'prozess-folgen'});
      folgen.append(el('legend', k.art === 'entscheidung' ? 'Antwortzweige' : 'Danach weiter'));
      const kanten = this.kanten(k);
      for (const [index, v] of kanten.entries()) {
        const row = el('div', null, {class: 'prozess-verbindung', 'data-verbindung-id': v.id});
        const label = el('input', null, {type: 'text', maxlength: '200'}); label.value = v.beschriftung || '';
        label.addEventListener('input', () => this.aendern(() => v.beschriftung = label.value));
        this.feld(k.art === 'entscheidung' ? `Antwort ${index + 1}` : 'Beschriftung (bei Rücksprung erforderlich)', label, row);
        const ziele = [['', 'Folgeschritt wählen'], ...this.graph.knoten.map((ziel, i) => [ziel.id, `${i + 1}. ${this.name(ziel)}`])];
        if (v.nach && !ziele.some(([id]) => id === v.nach)) ziele.push([v.nach, 'Folgeschritt fehlt – bitte wählen']);
        this.feld(`Folgeschritt ${index + 1}`, this.select(ziele, v.nach || '', value => this.aendern(() => v.nach = value)), row);
        const box = el('input', null, {type: 'checkbox'}); box.checked = !!v.ruecksprung;
        box.addEventListener('change', () => this.aendern(() => v.ruecksprung = box.checked));
        const boxLabel = el('label', null, {class: 'prozess-checkbox'}); boxLabel.append(box, document.createTextNode(` Verbindung ${index + 1} als Rücksprung kennzeichnen`)); row.append(boxLabel);
        row.append(button('Verbindung entfernen', () => {
          this.graph.verbindungen = this.graph.verbindungen.filter(x => x.id !== v.id);
          this.sync(); this.rendern(); this.focusTitel();
        }));
        folgen.append(row);
      }
      folgen.append(button(k.art === 'entscheidung' ? 'Weitere Antwort hinzufügen' : 'Verbindung hinzufügen', () => {
        this.neuKante(k); this.sync(); this.rendern();
        this.details.querySelector('.prozess-verbindung:last-of-type input')?.focus();
      }));
      this.details.append(folgen);
      this.renderMaterial(k);
      const aktionen = el('div', null, {class: 'knopf-reihe prozess-schritt-aktionen'});
      for (const [delta, label] of [[-1, 'Schritt nach oben'], [1, 'Schritt nach unten']]) {
        const b = button(label, () => {
          const i = this.graph.knoten.indexOf(k); const j = i + delta;
          [this.graph.knoten[i], this.graph.knoten[j]] = [this.graph.knoten[j], this.graph.knoten[i]];
          this.sync(); this.rendern(); this.focusTitel();
        });
        b.disabled = nummer - 1 + delta < 0 || nummer - 1 + delta >= this.graph.knoten.length;
        aktionen.append(b);
      }
      aktionen.append(button('Schritt entfernen …', () => {
        const vorher = this.details.querySelector('[data-loeschfrage]'); if (vorher) { vorher.focus(); return; }
        const frage = el('div', null, {class: 'meldung meldung-warning', 'data-loeschfrage': '', tabindex: '-1'});
        frage.append(el('p', `„${this.name(k)}“ und die dazugehörigen Verbindungen entfernen?`));
        frage.append(button('Schritt jetzt entfernen', () => this.entfernen(k)), button('Schritt behalten', () => { frage.remove(); this.focusTitel(); }));
        this.details.append(frage); frage.focus();
      }));
      this.details.append(aktionen);
    }
    entfernen(k) {
      const index = this.graph.knoten.indexOf(k);
      this.undo.push({knoten: kopie(k), index, ids: this.graph.knoten.map(x => x.id), kanten: kopie(this.graph.verbindungen.filter(v => v.von === k.id || v.nach === k.id))});
      if (this.undo.length > 20) this.undo.shift();
      this.graph.knoten.splice(index, 1);
      this.graph.verbindungen = this.graph.verbindungen.filter(v => v.von !== k.id && v.nach !== k.id);
      this.auswahl = this.graph.knoten[Math.min(index, this.graph.knoten.length - 1)]?.id || '';
      this.sync(); this.rendern(); this.focusTitel();
      this.status.textContent = 'Schritt entfernt. Du kannst ihn wiederherstellen.';
    }
    wiederherstellen() {
      const alt = this.undo.pop(); if (!alt) return;
      if (this.graph.knoten.length >= 200) { this.undo.push(alt); this.status.textContent = 'Höchstens 200 Schritte sind möglich.'; return; }
      const ids = new Set([...this.graph.knoten.map(k => k.id), alt.knoten.id]);
      const kanten = alt.kanten.filter(v => (!alt.ids.includes(v.von) || ids.has(v.von)) && (!alt.ids.includes(v.nach) || ids.has(v.nach)));
      if (this.graph.verbindungen.length + kanten.length > 600) {
        this.undo.push(alt); this.status.textContent = 'Zum Wiederherstellen sind zu viele Verbindungen vorhanden.'; return;
      }
      this.graph.knoten.splice(Math.min(alt.index, this.graph.knoten.length), 0, alt.knoten);
      this.graph.verbindungen.push(...kanten);
      this.auswahl = alt.knoten.id; this.sync(); this.rendern(); this.focusTitel();
      this.status.textContent = 'Schritt wiederhergestellt. Andere Eingaben bleiben erhalten.';
    }
    renderMaterial(k) {
      const bereich = el('fieldset', null, {class: 'prozess-material'}); bereich.append(el('legend', 'Wissen und Materialien (optional)'));
      const liste = el('ul');
      for (const v of k.verweise || []) {
        const li = el('li', this.labels.get(key(v)) || (v.typ === 'eintrag' ? 'Verknüpfter Wissenseintrag' : 'Verknüpfte Datei'));
        li.append(button('Verweis entfernen', () => {
          k.verweise = k.verweise.filter(x => key(x) !== key(v));
          this.sync(); this.renderDetails();
        })); liste.append(li);
      }
      bereich.append(liste);
      const suchfeld = el('input', null, {type: 'search', maxlength: '150', placeholder: 'Mindestens zwei Zeichen'});
      this.feld('Wissen oder Datei suchen', suchfeld, bereich);
      const status = el('p', '', {role: 'status', class: 'klein leise'}); const treffer = el('ul', null, {class: 'liste-schlicht'});
      bereich.append(button('Material suchen', async () => {
        const begriff = suchfeld.value.trim();
        if (begriff.length < 2) { status.textContent = 'Gib mindestens zwei Zeichen ein.'; return; }
        if (!this.opts.ziele_url) { status.textContent = 'Die Suche ist hier nicht verfügbar.'; return; }
        const nummer = ++this.sucheNummer;
        status.textContent = 'Suche läuft …'; treffer.replaceChildren();
        try {
          const url = new URL(this.opts.ziele_url, location.href); url.searchParams.set('q', begriff);
          if (this.opts.kennung) url.searchParams.set('kennung', this.opts.kennung);
          const r = await fetch(url, {headers: {'Accept': 'application/json'}});
          if (!r.ok || r.redirected) throw Error();
          const daten = await r.json(); if (nummer !== this.sucheNummer || k.id !== this.auswahl) return;
          status.textContent = daten.treffer.length ? 'Wähle einen Treffer zum Verknüpfen.' : 'Keine erlaubten passenden Ziele gefunden.';
          for (const t of daten.treffer) {
            const li = el('li'); li.append(button(t.label, () => {
              k.verweise ||= [];
              if (k.verweise.length >= 20) { status.textContent = 'Höchstens 20 Verweise je Schritt sind möglich.'; return; }
              if (!k.verweise.some(v => key(v) === key(t.wert))) k.verweise.push(t.wert);
              this.labels.set(key(t.wert), t.label); this.sync(); this.renderDetails();
              this.status.textContent = 'Verweis hinzugefügt.';
            })); treffer.append(li);
          }
        } catch (_) { if (nummer === this.sucheNummer) status.textContent = 'Die Suche ist gerade nicht möglich. Deine Eingaben bleiben erhalten.'; }
      }));
      suchfeld.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); bereich.querySelectorAll('button')[k.verweise?.length || 0]?.click(); } });
      bereich.append(status, treffer); this.details.append(bereich);
    }
    async pruefen() {
      if (!this.opts.pruefen_url) { this.root.querySelector('[data-pruefstatus]').textContent = 'Die Prüfung ist hier nicht verfügbar.'; return; }
      const nummer = ++this.pruefNummer;
      const knopf = this.root.querySelector('[data-pruefen]'); knopf.disabled = true;
      this.root.querySelector('[data-pruefstatus]').textContent = 'Der Ablauf wird geprüft …';
      this.root.querySelector('[data-pruefstatus]').dataset.geprueft = 'true';
      try {
        const daten = new FormData(this.form); if (this.opts.kennung) daten.set('kennung', this.opts.kennung);
        const r = await fetch(this.opts.pruefen_url, {method: 'POST', body: daten, headers: {'Accept': 'application/json'}});
        if (!r.ok || r.redirected) throw Error();
        const auskunft = await r.json(); if (nummer !== this.pruefNummer) return;
        this.meldungen(auskunft.meldungen);
        if (auskunft.ok) this.root.querySelector('[data-pruefstatus]').textContent = 'Die Prüfung ist vollständig. Der Ablauf kann fachlich abgestimmt werden; beschlossen wird er erst durch eine Freigabe.';
      } catch (_) { if (nummer === this.pruefNummer) this.root.querySelector('[data-pruefstatus]').textContent = 'Die Prüfung ist gerade nicht möglich. Deine Eingaben bleiben erhalten.'; }
      finally { knopf.disabled = false; }
    }
    meldungen(meldungen) {
      const status = this.root.querySelector('[data-pruefstatus]'); status.dataset.geprueft = 'true';
      status.textContent = meldungen.length ? `${meldungen.length} Hinweise: Du kannst den Ablauf weiter als Entwurf speichern.` : 'Keine Hindernisse gefunden.';
      const liste = this.root.querySelector('[data-pruefmeldungen]'); liste.replaceChildren();
      for (const m of meldungen) {
        const li = el('li');
        if (m.schritt && this.graph.knoten.some(k => k.id === m.schritt)) li.append(button(m.text, () => this.waehlen(m.schritt)));
        else if (m.verbindung && this.graph.verbindungen.some(v => v.id === m.verbindung)) li.append(button(m.text, () => {
          const row = [...this.root.querySelectorAll('[data-verwaist-id]')].find(r => r.dataset.verwaistId === m.verbindung);
          (row?.querySelector('select') || this.root.querySelector('[data-schritt-neu]'))?.focus();
        }));
        else li.append(el('span', m.text));
        liste.append(li);
      }
    }
    renderVorschau() {
      const knoten = this.graph.knoten;
      const svg = window.SchulwissenGrafik.zeichnen(this.graph, {auswahl: this.auswahl, prefix: 'editor', waehlen: id => this.waehlen(id)});
      this.vorschau.replaceChildren(svg);
      const alternativ = this.root.querySelector('[data-textvorschau]'); alternativ.replaceChildren();
      if (!knoten.length) alternativ.append(el('p', 'Noch keine Schritte.'));
      for (const k of knoten) {
        alternativ.append(el('h5', `${ARTEN[k.art]}: ${this.name(k)}`));
        if (k.text) alternativ.append(el('p', k.text));
        const liste = el('ul');
        for (const v of this.kanten(k)) {
          const ziel = knoten.find(z => z.id === v.nach);
          liste.append(el('li', `${v.ruecksprung ? 'Rücksprung: ' : ''}${v.beschriftung || 'Weiter'} → ${ziel ? this.name(ziel) : 'Folgeschritt fehlt'}`));
        }
        alternativ.append(liste);
      }
    }
  }
  document.querySelectorAll('[data-prozess-editor]').forEach(root => new ProzessEditor(root));
})();
