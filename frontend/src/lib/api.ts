import type {
  HotspotDetectionResult, RecommendationGenerationResult, MockDataset
} from './contracts'
import { hotspotResultSchema, recommendationResultSchema } from './zod'

// ---------------------------------------------------------------------------
// Phase 2 data layer: real API first, mock fallback behind USE_MOCK_DATA.
//
// Mode resolution (shared Phase 2 gate, P1 side):
//   1. localStorage 'ecoleak.useMockData'  (runtime override; demo banner toggles)
//   2. VITE_USE_MOCK_DATA  ('true'|'false'|'auto')
//   3. VITE_USE_MOCKS (legacy Phase 1 flag: true->mock, false->live)
//   4. unset -> 'auto' (live first, instant per-group mock fallback)
//
// Every endpoint group goes through liveOrMock(): in 'auto' a live failure
// (network / 4xx / 5xx / Zod shape failure) falls back to the Phase 1 mock
// payload FOR THAT GROUP ONLY and records the group in the fallback registry
// so <DemoDataBanner> can show "using demo data". No blank/crashed screens.
//
// Live mapping (contracts/api_contract.md): A2/A5/A9 profiling, B2 processes,
// C3 activity, E1 factors, G2 hotspots, N1 dashboard, N2 leak-map, J2
// recommendations, M1 explanation, K1 simulate; dataset via merged API
// /api/context (additive endpoint logged in docs/phase2/contract_changes.md).
// ---------------------------------------------------------------------------

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
const API_TOKEN = (import.meta.env.VITE_API_TOKEN as string | undefined) ?? ''

export type MockMode = 'auto' | 'mock' | 'live'
export type Source = 'live' | 'mock'

/** Bootstrap IDs — resolved from /api/context first, mock UUIDs as fallback. */
export interface BootstrapIds {
  organization_id: string
  facility_id: string
  reporting_period_id: string
}

export const DEMO_IDS: BootstrapIds = {
  organization_id: '0a1b2c3d-0001-4001-8001-000000000001',
  facility_id: '0a1b2c3d-0002-4002-8002-000000000002',
  reporting_period_id: '0a1b2c3d-0003-4003-8003-000000000003'
}

// ---------------------------------------------------------------------------
// Mode resolution + fallback registry
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'ecoleak.useMockData'
const listeners = new Set<() => void>()

export function resolveMockMode(): MockMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'mock' || stored === 'live' || stored === 'auto') return stored
  } catch { /* SSR/private mode — ignore */ }
  const v2 = (import.meta.env.VITE_USE_MOCK_DATA as string | undefined)?.toLowerCase()
  if (v2 === 'true') return 'mock'
  if (v2 === 'false') return 'live'
  if (v2 === 'auto') return 'auto'
  // Legacy Phase 1 flag.
  const legacy = (import.meta.env.VITE_USE_MOCKS as string | undefined)?.toLowerCase()
  if (legacy !== undefined) return legacy === 'false' ? 'live' : 'mock'
  return 'auto'
}

export function setMockModeOverride(mode: MockMode): void {
  try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* ignore */ }
  listeners.forEach(l => l())
}

export function subscribeMockMode(cb: () => void): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export interface FallbackState {
  groups: string[]
}

const fallback: FallbackState = { groups: [] }
const fallbackListeners = new Set<() => void>()

export function getFallbackGroups(): string[] {
  return [...fallback.groups]
}

export function subscribeFallbacks(cb: () => void): () => void {
  fallbackListeners.add(cb)
  return () => fallbackListeners.delete(cb)
}

function recordFallback(group: string): void {
  if (!fallback.groups.includes(group)) {
    fallback.groups.push(group)
    fallbackListeners.forEach(l => l())
  }
}

export function resetFallbacks(): void {
  if (fallback.groups.length) {
    fallback.groups = []
    fallbackListeners.forEach(l => l())
  }
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number
  readonly errorCode?: string
  constructor(status: number, message: string, errorCode?: string) {
    super(message)
    this.status = status
    this.errorCode = errorCode
  }
}

const FETCH_TIMEOUT_MS = 5000

/** Abort-compatible timeout (Signal.timeout not in older browsers). */
function timeoutSignal(): { signal: AbortSignal; clear: () => void } {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(new DOMException('timeout', 'TimeoutError')), FETCH_TIMEOUT_MS)
  return { signal: ctrl.signal, clear: () => clearTimeout(timer) }
}

