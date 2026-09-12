/**
 * PURE K1/fallback decision logic — no import.meta, no fetch, no env.
 * Importable by Node tests (tsx) directly. The env-bound fetch layer in
 * api.ts delegates here so every decision is unit-testable exactly.
 */
export type Source = 'live' | 'mock'

export interface SimulateResult {
  baseline_emissions_kg: number
  projected_emissions_kg: number
  total_co2_saving_kg: number | null
  reduction_percent: number | null
  total_capex: number
  annual_saving: number | null
  payback_years: number | null
}

export interface SimulateOutcome {
  data: SimulateResult | null
  computedVia: 'engine' | 'local_fallback'
}

/**
 * STRICT basis decision (adversarial-test contract — tests/k1_pure.ts):
 * computedVia === 'engine' IFF the live call resolved WITH data.
 * Any mock source, any failure, any null parse => local_fallback.
 * No third state, no looser acceptance.
 */
export function resolveComputedVia(
  source: Source,
  data: SimulateResult | null | undefined,
): 'engine' | 'local_fallback' {
  return source === 'live' && data != null ? 'engine' : 'local_fallback'
}

/**
 * Defensive normalization of K1 responses (wrapper envelope is canonical).
 */
export function normalizeSimulate(raw: Record<string, unknown>): SimulateResult | null {
  const nested = raw['assessment'] as Record<string, unknown> | undefined
  const pick = (k: string): unknown => raw[k] ?? (nested ? nested[k] : undefined)
  if (pick('projected_emissions_kg') === undefined && pick('baseline_emissions_kg') === undefined) {
    return null
  }
  return {
    baseline_emissions_kg: Number(pick('baseline_emissions_kg')),
    projected_emissions_kg: Number(pick('projected_emissions_kg')),
    total_co2_saving_kg: pick('total_co2_saving_kg') == null ? null : Number(pick('total_co2_saving_kg')),
    reduction_percent: pick('reduction_percent') == null ? null : Number(pick('reduction_percent')),
    total_capex: Number(pick('total_capex') ?? 0),
    annual_saving: pick('annual_saving') == null ? null : Number(pick('annual_saving')),
    payback_years: pick('payback_years') == null ? null : Number(pick('payback_years')),
  }
}
