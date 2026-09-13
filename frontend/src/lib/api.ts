// EcoLeak AI — data layer. Live-first with per-group mock fallback (auto mode).
// Mode precedence: localStorage 'ecoleak.useMockData' -> VITE_USE_MOCK_DATA
// -> VITE_USE_MOCKS -> 'auto'. See UI_REDESIGN_REQUIREMENTS.md §2.1/§7.
import type {
  ActivityData, BootstrapIds, CircularityScore, ContextPayload, DashboardPayload,
  DataQuality, EmissionFactor, ExplanationPayload, Facility, HotspotResult, ImportJob,
  InventorySummary, LeakMapPayload, NormalizeResult, Organization, Process,
  RecommendationResult, ReportReceipt, ScenarioEnvelope,
} from './types'
import {
  dashboardSchema, hotspotResultSchema, normalizeResultSchema, recommendationResultSchema,
} from './schemas'

const API_URL: string = import.meta.env.VITE_API_URL ?? ''
const API_TOKEN: string = import.meta.env.VITE_API_TOKEN ?? ''

export type MockMode = 'auto' | 'mock' | 'live'
export type Source = 'live' | 'mock'

export const DEMO_IDS: BootstrapIds = {
  organization_id: '0a1b2c3d-0001-4001-8001-000000000001',
  facility_id: '0a1b2c3d-0002-4002-8002-000000000002',
  reporting_period_id: '0a1b2c3d-0003-4003-8003-000000000003',
}

// ---------------------------------------------------------------------------
// Mode + fallback registry
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'ecoleak.useMockData'
const modeListeners = new Set<() => void>()

export function resolveMockMode(): MockMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'mock' || stored === 'live' || stored === 'auto') return stored
  } catch { /* ignore */ }
  const v2 = import.meta.env.VITE_USE_MOCK_DATA?.toLowerCase()
  if (v2 === 'true') return 'mock'
  if (v2 === 'false') return 'live'
  if (v2 === 'auto') return 'auto'
  const legacy = import.meta.env.VITE_USE_MOCKS?.toLowerCase()
  if (legacy !== undefined) return legacy === 'false' ? 'live' : 'mock'
  return 'auto'
}

export function setMockMode(mode: MockMode): void {
  try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* ignore */ }
  modeListeners.forEach((l) => l())
}
export function subscribeMode(cb: () => void): () => void {
  modeListeners.add(cb)
  return () => modeListeners.delete(cb)
}

const fallbackGroups: string[] = []
const fallbackListeners = new Set<() => void>()
export function getFallbackGroups(): string[] { return [...fallbackGroups] }
export function subscribeFallbacks(cb: () => void): () => void {
  fallbackListeners.add(cb)
  return () => fallbackListeners.delete(cb)
}
function recordFallback(group: string): void {
  if (!fallbackGroups.includes(group)) { fallbackGroups.push(group); fallbackListeners.forEach((l) => l()) }
}
export function resetFallbacks(): void {
  if (fallbackGroups.length) { fallbackGroups.length = 0; fallbackListeners.forEach((l) => l()) }
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number
  readonly errorCode?: string
  constructor(status: number, message: string, errorCode?: string) {
    super(message); this.status = status; this.errorCode = errorCode
  }
}

const TIMEOUT_MS = 5000

function withTimeout(): { signal: AbortSignal; clear: () => void } {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(new DOMException('timeout', 'TimeoutError')), TIMEOUT_MS)
  return { signal: ctrl.signal, clear: () => clearTimeout(t) }
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...(extra ?? {}) }
  const token = getToken()
  if (token) h.Authorization = `Bearer ${token}`
  // Stub-mode identity (UI_REDESIGN_REQUIREMENTS.md §3). Bearer token wins in JWT mode.
  try {
    const org = localStorage.getItem('ecoleak.organizationId')
    const role = localStorage.getItem('ecoleak.role')
    if (org) h['X-Organization-Id'] = org
    if (role) h['X-Role'] = role
  } catch { /* ignore */ }
  return h
}

export interface Identity { organizationId: string; role: string }

export function getIdentity(): Identity {
  try {
    return {
      organizationId: localStorage.getItem('ecoleak.organizationId') ?? '',
      role: localStorage.getItem('ecoleak.role') ?? 'SUSTAINABILITY_ANALYST',
    }
  } catch {
    return { organizationId: '', role: 'SUSTAINABILITY_ANALYST' }
  }
}

