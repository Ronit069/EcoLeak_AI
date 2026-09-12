import { chromium } from 'playwright-core';

const run = async (label, url, checks, out) => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERR ' + String(e).slice(0, 120)));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('ERR_FAILED') && !m.text().includes('Failed to load resource')) errs.push('CONSOLE ' + m.text().slice(0, 120)); });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3000);
  const text = await page.textContent('body').then(t => t.replace(/\s+/g, ' '));
  let pass = true;
  console.log(`=== ${label} ===`);
  for (const [name, fn] of Object.entries(checks)) {
    const ok = fn(text, page);
    console.log((ok ? 'PASS' : 'FAIL'), name);
    if (!ok) pass = false;
  }
  if (errs.length) { console.log('JS-ERRORS:'); errs.forEach(e => console.log('  ', e)); }
  await page.screenshot({ path: out, fullPage: true });
  await browser.close();
  return pass;
};

const liveChecks = {
  'live N1 all-scope total rendered': t => t.includes('72,02,350') || t.includes('7,202'),
  'N1 live badge': t => t.includes('N1 live'),
  'Boiler hotspot': t => t.includes('Boiler'),
  'recommendation cards from live J2': t => (t.match(/RANK/g) || []).length >= 12 && t.includes('INT-'),
  'scope from response': t => t.includes('SCOPE 1 + SCOPE 2'),
  'banner lists ONLY P2-DB groups': t => !t.includes('hotspots, recommendations'),
  'LIVE mode label': t => t.includes('LIVE'),
};

const runAll = async () => {
  const live = await run('LIVE MODE (auto, API up)', 'http://localhost:5174/', liveChecks, 'D:/EcoLeak_AI/.impeccable/review/p2-live.png');
  // Fallback test: API down
  console.log('STOPPING API for fallback test...');
  try {
    await (await import('node:child_process')).execSync(
      'powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }"',
      { stdio: 'ignore' });
  } catch { /* already down */ }
  await new Promise(r => setTimeout(r, 2000));
  const fallbackChecks = {
    'dashboard still renders (no blank screen)': t => t.includes('Carbon leak bench'),
    'demo banner visible': t => t.includes('Using demo data') && t.includes('live API unavailable'),
    'mock totals render (5,65,050 kgCO2e en-IN)': t => t.includes('5,65,050') || t.includes('565.1'),
    'Boiler still visible': t => t.includes('Boiler'),
    'J2 mock recs still render': t => (t.match(/RANK/g) || []).length >= 3,
  };
  const fb = await run('FALLBACK MODE (auto, API down)', 'http://localhost:5174/', fallbackChecks, 'D:/EcoLeak_AI/.impeccable/review/p2-fallback.png');
  console.log(live && fb ? 'ALL GROUPS OK' : 'SOME CHECKS FAILED');
  process.exit(live && fb ? 0 : 1);
};
runAll();