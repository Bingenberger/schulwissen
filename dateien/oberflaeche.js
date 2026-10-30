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