export function setIdentity(identity: Partial<Identity>): void {
  try {
    if (identity.organizationId !== undefined) localStorage.setItem('ecoleak.organizationId', identity.organizationId)
    if (identity.role !== undefined) localStorage.setItem('ecoleak.role', identity.role)
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Session (login gate)
// ---------------------------------------------------------------------------

export type AuthMethod = 'stub' | 'jwt'

export interface StoredAuth {
  method: AuthMethod
  organizationId: string
  role: string
  token: string
}

const AUTH_KEY = 'ecoleak.auth'

export function getToken(): string {
  try {
    return localStorage.getItem('ecoleak.token') || API_TOKEN
  } catch {
    return API_TOKEN
  }
}

export function getAuth(): StoredAuth | null {
  try {
    const method = localStorage.getItem(AUTH_KEY)
    if (method !== 'stub' && method !== 'jwt') return null
    const id = getIdentity()
    return { method, organizationId: id.organizationId, role: id.role, token: getToken() }
  } catch {
    return null
  }
}

export function setAuth(auth: StoredAuth): void {
  try {
    localStorage.setItem(AUTH_KEY, auth.method)
    localStorage.setItem('ecoleak.organizationId', auth.organizationId)
    localStorage.setItem('ecoleak.role', auth.role)
    localStorage.setItem('ecoleak.token', auth.token)
  } catch { /* ignore */ }
}

export function clearAuth(): void {
  try {
    localStorage.removeItem(AUTH_KEY)
    localStorage.removeItem('ecoleak.token')
  } catch { /* ignore */ }
}

/** Live auth probe (NO mock fallback) so 401/403 surface to the login screen. */
export async function probeAuth(): Promise<ContextPayload> {
  return getJson<ContextPayload>(`${API_URL}/api/context`)
}

async function handle<T>(res: Response, url: string): Promise<T> {
  if (res.status === 401) {
    throw new ApiError(401, 'Authentication required — set VITE_API_TOKEN or check AUTH_MODE.', 'UNAUTHORIZED')
  }
  if (!res.ok) {
    let code: string | undefined
    let message = `Request failed: ${res.status} ${url}`
    try {
      const body = (await res.json()) as { error_code?: string; message?: string }
      code = body.error_code
      if (body.message) message = body.message
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, message, code)
  }
  const ct = res.headers.get('content-type') ?? ''
  if (ct.includes('text/html')) {
    // SPA fallback HTML from a non-API origin is a failed live call.
    throw new ApiError(500, `Not an API response: ${url}`, 'NOT_JSON')
  }
  return res.json() as Promise<T>
}

export async function getJson<T>(url: string): Promise<T> {
  const { signal, clear } = withTimeout()
  const res = await fetch(url, { headers: authHeaders(), signal }).finally(clear)
  return handle<T>(res, url)
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const { signal, clear } = withTimeout()
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal,
  }).finally(clear)
  return handle<T>(res, url)
}

export async function patchJson<T>(url: string, body: unknown): Promise<T> {
  const { signal, clear } = withTimeout()
  const res = await fetch(url, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal,
  }).finally(clear)
  return handle<T>(res, url)
}

export async function postForm<T>(url: string, form: FormData): Promise<T> {
  const { signal, clear } = withTimeout()
  const res = await fetch(url, { method: 'POST', headers: authHeaders(), body: form, signal }).finally(clear)
  return handle<T>(res, url)
}

export interface GroupResult<T> { data: T; source: Source; group: string }