async function getJson<T>(url: string): Promise<T> {
  const headers: Record<string, string> = {}
  // Auth wiring (Phase 1 D1): VITE_API_TOKEN -> Bearer; flips stub->JWT
  // without touching components.
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`
  const { signal, clear } = timeoutSignal()
  const res = await fetch(url, { headers, signal }).finally(clear)
  if (res.status === 401) {
    throw new ApiError(401, 'Authentication required — check VITE_API_TOKEN / backend auth_mode.', 'UNAUTHORIZED')
  }
  if (!res.ok) {
    let errorCode: string | undefined
    try {
      const body = await res.json() as { error_code?: string; message?: string }
      errorCode = body.error_code
      throw new ApiError(res.status, body.message ?? `Request failed: ${res.status} ${url}`, errorCode)
    } catch (e) {
      if (e instanceof ApiError) throw e
      throw new ApiError(res.status, `Request failed: ${res.status} ${url}`)
    }
  }
  const contentType = res.headers.get('content-type') ?? ''
  // A 200 from a non-API origin (SPA fallback HTML) must count as a failed
  // live call so auto-fallback kicks in instead of parsing HTML as JSON.
  if (contentType.includes('text/html')) {
    throw new ApiError(500, `Not an API response: ${url} (content-type ${contentType})`)
  }
  return res.json() as Promise<T>
}

export interface GroupResult<T> {
  data: T
  source: Source
  group: string
}

/**
 * Live-first with per-group mock fallback (auto mode).
 * 'mock' mode -> straight to fallback. 'live' mode -> live or throw.
 */
export async function liveOrMock<T>(
  group: string,
  liveFetch: () => Promise<T>,
  mockFetch: () => Promise<T>,
): Promise<GroupResult<T>> {
  const mode = resolveMockMode()
  if (mode === 'mock') {
    return { data: await mockFetch(), source: 'mock', group }
  }
  if (mode === 'live') {
    return { data: await liveFetch(), source: 'live', group }
  }
  // auto: live first, fallback per group
  try {
    return { data: await liveFetch(), source: 'live', group }
  } catch (err) {
    recordFallback(group)
    return { data: await mockFetch(), source: 'mock', group }
  }
}

// ---------------------------------------------------------------------------
// Dataset / bootstrap
// ---------------------------------------------------------------------------

export async function fetchDataset(): Promise<GroupResult<MockDataset>> {
  return liveOrMock<MockDataset>(
    'dataset',
    async () => getJson<MockDataset>(`${API_URL}/api/context`),
    async () => getJson<MockDataset>('/mocks/mock_dataset.json'),
  )
}

export async function fetchBootstrapIds(): Promise<BootstrapIds> {
  const { data, source } = await fetchDataset()
  if (source === 'live' && data.facilities.length > 0) {
    return {
      organization_id: data.organization?.id ?? DEMO_IDS.organization_id,
      facility_id: data.facilities[0].id,
      reporting_period_id:
        data.reporting_periods[0]?.id ?? DEMO_IDS.reporting_period_id,
    }
  }
  return DEMO_IDS
}

// ---------------------------------------------------------------------------
// Endpoint groups (one live call each, mock fallback each)
// ---------------------------------------------------------------------------

export async function fetchProcesses(
  facilityId: string,
): Promise<GroupResult<MockDataset['processes']>> {
  return liveOrMock(
    'processes',
    async () => {
      const rows = await getJson<unknown[]>(
        `${API_URL}/api/facilities/${facilityId}/processes`)
      return rows as MockDataset['processes']
    },
    async () => {
      // Phase 1 mock truth: the frozen dataset file (NOT /api/context, which
      // carries org/facility/period only and has no processes key).
      const mock = await getJson<MockDataset>('/mocks/mock_dataset.json')
      return mock.processes
    },
  )
}

export async function fetchActivities(
  facilityId: string,
  periodId: string,
): Promise<GroupResult<MockDataset['activity_data']>> {
  return liveOrMock(
    'activities',
    async () => {
      const rows = await getJson<unknown[]>(
        `${API_URL}/api/facilities/${facilityId}/activity?reporting_period_id=${periodId}`)
      return rows as MockDataset['activity_data']
    },
    async () => {
      const mock = await getJson<MockDataset>('/mocks/mock_dataset.json')
      return mock.activity_data
    },
  )
}

export async function fetchHotspots(
  facilityId: string,
  periodId: string,
): Promise<GroupResult<HotspotDetectionResult>> {
  return liveOrMock<HotspotDetectionResult>(
    'hotspots',
    async () => {
      const raw = await getJson<unknown>(
        `${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/hotspots`)
      return hotspotResultSchema.parse(raw)
    },
    async () => {
      const raw = await getJson<unknown>('/mocks/mock_hotspot_output.json')
      return hotspotResultSchema.parse(raw)
    },
  )
}

export interface DashboardPayload {
  total_kgco2e: number
  scope_breakdown: Record<string, number>
  carbon_intensity: number | null
  production_unit?: string | null  // formally accepted Phase-2 additive key
  largest_hotspot: unknown | null
  circularity_score: number | null
  potential_reduction_kgco2e: number
  potential_annual_saving: number
  last_calculated_at: string
  empty_state: boolean
}

export async function fetchDashboard(
  facilityId: string,
  periodId: string,
): Promise<GroupResult<DashboardPayload | null>> {
  // N1 lives behind the merged API; fallback: null -> caller derives from
  // (possibly fallen-back) hotspots + recommendations. Derivation is NOT a
  // mock; it is real-data aggregation, so no "demo data" banner for it.
  return liveOrMock<DashboardPayload | null>(
    'dashboard',
    async () => {
      const raw = await getJson<DashboardPayload>(
        `${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/dashboard`)
      return raw
    },
    async () => null,
  )
}

export async function fetchLeakMap(
  facilityId: string,
  periodId: string,
): Promise<GroupResult<{ nodes: unknown[]; links: unknown[] }>> {
  return liveOrMock(
    'leak-map',
    async () => {
      const raw = await getJson<{ nodes: unknown[]; links: unknown[] }>(
        `${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/leak-map`)
      return raw
    },
    async () => {
      const { data } = await fetchHotspots(facilityId, periodId)
      return {
        nodes: data.hotspots.map(h => ({
          process_id: h.process_id,
          process_name: h.process_name,
          emissions_kgco2e: h.emissions_kgco2e,
          contribution_percent: h.contribution_percent,
          severity: h.severity,
        })),
        links: [],
      }
    },
  )
}

export async function fetchRecommendations(
  facilityId: string,
  periodId: string,
): Promise<GroupResult<RecommendationGenerationResult>> {
  return liveOrMock<RecommendationGenerationResult>(
    'recommendations',
    async () => {
      const raw = await getJson<unknown>(
        `${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/recommendations`)
      return recommendationResultSchema.parse(raw)
    },
    async () => {
      const raw = await getJson<unknown>('/mocks/mock_recommendation_output.json')
      return recommendationResultSchema.parse(raw)
    },
  )
}

export async function fetchExplanation(
  recommendationId: string,
): Promise<GroupResult<Record<string, unknown> | null>> {
  return liveOrMock<Record<string, unknown> | null>(
    'explanation',
    async () => getJson<Record<string, unknown>>(
      `${API_URL}/api/recommendations/${recommendationId}/explanation`),
    async () => null,
  )
}

export interface SimulateResult {
  baseline_emissions_kg: number
  projected_emissions_kg: number
  total_co2_saving_kg: number | null
  reduction_percent: number | null
  total_capex: number
  annual_saving: number | null
  payback_years: number | null
}

/**
 * Defensive normalization of K1 responses. The frozen contract says the
 * response IS an ImpactAssessment; the live engine router wraps it as
 * { assessment: ImpactAssessment, interventions, over_budget, issues, ... }.
 * Unwrap (and prefer flat) so the UI works with either shape. Deviation from
 * the contracted shape is logged in docs/phase2/contract_changes.md §P1.
 */
function normalizeSimulate(raw: Record<string, unknown>): SimulateResult | null {
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

export interface SimulateOutcome {
  data: SimulateResult | null
  computedVia: 'engine' | 'local_fallback'
}

export async function fetchSimulate(
  facilityId: string,
  periodId: string,
  selections: Array<{ intervention_id: string; adoption_percentage: number; selected?: boolean }>,
  budgetLimit?: number,
): Promise<SimulateOutcome> {
  // K1: POST /api/scenarios/{scenario_id}/simulate (merged engine router).
  // BLOCKER-1 remediation: never silently fall back — the caller is told
  // which basis produced the numbers (computedVia), and any live failure
  // also lands 'scenario-simulate' in the demo-data banner group list.
  const r = await liveOrMock<SimulateResult | null>(
    'scenario-simulate',
    async () => {
      const raw = await postJson<Record<string, unknown>>(
        `${API_URL}/api/scenarios/00000000-0000-4000-8000-000000000000/simulate`,
        {
          facility_id: facilityId,
          reporting_period_id: periodId,
          interventions: selections.map(s => ({
            intervention_id: s.intervention_id,
            adoption_percentage: s.adoption_percentage,
            selected: s.selected !== false,
          })),
          ...(budgetLimit !== undefined ? { budget_limit: String(budgetLimit) } : {}),
        },
      )
      return normalizeSimulate(raw)
    },
    async () => null,
  )
  // Visible basis flag: 'engine' only when the K1 call truly resolved;
  // any fallback (registry hit, network error, unresolved ids) = local math.
  const computedVia: SimulateOutcome['computedVia'] =
    r.source === 'live' && r.data ? 'engine' : 'local_fallback'
  return { data: r.data, computedVia }
}

/** POST helper used by fetchSimulate (headers/body handling). */
export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`
  const { signal, clear } = timeoutSignal()
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body), signal }).finally(clear)
  if (res.status === 401) {
    throw new ApiError(401, 'Authentication required — check VITE_API_TOKEN / backend auth_mode.', 'UNAUTHORIZED')
  }
  if (!res.ok) {
    let errorCode: string | undefined
    try {
      const b = await res.json() as { error_code?: string; message?: string }
      errorCode = b.error_code
      throw new ApiError(res.status, b.message ?? `POST failed: ${res.status} ${url}`, errorCode)
    } catch (e) {
      if (e instanceof ApiError) throw e
      throw new ApiError(res.status, `POST failed: ${res.status} ${url}`)
    }
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Derived dashboard + local simulator (mock-mode / fallback math)
// ---------------------------------------------------------------------------

export function deriveDashboard(
  hotspots: HotspotDetectionResult,
  recs: RecommendationGenerationResult,
) {
  const potentialReduction = recs.recommendations.reduce(
    (s, r) => s + (r.impact?.estimated_co2_saving_kg ?? 0), 0)
  const potentialSaving = recs.recommendations.reduce(
    (s, r) => s + (r.impact?.estimated_annual_saving ?? 0), 0)
  const totalCapex = recs.recommendations.reduce(
    (s, r) => s + (r.impact?.estimated_capex ?? 0), 0)
  return {
    total_kgco2e: hotspots.total_emissions_kgco2e,
    largest_hotspot: hotspots.hotspots[0] ?? null,
    data_quality_score: hotspots.data_quality_score,
    potential_reduction_kgco2e: potentialReduction,
    potential_annual_saving: potentialSaving,
    total_capex: totalCapex,
    budget_limit: recs.budget_limit,
    empty_state: hotspots.hotspots.length === 0
  }
}

// O-frontend fallback math (Module K rules); used when K1 is unavailable.
export function simulateAdoption(
  baseline: number,
  items: Array<{ co2: number; saving: number; capex: number; adoption: number }>
) {
  let co2 = 0, saving = 0, capex = 0
  for (const it of items) {
    const f = Math.min(100, Math.max(0, it.adoption)) / 100
    co2 += it.co2 * f
    saving += it.saving * f
    capex += it.capex * f
  }
  const projected = Math.max(0, baseline - co2)
  return {
    baseline_emissions_kg: baseline,
    projected_emissions_kg: projected,
    total_co2_saving_kg: baseline - projected,
    reduction_percent: baseline > 0 ? ((baseline - projected) / baseline) * 100 : 0,
    total_capex: capex,
    annual_saving: saving,
    payback_years: saving > 0 ? capex / saving : null
  }
}

/** Legacy badge helper (kept for pages that still call it). */
export function usePhase2ModeLabel(): string {
  const mode = resolveMockMode()
  if (mode === 'mock') return 'DEMO DATA (USE_MOCK_DATA=true)'
  if (mode === 'live') return 'LIVE API (USE_MOCK_DATA=false)'
  return 'LIVE API · AUTO-FALLBACK'
}