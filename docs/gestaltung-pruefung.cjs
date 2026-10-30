/* Wiederholbare Gestaltungsprüfung gegen die lokale Demo-Instanz.
 * Zugangsdaten nur aus der Umgebung; es werden keine Schuldaten gespeichert. */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const path = require('node:path');
const fs = require('node:fs');
const basis = process.env.SW_PRUEF_URL || 'http://127.0.0.1:8001';
const ausgabe = path.join(__dirname, 'screenshots');
if (!process.env.SW_PRUEF_EMAIL || !process.env.SW_PRUEF_PASSWORT) {
  throw Error('Bitte SW_PRUEF_EMAIL und SW_PRUEF_PASSWORT für ein Administrationskonto setzen.');
}
const ziele = [
  ['/', '01-startseite'], ['/styleguide', '01-styleguide'],
  ['/suche/?q=M%C3%A4rchen', '02-suche'], ['/suche/?q=xyzzzzzzzz', '02-suche-leer'],
  ['/d/arbeitsplan-deutsch/V-3-01', '03-eintrag'],
  ['/d/arbeitsplan-deutsch/R-01', '03-ritual'],
  ['/d/arbeitsplan-deutsch/2.4', '03-grundlagen'],
  ['/d/arbeitsplan-deutsch/V-3-01/bearbeiten', '03-bearbeiten'],
  ['/d/arbeitsplan-deutsch', '04-dokument'],
  ['/deutsch/arbeitsplan-deutsch/abdeckung', '04-abdeckung'],
  ['/deutsch/arbeitsplan-deutsch/fahrplan/3', '04-fahrplan'],
  ['/deutsch/arbeitsplan-deutsch/zeitbudget', '04-zeitbudget'],
  ['/deutsch/arbeitsplan-deutsch/leistung', '04-leistung'],
  ['/deutsch/arbeitsplan-deutsch/rituale', '04-rituale'],
  ['/deutsch/arbeitsplan-deutsch/progressionspaare', '04-progression'],
  ['/deutsch/arbeitsplan-deutsch/pruefliste', '04-pruefliste'],
  ['/kompetenzen/?fach=deutsch', '04-kompetenzen'],
  ['/meine-planung?dokument=arbeitsplan-deutsch&schuljahr=2026%2F27&jahrgang=3&klasse=3a', '05-planung'],
  ['/beschluesse', '05-beschluesse'], ['/beschluesse/vorlage', '05-beschlussvorlage'],
  ['/d/arbeitsplan-deutsch/import', '05-import'], ['/verwaltung/', '05-verwaltung'],
];
(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage();
  const bericht = { datum: new Date().toISOString(), breiten: [390, 768, 1024, 1440], ansichten: [], browserfehler: [] };
  page.on('pageerror', e => bericht.browserfehler.push(e.message));
  await page.goto(basis + '/anmelden');
  await page.getByLabel('E-Mail-Adresse').fill(process.env.SW_PRUEF_EMAIL);
  await page.getByLabel('Passwort', { exact: true }).fill(process.env.SW_PRUEF_PASSWORT);
  await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await page.waitForURL(basis + '/');
  for (const [url, name] of ziele) {
    const ergebnis = { seite: name, breiten: [], barrierefreiheit: [] };
    await page.emulateMedia({ colorScheme: 'light' });
    for (const breite of [1440, 768, 390, 1024]) {
      await page.setViewportSize({ width: breite, height: 1000 });
      const antwort = await page.goto(basis + url);
      if (antwort.status() !== 200) throw Error(`${name}: HTTP ${antwort.status()}`);
      await page.waitForLoadState('networkidle');
      const ueberlauf = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      ergebnis.breiten.push({ breite, ueberlauf });
      if ([1440, 768].includes(breite) || (breite === 390 && name.startsWith('01-'))) {
        await page.screenshot({ path: path.join(ausgabe, `${name}-${breite}.png`), fullPage: true });
      }
    }
    for (const thema of ['light', 'dark']) {
      await page.emulateMedia({ colorScheme: thema });
      const pruefung = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      ergebnis.barrierefreiheit.push({ thema, befunde: pruefung.violations.map(v => ({ regel: v.id, elemente: v.nodes.map(n => n.target) })) });
    }
    bericht.ansichten.push(ergebnis);
    console.log(name, JSON.stringify(ergebnis));
  }
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto(basis + '/');
  const suche = page.getByRole('combobox');
  await suche.fill('Märchen');
  await page.locator('[role=listbox]').waitFor();
  await suche.press('ArrowUp');
  if (!await suche.getAttribute('aria-activedescendant')) throw Error('Tastaturauswahl fehlt');
  await suche.press('Escape');
  if (await suche.getAttribute('aria-expanded') !== 'false') throw Error('Escape schließt nicht');
  await suche.press('ArrowDown');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: path.join(ausgabe, '02-suchvorschlaege-1440.png'), fullPage: true });
  await suche.press('Enter'); await page.waitForURL(/\/d\//);
  await page.goto(basis + '/d/arbeitsplan-deutsch/V-3-01/bearbeiten');
  const vorher = await page.locator('[data-fortschritt-text]').innerText();
  await page.locator('#id_titel').fill('');
  await page.waitForFunction(text => document.querySelector('[data-fortschritt-text]').textContent !== text, vorher);
  await page.locator('[data-fortschritt] summary').click();
  await page.locator('[data-fehlende-felder]').getByRole('button', { name: 'Titel', exact: true }).click();
  if (!await page.locator('#id_titel').evaluate(e => e === document.activeElement)) throw Error('Pflichtfeldsprung fehlt');
  bericht.bedienung = { suchauswahl: true, escape: true, pflichtfeldfortschritt: true, pflichtfeldsprung: true };
  fs.writeFileSync(path.join(__dirname, 'gestaltungspruefung.json'), JSON.stringify(bericht, null, 2) + '\n');
  await browser.close();
  if (bericht.browserfehler.length || bericht.ansichten.some(a => a.breiten.some(b => b.ueberlauf) || a.barrierefreiheit.some(b => b.befunde.length))) {
    throw Error('Die Prüfung enthält Befunde. Siehe docs/gestaltungspruefung.json.');
  }
  console.log('Gestaltungsprüfung erfolgreich. Keine Schuldaten verändert.');
})().catch(e => { console.error(e); process.exit(1); });