export async function liveOrMock<T>(
  group: string,
  liveFetch: () => Promise<T>,
  mockFetch: () => Promise<T>,
): Promise<GroupResult<T>> {
  const mode = resolveMockMode()
  if (mode === 'mock') return { data: await mockFetch(), source: 'mock', group }
  if (mode === 'live') return { data: await liveFetch(), source: 'live', group }
  try {
    return { data: await liveFetch(), source: 'live', group }
  } catch {
    recordFallback(group)
    return { data: await mockFetch(), source: 'mock', group }
  }
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

interface RawMockDataset {
  organization: Organization
  facilities: Facility[]
  reporting_periods: ContextPayload['reporting_periods']
  processes: Process[]
  activity_data: ActivityData[]
  emission_factors: EmissionFactor[]
}

async function mockDataset(): Promise<RawMockDataset> {
  return getJson<RawMockDataset>('/mocks/mock_dataset.json')
}

export async function fetchContext(): Promise<GroupResult<ContextPayload & { processes?: Process[] }>> {
  return liveOrMock(
    'dataset',
    () => getJson<ContextPayload>(`${API_URL}/api/context`),
    async () => {
      const d = await mockDataset()
      return { organization: d.organization, facilities: d.facilities, reporting_periods: d.reporting_periods }
    },
  )
}

export async function fetchBootstrapIds(): Promise<BootstrapIds> {
  try {
    const { data, source } = await fetchContext()
    if (source === 'live' && data.facilities.length) {
      return {
        organization_id: data.organization?.id ?? DEMO_IDS.organization_id,
        facility_id: data.facilities[0].id,
        reporting_period_id: data.reporting_periods[0]?.id ?? DEMO_IDS.reporting_period_id,
      }
    }
  } catch { /* fall through */ }
  return DEMO_IDS
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export async function fetchProcesses(facilityId: string): Promise<GroupResult<Process[]>> {
  return liveOrMock(
    'processes',
    () => getJson<Process[]>(`${API_URL}/api/facilities/${facilityId}/processes`),
    async () => (await mockDataset()).processes,
  )
}

export async function fetchActivities(facilityId: string, periodId: string): Promise<GroupResult<ActivityData[]>> {
  return liveOrMock(
    'activities',
    () => getJson<ActivityData[]>(`${API_URL}/api/facilities/${facilityId}/activity?reporting_period_id=${periodId}`),
    async () => (await mockDataset()).activity_data,
  )
}

export interface ActivityCreateBody {
  reporting_period_id: string
  process_id?: string | null
  activity_category: string
  activity_subcategory: string
  source_name?: string | null
  original_value: string
  original_unit: string
  data_source_type?: string
  measured_or_estimated?: string
  confidence_score?: string | null
  notes?: string | null
}

export async function createActivity(facilityId: string, body: ActivityCreateBody): Promise<ActivityData> {
  return postJson<ActivityData>(`${API_URL}/api/facilities/${facilityId}/activity`, body)
}

export async function fetchFactors(): Promise<EmissionFactor[]> {
  return getJson<EmissionFactor[]>(`${API_URL}/api/emission-factors`)
}

export async function fetchHotspots(facilityId: string, periodId: string): Promise<GroupResult<HotspotResult>> {
  return liveOrMock(
    'hotspots',
    async () => hotspotResultSchema.parse(await getJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/hotspots`)) as unknown as HotspotResult,
    async () => hotspotResultSchema.parse(await getJson<unknown>('/mocks/mock_hotspot_output.json')) as unknown as HotspotResult,
  )
}

export async function fetchLeakMap(facilityId: string, periodId: string): Promise<GroupResult<LeakMapPayload>> {
  return liveOrMock(
    'leak-map',
    () => getJson<LeakMapPayload>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/leak-map`),
    async () => {
      const { data } = await fetchHotspots(facilityId, periodId)
      return {
        nodes: data.hotspots.map((h) => ({
          process_id: h.process_id, process_name: h.process_name,
          emissions_kgco2e: h.emissions_kgco2e, contribution_percent: h.contribution_percent,
          severity: h.severity,
        })),
        links: [],
      }
    },
  )
}

export async function fetchRecommendations(facilityId: string, periodId: string): Promise<GroupResult<RecommendationResult>> {
  return liveOrMock(
    'recommendations',
    async () => recommendationResultSchema.parse(await getJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/recommendations`)) as unknown as RecommendationResult,
    async () => recommendationResultSchema.parse(await getJson<unknown>('/mocks/mock_recommendation_output.json')) as unknown as RecommendationResult,
  )
}

export async function fetchExplanation(recommendationId: string): Promise<GroupResult<ExplanationPayload | null>> {
  return liveOrMock(
    'explanation',
    () => getJson<ExplanationPayload>(`${API_URL}/api/recommendations/${recommendationId}/explanation`),
    async () => null,
  )
}

export async function fetchDashboard(facilityId: string, periodId: string): Promise<GroupResult<DashboardPayload | null>> {
  return liveOrMock(
    'dashboard',
    async () => dashboardSchema.parse(await getJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/dashboard`)) as unknown as DashboardPayload,
    async () => null,
  )
}

export async function fetchInventory(facilityId: string, periodId: string): Promise<InventorySummary> {
  return getJson<InventorySummary>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/inventory-summary`)
}

export async function fetchCircularity(facilityId: string, periodId: string): Promise<CircularityScore> {
  return getJson<CircularityScore>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/circularity-score`)
}

