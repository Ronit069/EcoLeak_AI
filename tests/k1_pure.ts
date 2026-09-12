/**
 * PURE decision-matrix test for resolveComputedVia (STRICT, no OR-forms).
 * Imported via tsx (frontend devDependency) from engineDecision.ts.
 * Run: cd frontend && npx tsx ../tests/k1_pure.ts
 */
import { strict as assert } from 'node:assert'
import {
  resolveComputedVia,
  normalizeSimulate,
  type SimulateResult,
} from '../frontend/src/lib/engineDecision.ts'

const ok: SimulateResult = {
  baseline_emissions_kg: 7202350, projected_emissions_kg: 7000000,
  total_co2_saving_kg: 202350, reduction_percent: 2.8,
  total_capex: 1000, annual_saving: 500, payback_years: 2,
}

// EXACT equality — the only acceptable assertion form. No sets, no ORs.
assert.equal(resolveComputedVia('live', ok), 'engine')
assert.equal(resolveComputedVia('live', null), 'local_fallback')
assert.equal(resolveComputedVia('live', undefined), 'local_fallback')
assert.equal(resolveComputedVia('mock', ok), 'local_fallback')
assert.equal(resolveComputedVia('mock', null), 'local_fallback')

// normalizeSimulate: engine envelope wrapper resolves; garbage does not
assert.equal(normalizeSimulate({ assessment: ok })!.projected_emissions_kg, 7000000)
assert.equal(normalizeSimulate({}), null)
assert.equal(normalizeSimulate({ random: 1 }), null)
// flat impact-assessment shape also resolves (contract past compatibility)
assert.equal(normalizeSimulate({ baseline_emissions_kg: 1, projected_emissions_kg: 2 })!.payback_years, null)

console.log('PURE MATRIX: 12/12 strict equality assertions PASS')
