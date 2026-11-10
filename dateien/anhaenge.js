/* Dateivorschau, Nextcloud-Dialog und noch nicht gespeicherte Dateiauswahl. */
(() => {
  const fenster = document.getElementById('dateivorschau');
  const dialog = document.getElementById('nextcloud-dialog');
  if (!fenster || !dialog) return;
  const rahmen = fenster.querySelector('iframe');
  const original = fenster.querySelector('[data-vorschau-original]');
  const kannPopover = typeof fenster.showPopover === 'function';
  let timer, schliessenTimer, fest = false, ausloeser;
  const offen = () => (kannPopover && fenster.matches(':popover-open')) || fenster.hasAttribute('data-offen');

  function schliessen() {
    clearTimeout(timer);
    clearTimeout(schliessenTimer);
    if (fenster.hidePopover && fenster.matches(':popover-open')) fenster.hidePopover();
    fenster.removeAttribute('data-offen');
    fenster.hidden = true;
    rahmen.src = 'about:blank';
    ausloeser?.setAttribute('aria-expanded', 'false');
    fest = false;
  }

  function zeigen(knopf, fixieren = false) {
    clearTimeout(timer);
    clearTimeout(schliessenTimer);
    if (fest && !fixieren) return;
    if (!knopf.dataset.dateivorschau) return;
    // Innerhalb eines modalen Dialogs muss auch die Vorschau dort liegen,
    // damit sie für Maus, Tastatur und Screenreader erreichbar bleibt.
    const eltern = dialog.open ? dialog : document.body;
    if (fenster.parentElement !== eltern) {
      schliessen();
      eltern.append(fenster);
    }
    if (ausloeser && ausloeser !== knopf) ausloeser.setAttribute('aria-expanded', 'false');
    ausloeser = knopf;
    fest = fixieren;
    knopf.setAttribute('aria-controls', 'dateivorschau');
    knopf.setAttribute('aria-expanded', 'true');
    document.getElementById('dateivorschau-titel').textContent = knopf.dataset.name || 'Dateivorschau';
    const url = knopf.dataset.dateivorschau;
    if (rahmen.getAttribute('src') !== url) rahmen.src = url;
    original.href = knopf.dataset.vorschauOriginal || knopf.getAttribute('href') || url;
    if (!offen()) {
      fenster.hidden = false;
      if (fenster.showPopover) fenster.showPopover();
      else fenster.setAttribute('data-offen', '');
    }
    if (fixieren) fenster.querySelector('[data-vorschau-schliessen]').focus();
  }

  function spaeterSchliessen() {
    clearTimeout(timer);
    clearTimeout(schliessenTimer);
    if (!fest) schliessenTimer = setTimeout(schliessen, 450);
  }

  document.addEventListener('pointerover', e => {
    if (e.pointerType !== 'mouse' || !matchMedia('(hover: hover)').matches) return;
    const knopf = e.target.closest('[data-dateivorschau]');
    if (!knopf || knopf.contains(e.relatedTarget)) return;
    clearTimeout(schliessenTimer);
    clearTimeout(timer);
    timer = setTimeout(() => { if (knopf.isConnected) zeigen(knopf); }, 450);
  });
  document.addEventListener('pointerout', e => {
    const knopf = e.target.closest('[data-dateivorschau]');
    if (knopf && !knopf.contains(e.relatedTarget)) spaeterSchliessen();
  });
  fenster.addEventListener('pointerenter', () => clearTimeout(schliessenTimer));
  fenster.addEventListener('pointerleave', spaeterSchliessen);
  // Beim Lesen oder Scrollen innerhalb der Vorschau bleibt sie stehen.
  fenster.addEventListener('pointerdown', () => { fest = true; });
  fenster.addEventListener('focusin', () => { fest = true; });
  fenster.addEventListener('toggle', e => {
    if (e.newState === 'closed' && !offen()) schliessen();
  });

  document.addEventListener('click', e => {
    if (e.target.closest('[data-vorschau-schliessen]')) {
      const zurueck = ausloeser;
      schliessen();
      if (zurueck?.isConnected) zurueck.focus();
      return;
    }
    const vorschau = e.target.closest('[data-vorschau-oeffnen]');
    if (vorschau) {
      e.preventDefault();
      zeigen(vorschau, true);
      return;
    }
    if (e.target.closest('[data-nextcloud-oeffnen]')) {
      schliessen();
      if (!dialog.open) dialog.showModal();
      return;
    }
    if (e.target.closest('[data-nextcloud-schliessen]')) {
      schliessen();
      dialog.close();
      return;
    }
    const entfernen = e.target.closest('[data-nextcloud-entfernen]');
    if (entfernen) {
      entfernen.closest('li').remove();
      document.querySelector('[data-eintragsformular]').dispatchEvent(new Event('input', {bubbles: true}));
      return;
    }
    const knopf = e.target.closest('[data-nextcloud-auswahl]');
    if (!knopf) return;
    const liste = document.getElementById('nextcloud-auswahl');
    if (!liste || Array.from(liste.children).some(z => z.dataset.nextcloudPfad === knopf.dataset.name)) return;
    const zeile = document.createElement('li');
    zeile.dataset.nextcloudPfad = knopf.dataset.name;
    const feld = document.createElement('input');
    feld.type = 'hidden'; feld.name = 'anhang_nextcloud'; feld.value = knopf.dataset.nextcloudAuswahl;
    const vorschauKnopf = document.createElement('button');
    vorschauKnopf.type = 'button'; vorschauKnopf.className = 'knopf knopf-leise';
    vorschauKnopf.dataset.dateivorschau = knopf.dataset.dateivorschau;
    vorschauKnopf.dataset.name = knopf.dataset.name;
    vorschauKnopf.dataset.vorschauOriginal = knopf.dataset.vorschauOriginal;
    vorschauKnopf.dataset.vorschauOeffnen = '';
    vorschauKnopf.textContent = 'Vorschau';
    const loeschen = document.createElement('button');
    loeschen.type = 'button'; loeschen.className = 'knopf knopf-leise';
    loeschen.dataset.nextcloudEntfernen = ''; loeschen.textContent = 'Auswahl entfernen';
    zeile.append(feld, document.createTextNode(knopf.dataset.name + ' '), vorschauKnopf, loeschen);
    liste.append(zeile);
    knopf.textContent = 'Ausgewählt';
    feld.dispatchEvent(new Event('input', {bubbles: true}));
  });
  dialog.addEventListener('close', schliessen);
  dialog.addEventListener('cancel', e => {
    if (offen()) { e.preventDefault(); schliessen(); }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && offen()) { e.preventDefault(); schliessen(); }
  });
  document.body.addEventListener('htmx:responseError', e => {
    if (e.detail.target?.id === 'nextcloud-ordner') {
      e.detail.target.textContent = 'Die Dateiauswahl konnte nicht geladen werden. Bitte versuche es erneut.';
    }
  });
  document.body.addEventListener('htmx:beforeRequest', e => {
    if (e.detail.target?.id === 'nextcloud-ordner') schliessen();
  });

  function bildOderPdf(bytes) {
    const text = String.fromCharCode(...bytes);
    if (text.startsWith('%PDF-')) return 'application/pdf';
    if (text.startsWith('\x89PNG\r\n\x1a\n')) return 'image/png';
    if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'image/jpeg';
    if (/^GIF8[79]a/.test(text)) return 'image/gif';
    if (text.startsWith('RIFF') && text.slice(8, 12) === 'WEBP') return 'image/webp';
    return '';
  }

  document.querySelectorAll('[data-eintragsformular] input[type="file"], [data-anhang-upload] input[type="file"]').forEach(eingabe => {
    const liste = document.createElement('ul');
    liste.className = 'anhang-auswahl'; liste.setAttribute('aria-label', 'Ausgewählte Dateien vom Gerät');
    eingabe.after(liste);
    let urls = [];
    function anzeigen() {
      urls.forEach(url => { if (rahmen.getAttribute('src') === url) schliessen(); URL.revokeObjectURL(url); });
      urls = []; liste.replaceChildren();
      Array.from(eingabe.files).forEach((datei, index) => {
        const zeile = document.createElement('li');
        const knopf = document.createElement('button');
        knopf.type = 'button'; knopf.className = 'knopf knopf-leise';
        knopf.textContent = 'Vorschau'; knopf.disabled = true;
        const weg = document.createElement('button');
        weg.type = 'button'; weg.className = 'knopf knopf-leise'; weg.textContent = 'Auswahl entfernen';
        weg.addEventListener('click', () => {
          const transfer = new DataTransfer();
          Array.from(eingabe.files).forEach((f, i) => { if (i !== index) transfer.items.add(f); });
          eingabe.files = transfer.files;
          eingabe.dispatchEvent(new Event('change', {bubbles: true}));
        });
        zeile.append(document.createTextNode(datei.name + ' '), knopf, weg); liste.append(zeile);
        datei.slice(0, 16).arrayBuffer().then(puffer => {
          if (!zeile.isConnected) return;
          const typ = bildOderPdf(new Uint8Array(puffer));
          if (!typ) { knopf.textContent = 'Keine Vorschau für dieses Format'; return; }
          const url = URL.createObjectURL(new Blob([datei], {type: typ})); urls.push(url);
          knopf.dataset.dateivorschau = url; knopf.dataset.vorschauOriginal = url;
          knopf.dataset.vorschauOeffnen = ''; knopf.dataset.name = datei.name; knopf.disabled = false;
        }).catch(() => { knopf.textContent = 'Vorschau nicht verfügbar'; });
      });
    }
    eingabe.addEventListener('change', anzeigen);
    window.addEventListener('pagehide', () => urls.forEach(url => URL.revokeObjectURL(url)));
  });
})();
