import type {
  HotspotDetectionResult, RecommendationGenerationResult, MockDataset
} from './contracts'
import { hotspotResultSchema, recommendationResultSchema } from './zod'

// ---------------------------------------------------------------------------
// Mock-now / API-later data layer.
// Default: read frozen mocks from /mocks/*.json (Phase 1).
// Swap: set VITE_USE_MOCKS=false and VITE_API_URL to P2 live backend;
// only this file changes — components consume these hooks, never fetch paths.
// Live mapping: G2 hotspots, J2 recommendations, N1 dashboard, N2 leak-map.
// ---------------------------------------------------------------------------

const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false'
const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
const API_TOKEN = (import.meta.env.VITE_API_TOKEN as string | undefined) ?? ''

export const DEMO_IDS = {
  facility_id: '0a1b2c3d-0002-4002-8002-000000000002',
  reporting_period_id: '0a1b2c3d-0003-4003-8003-000000000003'
}

export class ApiError extends Error {
  readonly status: number
  readonly errorCode?: string
  constructor(status: number, message: string, errorCode?: string) {
    super(message)
    this.status = status
    this.errorCode = errorCode
  }
}

async function getJson<T>(url: string): Promise<T> {
  const headers: Record<string, string> = {}
  // Auth wiring (D1): when VITE_API_TOKEN is set, send it as a Bearer token;
  // flips from P2 stub auth to JWT without touching components.
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`
  const res = await fetch(url, { headers })
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
  return res.json() as Promise<T>
}

export async function fetchDataset(): Promise<MockDataset> {
  if (!USE_MOCKS) {
    // Merged API context endpoint (engine router) — field names match the mock file.
    return getJson<MockDataset>(`${API_URL}/api/context`)
  }
  return getJson<MockDataset>('/mocks/mock_dataset.json')
}

export async function fetchHotspots(
  facilityId = DEMO_IDS.facility_id, periodId = DEMO_IDS.reporting_period_id
): Promise<HotspotDetectionResult> {
  const raw = USE_MOCKS
    ? await getJson<unknown>('/mocks/mock_hotspot_output.json')
    : await getJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/hotspots`)
  return hotspotResultSchema.parse(raw)
}

export async function fetchRecommendations(
  facilityId = DEMO_IDS.facility_id, periodId = DEMO_IDS.reporting_period_id
): Promise<RecommendationGenerationResult> {
  const raw = USE_MOCKS
    ? await getJson<unknown>('/mocks/mock_recommendation_output.json')
    : await getJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/recommendations`)
  return recommendationResultSchema.parse(raw)
}

export function useMockBadge(): string {
  return USE_MOCKS ? 'MOCK · G2/J2 frozen' : 'LIVE API'
}

// Derived Phase 1 dashboard (replaced by N1 when live).
export function deriveDashboard(
  hotspots: HotspotDetectionResult,
  recs: RecommendationGenerationResult
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

// O-frontend prototype math (Module K rules): payback null when saving<=0,
// projected floored at 0. Mirrors simulator until K1 live.
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
