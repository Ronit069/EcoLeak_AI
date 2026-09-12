#!/usr/bin/env node
/**
 * K1 UI dual-state check (adversarial). Setup required BEFORE running:
 *   1. seed fixed + broken DBs (tools/seed_sql_lite.py, tools/seed_sqlite_broken.py)
 *   2. start fixed API on :8000 (ENGINE_DSN=fixed), broken API on :8001 (ENGINE_DSN=broken)
 *   3. build two frontend dists baking the two API URLs (VITE_API_URL=...)
 *   4. serve each dist via a PROXY-FREE static server (tests use node static,
 *      never `vite preview`, whose /api proxy silently routes to :8000)
 *   5. node tests/k1_ui.mjs
 * This probe caught a real regression: env baking was broken (import.meta.env
 * accessed indirectly), and `vite preview` proxying masked the broken UI.
 */
import { chromium } from 'playwright-core';
const b = await chromium.launch();

async function probe(url, shot, label) {
  const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
  await p.goto(url + '/scenarios', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(10000);
  const t = (await p.textContent('main')).replace(/\s+/g, ' ');
  const engineLabel = t.includes('Engine-verified simulation (K1)');
  const localLabel = t.includes('computed_via=local_fallback');
  const bannerScenario = t.includes('scenario-simulate');
  const projected = (t.match(/PROJECTED.{0,26}/) || ['none'])[0];
  console.log(`=== ${label} ===`);
  console.log('  engine-label:', engineLabel);
  console.log('  local-fallback-label:', localLabel);
  console.log('  banner lists scenario-simulate:', bannerScenario);
  console.log('  projected gauge:', projected);
  if (engineLabel && localLabel) console.log('  !! BOTH LABELS PRESENT — labeling bug');
  await p.screenshot({ path: shot, fullPage: false });
  await p.close();
  return { engineLabel, localLabel, bannerScenario };
}

const fixed = await probe('http://localhost:5174', 'D:/EcoLeak_AI/.impeccable/review/k1-ui-fixed.png', 'FIXED API (:8000)');
const broken = await probe('http://localhost:5175', 'D:/EcoLeak_AI/.impeccable/review/k1-ui-broken.png', 'BROKEN API (:8001, 5-entry seed)');

const okFixed = fixed.engineLabel && !fixed.localLabel && !fixed.bannerScenario;
const okBroken = broken.localLabel && !broken.engineLabel && broken.bannerScenario;
console.log(okFixed ? 'PASS fixed-UI shows engine label and nothing else' : 'FAIL fixed-UI');
console.log(okBroken ? 'PASS broken-UI shows fallback label + banner, never engine' : 'FAIL broken-UI');
await b.close();
process.exit(okFixed && okBroken ? 0 : 1);
