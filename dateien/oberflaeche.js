/* Bedienung gemeinsamer Komponenten; alle Inhalte kommen weiter vom Server. */
document.addEventListener('alpine:init', () => {
  Alpine.data('schulwissenSuche', () => ({
    offen: false, sucht: false, aktiv: -1, aktiveId: '',
    init() {
      this.$el.addEventListener('htmx:beforeRequest', () => { this.sucht = true; });
      this.$el.addEventListener('htmx:afterRequest', () => { this.sucht = false; });
      this.$el.addEventListener('htmx:afterSwap', () => this.vorschlaegeGeladen());
    },
    optionen() { return [...this.$refs.vorschlaege.querySelectorAll('[role="option"] a')]; },
    vorschlaegeGeladen() {
      const liste = this.$refs.vorschlaege.querySelector('[role="listbox"]');
      this.aktiv = -1; this.aktiveId = '';
      if (liste) {
        liste.id = this.$refs.eingabe.id + '-liste';
        this.$refs.eingabe.setAttribute('aria-controls', liste.id);
        this.optionen().forEach((a, i) => {
          a.parentElement.id = liste.id + '-' + i;
          a.parentElement.setAttribute('aria-selected', 'false');
          a.tabIndex = -1;
        });
      } else this.$refs.eingabe.setAttribute('aria-controls', this.$refs.vorschlaege.id);
      this.offen = document.activeElement === this.$refs.eingabe;
    },
    bewegen(richtung) {
      const optionen = this.optionen();
      if (!optionen.length) return;
      this.offen = true;
      this.aktiv = this.aktiv < 0 ? (richtung > 0 ? 0 : optionen.length - 1) :
        (this.aktiv + richtung + optionen.length) % optionen.length;
      optionen.forEach((a, i) => a.parentElement.setAttribute('aria-selected', String(i === this.aktiv)));
      this.aktiveId = optionen[this.aktiv].parentElement.id;
      optionen[this.aktiv].scrollIntoView({block: 'nearest'});
    },
    auswaehlen(event) {
      if (this.offen && this.aktiv >= 0) {
        event.preventDefault(); window.location.assign(this.optionen()[this.aktiv].href);
      }
    },
    schliessen() { this.offen = false; this.aktiv = -1; this.aktiveId = ''; }
  }));
});
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-benutzermenue]').forEach(menue => {
    document.addEventListener('click', event => { if (!menue.contains(event.target)) menue.open = false; });
    menue.addEventListener('keydown', event => {
      if (event.key === 'Escape') { menue.open = false; menue.querySelector('summary').focus(); }
    });
  });
  document.querySelectorAll('[data-meldung-schliessen]').forEach(knopf => {
    knopf.addEventListener('click', () => knopf.closest('.meldung').remove());
  });
  document.querySelectorAll('[data-toast]').forEach(meldung => {
    let timer;
    const starten = () => { clearTimeout(timer); timer = setTimeout(() => meldung.remove(), 3000); };
    const pausieren = () => clearTimeout(timer);
    meldung.addEventListener('mouseenter', pausieren);
    meldung.addEventListener('focusin', pausieren);
    meldung.addEventListener('mouseleave', starten);
    meldung.addEventListener('focusout', starten);
    starten();
  });
});

/* Gliederung und Formularhinweise passen sich an den Bildschirm an. */
document.addEventListener('DOMContentLoaded', () => {
  const breit = matchMedia('(min-width: 1101px)');
  document.querySelectorAll('[data-gliederung],[data-ritual-jahrgang]').forEach(baum => {
    const anpassen = () => { baum.open = breit.matches; };
    anpassen(); breit.addEventListener('change', anpassen);
  });
  document.querySelectorAll('.suchfilter .filter-chip').forEach(chip => {
    chip.addEventListener('toggle', () => {
      if (chip.open) chip.closest('form').querySelectorAll('.filter-chip').forEach(anderer => {
        if (anderer !== chip) anderer.open = false;
      });
    });
    chip.addEventListener('keydown', e => { if (e.key === 'Escape') { chip.open = false; chip.querySelector('summary').focus(); } });
    document.addEventListener('click', e => { if (!chip.contains(e.target)) chip.open = false; });
  });
  document.querySelectorAll('[data-eintragsformular]').forEach(formular => {
    const hinweis = formular.querySelector('[data-fortschritt]');
    function auffrischen() {
      const felder = [...formular.querySelectorAll('[data-pflicht]')].filter(f => f.getClientRects().length);
      const fehlend = felder.filter(f => {
        const eingabe = f.querySelector('input,textarea,select');
        return !eingabe || !eingabe.value.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
      });
      felder.forEach(f => f.classList.toggle('ist-offen', fehlend.includes(f)));
      hinweis.hidden = false;
      formular.querySelector('[data-fortschritt-text]').textContent = `${felder.length-fehlend.length} von ${felder.length} Pflichtfeldern ausgefüllt`;
      const balken = formular.querySelector('[data-fortschritt-balken]');
      balken.max = felder.length || 1; balken.value = felder.length-fehlend.length;
      const liste = formular.querySelector('[data-fehlende-felder]');
      liste.replaceChildren();
      fehlend.forEach(f => {
        const li = document.createElement('li'), knopf = document.createElement('button');
        knopf.type = 'button'; knopf.className = 'knopf knopf-leise'; knopf.textContent = f.dataset.pflicht;
        knopf.addEventListener('click', () => {
          f.scrollIntoView({block:'center'});
          f.querySelector('[contenteditable="true"],input:not([type="hidden"]),select,textarea:not(.editor-quelle)')?.focus();
        });
        li.append(knopf); liste.append(li);
      });
      if (!fehlend.length) { const li = document.createElement('li'); li.textContent = 'Alle Pflichtfelder sind ausgefüllt.'; liste.append(li); }
      const status = formular.querySelector('[name="status"]');
      formular.querySelector('[data-speichern]').textContent = status?.value === 'entwurf' ? 'Als Entwurf speichern' : 'Speichern';
    }
    function geaendert() { formular.querySelector('[data-speicherhinweis]').textContent = 'Ungespeicherte Änderungen'; requestAnimationFrame(auffrischen); }
    formular.addEventListener('input', geaendert); formular.addEventListener('change', geaendert);
    requestAnimationFrame(auffrischen);
  });
  document.querySelectorAll('textarea:not([data-editor])').forEach(feld => {
    function wachsen() { if (feld.offsetParent) { feld.style.height = 'auto'; feld.style.height = Math.max(feld.scrollHeight, 100)+'px'; } }
    feld.addEventListener('input', wachsen);
  });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.auswertungen-navigation a').forEach(a => {
    if (new URL(a.href).pathname === location.pathname) a.setAttribute('aria-current','page');
  });
});