export async function fetchDataQuality(facilityId: string, periodId: string): Promise<DataQuality> {
  return getJson<DataQuality>(`${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/data-quality`)
}

export async function normalizeUnit(value: string, fromUnit: string, toUnit: string): Promise<NormalizeResult> {
  const raw = await postJson<unknown>(`${API_URL}/api/units/normalize`, { value, from_unit: fromUnit, to_unit: toUnit })
  return normalizeResultSchema.parse(raw) as unknown as NormalizeResult
}

export interface ImportOptions { file: File; facilityId: string; periodId: string; sheet?: string; dryRun?: boolean }

export async function importActivities(opts: ImportOptions): Promise<ImportJob> {
  const form = new FormData()
  form.append('file', opts.file)
  form.append('reporting_period_id', opts.periodId)
  if (opts.sheet) form.append('sheet', opts.sheet)
  form.append('dry_run', String(opts.dryRun ?? true))
  return postForm<ImportJob>(`${API_URL}/api/facilities/${opts.facilityId}/activity/import`, form)
}

export async function fetchImportJob(importId: string): Promise<ImportJob> {
  return getJson<ImportJob>(`${API_URL}/api/ingestion/batches/${importId}`)
}

export async function generateReport(facilityId: string, periodId: string, templateVersion: string, includeScope3: boolean): Promise<ReportReceipt> {
  return postJson<ReportReceipt>(
    `${API_URL}/api/facilities/${facilityId}/reporting-periods/${periodId}/reports`,
    { template_version: templateVersion, include_scope3: includeScope3 },
  )
}

export interface ReportRecord extends ReportReceipt { payload: Record<string, unknown> }

export async function fetchReport(reportId: string): Promise<ReportRecord> {
  return getJson<ReportRecord>(`${API_URL}/api/reports/${reportId}`)
}

export async function listReports(facilityId: string, periodId: string): Promise<ReportReceipt[]> {
  return getJson<ReportReceipt[]>(`${API_URL}/api/reports?facility_id=${facilityId}&reporting_period_id=${periodId}`)
}

export function reportExportUrl(reportId: string, format: 'json' | 'csv' | 'pdf'): string {
  return `${API_URL}/api/reports/${reportId}/export?format=${format}`
}

export interface SimSelection { intervention_id: string; adoption_percentage: number; selected: boolean }

export async function simulate(
  facilityId: string, periodId: string, selections: SimSelection[], budgetLimit?: number,
): Promise<ScenarioEnvelope> {
  return postJson<ScenarioEnvelope>(
    `${API_URL}/api/scenarios/00000000-0000-4000-8000-000000000000/simulate`,
    {
      facility_id: facilityId,
      reporting_period_id: periodId,
      interventions: selections,
      ...(budgetLimit !== undefined ? { budget_limit: String(budgetLimit) } : {}),
    },
  )
}

export async function patchRecommendation(id: string, status: string): Promise<unknown> {
  return patchJson<unknown>(`${API_URL}/api/recommendations/${id}`, { status })
}

export async function submitFeedback(id: string, body: Record<string, unknown>): Promise<unknown> {
  return postJson<unknown>(`${API_URL}/api/recommendations/${id}/feedback`, body)
}

export async function fetchFeedbackHistory(id: string): Promise<unknown> {
  return getJson<unknown>(`${API_URL}/api/recommendations/${id}/feedback`)
}

export async function fetchHealth(): Promise<{ status?: string; components?: Record<string, string> }> {
  return getJson(`${API_URL}/api/health`)
}

// ---------------------------------------------------------------------------
// Module A/B maintenance (used by the onboarding wizard)
// ---------------------------------------------------------------------------

export async function createOrganization(body: Record<string, unknown>): Promise<Organization> {
  return postJson<Organization>(`${API_URL}/api/organizations`, body)
}
export async function createFacility(body: Record<string, unknown>): Promise<Facility> {
  return postJson<Facility>(`${API_URL}/api/facilities`, body)
}
export async function createReportingPeriod(facilityId: string, body: Record<string, unknown>): Promise<unknown> {
  return postJson<unknown>(`${API_URL}/api/facilities/${facilityId}/reporting-periods`, body)
}
export async function createProcess(facilityId: string, body: Record<string, unknown>): Promise<unknown> {
  return postJson<unknown>(`${API_URL}/api/facilities/${facilityId}/processes`, body)
}
