/* Screenshots und Bedienprüfung des ersten Gestaltungspakets.
 * Aufruf und Grenzen: design-bestandsaufnahme.md. Keine Schuldaten werden verändert. */
const {chromium} = require('playwright');
const path = require('node:path');
const ausgabe = path.join(__dirname, 'screenshots');
const basis = process.env.SW_PRUEF_URL || 'http://127.0.0.1:8001';
if (!process.env.SW_PRUEF_EMAIL || !process.env.SW_PRUEF_PASSWORT) throw Error('Bitte SW_PRUEF_EMAIL und SW_PRUEF_PASSWORT für ein Administrationskonto setzen.');
(async()=>{
 const browser=await chromium.launch({args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();
 const fehler=[]; page.on('pageerror',e=>fehler.push(e.message));
 await page.goto(basis+'/anmelden');
 await page.getByLabel('E-Mail-Adresse').fill(process.env.SW_PRUEF_EMAIL);
 await page.getByLabel('Passwort',{exact:true}).fill(process.env.SW_PRUEF_PASSWORT);
 await page.getByRole('button',{name:'Anmelden',exact:true}).click();
 await page.waitForURL(basis+'/');
 await page.waitForLoadState('networkidle');
 for(const breite of [1440,768,390,1024]) {
  await page.setViewportSize({width:breite,height:1000});
  for(const [url,name] of [['/','startseite'],['/styleguide','styleguide']]) {
   await page.goto(basis+url);
   await page.waitForLoadState('networkidle');
   const mass=await page.evaluate(()=>({breite:innerWidth,inhalt:document.documentElement.scrollWidth}));
   if(mass.inhalt>mass.breite) throw Error(name+': Überlauf bei '+breite+' '+JSON.stringify(mass));
   if(breite===1440||breite===768||breite===390) await page.screenshot({path:path.join(ausgabe, '01-'+name+'-'+breite+'.png'),fullPage:true});
   console.log(name,breite,'ohne horizontalen Überlauf');
  }
 }
 await page.goto(basis+'/');
 await page.setViewportSize({width:1440,height:1000});
 const suche=page.getByRole('combobox');
 await suche.fill('Märchen');
 await page.locator('[role=listbox]').waitFor();
 await suche.press('ArrowUp');
 if(!await suche.getAttribute('aria-activedescendant')) throw Error('Tastaturauswahl fehlt');
 await suche.press('Escape');
 if(await suche.getAttribute('aria-expanded')!=='false') throw Error('Escape schließt nicht');
 await suche.press('ArrowDown');
 await page.screenshot({path:path.join(ausgabe, '01-suchvorschlaege-1440.png'),fullPage:true});
 await suche.press('Enter');
 await page.waitForURL(/\/d\//);
 console.log('Suche: Pfeiltasten, Escape und Enter geprüft',page.url());
 await page.goto(basis+'/');
 await page.locator('[data-benutzermenue] summary').click();
 await page.getByRole('link',{name:'Gestaltungsübersicht',exact:true}).waitFor();
 await page.locator('[data-benutzermenue] summary').press('Escape');
 if(await page.locator('[data-benutzermenue]').getAttribute('open')!==null) throw Error('Menü bleibt offen');
 console.log('Benutzermenü: Escape geprüft');
 if(fehler.length) throw Error(JSON.stringify(fehler));
 const AxeBuilder = require('@axe-core/playwright').default;
 for (const thema of ['light','dark']) for (const ziel of ['/','/styleguide']) {
  await page.emulateMedia({colorScheme:thema});
  await page.goto(basis+ziel);
  const bericht=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
  if(bericht.violations.length) throw Error(JSON.stringify(bericht.violations));
  console.log('WCAG AA:',thema,ziel,'ohne automatisierten Befund');
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
