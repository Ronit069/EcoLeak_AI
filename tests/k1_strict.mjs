#!/usr/bin/env node
/**
 * ADVERSARIAL K1 strict checker (per-id, no aggregates).
 *
 * Usage: node tests/k1_strict.mjs <base_url> [--negative]
 *
 * For EVERY intervention_id from a live J2 response, this performs ONE
 * individual K1 POST and determines the basis STRICTLY:
 *   engine  <=> HTTP 200 AND response.assessment present AND no error_code
 *   anything else (404, 5xx, wrapper without assessment) => NOT engine
 *
 * A single non-engine id fails the run. A negative control (unknown id)
 * MUST return 404 with the frozen error shape. Do not run anything else
 * in this suite; batch POSTs are not accepted as proof.
 */
import { strict as assert } from 'node:assert'

const BASE = process.argv[2]
if (!BASE) { console.error('usage: node k1_strict.mjs <base_url>'); process.exit(2) }
const F = '0a1b2c3d-0002-4002-8002-000000000002'
const P = '0a1b2c3d-0003-4003-8003-000000000003'

async function j2Ids() {
  const r = await fetch(`${BASE}/api/facilities/${F}/reporting-periods/${P}/recommendations`)
  assert.equal(r.status, 200, `J2 fetch failed: ${r.status}`)
  const body = await r.json()
  return body.recommendations.map((x) => x.intervention_id)
}

async function k1(id) {
  const res = await fetch(
    `${BASE}/api/scenarios/00000000-0000-4000-8000-000000000000/simulate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        facility_id: F, reporting_period_id: P,
        interventions: [{ intervention_id: id, adoption_percentage: 50 }],
      }),
    },
  )
  let body = null
  try { body = await res.json() } catch { /* non-json */ }
  // STRICT basis: engine ONLY on 200 + assessment + no error_code.
  const isEngine = res.status === 200 && body && body.assessment && !body.error_code
  return { id, status: res.status, isEngine, hasAssessment: !!(body && body.assessment) }
}

const ids = await j2Ids()
console.log(`live J2 ids: ${ids.length}`)
assert.equal(ids.length, 18, `expected 18 ids, got ${ids.length}`)

const rows = []
let allEngine = true
let failed = 0
const failures = []
// Collect EVERY id first (no early abort) so the full per-id table prints,
// then assert strictly — one non-engine id fails the run.
for (const id of ids) {
  const r = await k1(id)
  rows.push(r)
  if (!r.isEngine) { allEngine = false; failed++; failures.push(r.id) }
}

console.log('PER-ID RESULTS (all 18, individually):')
for (const r of rows) console.log(`  ${r.id}  status=${r.status}  assessment=${r.hasAssessment}  computedVia=${r.isEngine ? 'engine' : 'NON-ENGINE'}`)
console.log(`AGGREGATE: engine=${failed === 0 ? '18/18' : `${18 - failed}/18`} -> ${allEngine ? 'PASS' : 'FAIL'}`)
assert.ok(allEngine, `NON-ENGINE IDs (would have been silent fallback before fix): ${failures.join(', ')}`)

// Negative control: an unknown id must 404 with the frozen error shape
const neg = await fetch(
  `${BASE}/api/scenarios/00000000-0000-4000-8000-000000000000/simulate`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      facility_id: F, reporting_period_id: P,
      interventions: [{ intervention_id: 'ffffffff-ffff-4fff-8fff-ffffffffffff', adoption_percentage: 100 }],
    }),
  },
)
const negBody = await neg.json()
assert.equal(neg.status, 404, `negative control expected 404, got ${neg.status}`)
assert.deepEqual(Object.keys(negBody).sort(), ['details', 'error_code', 'message', 'severity'], 'negative control must use frozen error shape')
console.log(`NEGATIVE CONTROL: unknown id -> ${neg.status} ${negBody.error_code} (frozen shape) PASS`)
console.log('K1 STRICT: ALL CHECKS PASS — every live id resolves via the engine')