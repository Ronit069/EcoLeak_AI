// EcoLeak AI — global app context: identity, mode, fallbacks, selection, health.
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode,
} from 'react'
import {
  DEMO_IDS, clearAuth, fetchContext, fetchHealth, getAuth, getFallbackGroups, getIdentity,
  resolveMockMode, setAuth, setIdentity as persistIdentity, setMockMode, subscribeFallbacks,
  subscribeMode, type Identity, type MockMode, type StoredAuth,
} from '../lib/api'
import type { BootstrapIds, Facility, ReportingPeriod } from '../lib/types'

export interface Selection {
  processId: string | null
  hotspotId: string | null
  recommendationId: string | null
}

interface AppState {
  ids: BootstrapIds
  facilities: Facility[]
  periods: ReportingPeriod[]
  ready: boolean
  authed: boolean
  login: (auth: StoredAuth) => void
  logout: () => void
  mode: MockMode
  setMode: (m: MockMode) => void
  fallbacks: string[]
  identity: Identity
  setIdentity: (i: Partial<Identity>) => void
  health: { status?: string; components?: Record<string, string> } | null
  selection: Selection
  select: (patch: Partial<Selection>) => void
  setFacility: (facilityId: string) => void
  setPeriod: (periodId: string) => void
  commandCenter: boolean
  setCommandCenter: (open: boolean) => void
  refreshKey: number
  refresh: () => void
}

const Ctx = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<BootstrapIds>(DEMO_IDS)
  const [facilities, setFacilities] = useState<Facility[]>([])
  const [periods, setPeriods] = useState<ReportingPeriod[]>([])
  const [ready, setReady] = useState(false)
  const [mode, setModeState] = useState<MockMode>(resolveMockMode())
  const [fallbacks, setFallbacks] = useState<string[]>(getFallbackGroups())
  const [identity, setIdentityState] = useState<Identity>(getIdentity())
  const [health, setHealth] = useState<{ status?: string; components?: Record<string, string> } | null>(null)
  const [selection, setSelection] = useState<Selection>({ processId: null, hotspotId: null, recommendationId: null })
  const [refreshKey, setRefreshKey] = useState(0)
  const [authed, setAuthed] = useState<boolean>(() => getAuth() !== null)
  const [commandCenter, setCommandCenter] = useState(false)

  useEffect(() => subscribeMode(() => setModeState(resolveMockMode())), [])
  useEffect(() => subscribeFallbacks(() => setFallbacks(getFallbackGroups())), [])

  useEffect(() => {
    let alive = true
    setReady(false)
    fetchContext()
      .then(({ data, source }) => {
        if (!alive) return
        const facs = data.facilities ?? []
        const prds = data.reporting_periods ?? []
        setFacilities(facs)
        setPeriods(prds)
        const next: BootstrapIds = source === 'live' && facs.length
          ? {
              organization_id: data.organization?.id ?? DEMO_IDS.organization_id,
              facility_id: facs[0].id,
              reporting_period_id: prds[0]?.id ?? DEMO_IDS.reporting_period_id,
            }
          : DEMO_IDS
        setIds(next)
        setIdentityState((prev) => {
          if (!prev.organizationId && next.organization_id) {
            const merged = { organizationId: next.organization_id, role: prev.role }
            persistIdentity(merged)
            return merged
          }
          return prev
        })
      })
      .catch(() => { if (alive) setIds(DEMO_IDS) })
      .finally(() => { if (alive) setReady(true) })
    fetchHealth().then((h) => { if (alive) setHealth(h) }).catch(() => { if (alive) setHealth(null) })
    return () => { alive = false }
  }, [refreshKey])

  const setMode = useCallback((m: MockMode) => { setMockMode(m); setModeState(m) }, [])
  const setIdentity = useCallback((patch: Partial<Identity>) => {
    setIdentityState((prev) => {
      const next = { ...prev, ...patch }
      persistIdentity(next)
      return next
    })
  }, [])
  const select = useCallback((patch: Partial<Selection>) => {
    setSelection((prev) => ({ ...prev, ...patch }))
  }, [])
  const setFacility = useCallback((facilityId: string) => {
    setIds((prev) => ({ ...prev, facility_id: facilityId }))
  }, [])
  const setPeriod = useCallback((periodId: string) => {
    setIds((prev) => ({ ...prev, reporting_period_id: periodId }))
  }, [])
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), [])
  const login = useCallback((auth: StoredAuth) => {
    setAuth(auth)
    setIdentityState({ organizationId: auth.organizationId, role: auth.role })
    setAuthed(true)
    setRefreshKey((k) => k + 1)
  }, [])
  const logout = useCallback(() => {
    clearAuth()
    setAuthed(false)
  }, [])

  const value = useMemo<AppState>(() => ({
    ids, facilities, periods, ready, authed, login, logout, mode, setMode, fallbacks, identity, setIdentity, health,
    selection, select, setFacility, setPeriod, commandCenter, setCommandCenter, refreshKey, refresh,
  }), [ids, facilities, periods, ready, authed, login, logout, mode, setMode, fallbacks, identity, setIdentity, health, selection, select, setFacility, setPeriod, commandCenter, refreshKey, refresh])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp(): AppState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
