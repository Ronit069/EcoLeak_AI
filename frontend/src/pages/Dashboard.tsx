import { useEffect, useState } from 'react'
import {
  fetchActivities, fetchBootstrapIds, fetchDashboard, fetchDataset,
  fetchFacilityPeriods,
  fetchHotspots, fetchProcesses, fetchRecommendations, resetFallbacks,
  setFacilitySelection,
  subscribeFallbacks, subscribeMockMode, DEMO_IDS, type BootstrapIds,
  type DashboardPayload, type FacilityPeriod, type GroupResult, type Source,
} from '../lib/api'
import type {
  HotspotDetectionResult, MockDataset, RecommendationGenerationResult,
} from '../lib/contracts'
import { fmtKg, fmtINR, fmtPct, fmtTonnes } from '../lib/format'
import { HotspotRail } from '../components/HotspotRail'
import { RecommendationPlate } from '../components/RecommendationPlate'
import { SeverityBadge } from '../components/badges'
import { DrillMap } from '../components/DrillMap'
import { Pareto } from '../components/Pareto'
import { ScopeDonut } from '../components/ScopeDonut'
import { deriveDashboard } from '../lib/api'

export interface Phase1Data {
  dataset: MockDataset | null
  hotspots: HotspotDetectionResult | null
  recs: RecommendationGenerationResult | null
  dashboard: DashboardPayload | null
  processes: MockDataset['processes'] | null
  activities: MockDataset['activity_data'] | null
  ids: BootstrapIds
  facilities: MockDataset['facilities']
  facilityPeriods: FacilityPeriod[]
  sources: Record<string, Source | 'derived'>
  error: string | null
  ready: boolean
}

/**
 * Phase 2 bootstrap: resolve IDs from the live /api/context, then fetch each
 * endpoint group live-first with per-group mock fallback (auto mode).
 * One endpoint failing never blanks the UI — it falls back per group.
 */
export function usePhase1Data(selection?: { facility_id?: string; reporting_period_id?: string }) {
  const [data, setData] = useState<Phase1Data>({
    dataset: null, hotspots: null, recs: null, dashboard: null,
    processes: null, activities: null, ids: DEMO_IDS, facilities: [],
    facilityPeriods: [], sources: {}, error: null, ready: false,
  })

  useEffect(() => {
    let live = true
    const seen: Record<string, Source | 'derived'> = {}

    const run = async () => {
      resetFallbacks()
      try {
        const datasetR = await fetchDataset()
        seen.dataset = datasetR.source
        const baseIds = await fetchBootstrapIds()
        // P1-09: user selection overrides bootstrap ids (facility selector)
        const ids: BootstrapIds = {
          organization_id: baseIds.organization_id,
          facility_id: selection?.facility_id ?? baseIds.facility_id,
          reporting_period_id: selection?.reporting_period_id ?? baseIds.reporting_period_id,
        }

        const periodRows = await fetchFacilityPeriods(ids.facility_id)
        const [hotspotsR, recsR, processesR, activitiesR, dashboardR] = await Promise.allSettled([
          fetchHotspots(ids.facility_id, ids.reporting_period_id),
          fetchRecommendations(ids.facility_id, ids.reporting_period_id),
          fetchProcesses(ids.facility_id),
          fetchActivities(ids.facility_id, ids.reporting_period_id),
          fetchDashboard(ids.facility_id, ids.reporting_period_id),
        ])
        const take = <T,>(r: PromiseSettledResult<GroupResult<T>>, group: string): GroupResult<T> | null => {
          if (r.status === 'fulfilled') {
            seen[group] = r.value.source
            return r.value
          }
          seen[group] = 'derived'
          return null
        }
        const hotspots = take(hotspotsR, 'hotspots')
        const recs = take(recsR, 'recommendations')
        take(processesR, 'processes')
        take(activitiesR, 'activities')
        take(dashboardR, 'dashboard')

        if (!live) return
        setData({
          dataset: datasetR.data,
          hotspots: hotspots?.data ?? null,
          recs: recs?.data ?? null,
          dashboard: (dashboardR.status === 'fulfilled' && dashboardR.value.data) ? dashboardR.value.data : null,
          processes: processesR.status === 'fulfilled' ? processesR.value.data : datasetR.data.processes,
          activities: activitiesR.status === 'fulfilled' ? activitiesR.value.data : datasetR.data.activity_data,
          ids,
          facilities: datasetR.data.facilities,
          facilityPeriods: periodRows,
          sources: seen,
          error: null,
          ready: true,
        })
      } catch (err) {
        // Final safety net: everything mock, never a blank screen.
        if (!live) return
        const mock = await fetchDataset().catch(() => null)
        setData({
          dataset: mock?.data ?? null,
          hotspots: null, recs: null, dashboard: null,
          processes: mock?.data.processes ?? null,
          activities: mock?.data.activity_data ?? null,
          ids: DEMO_IDS,
          facilities: mock?.data.facilities ?? [],
          facilityPeriods: [],
          sources: seen,
          error: err instanceof Error ? err.message : String(err),
          ready: true,
        })
      }
    }
    run()

    const unsub1 = subscribeFallbacks(() => { if (live) setData(d => ({ ...d })) })
    const unsub2 = subscribeMockMode(() => { if (live) run() })
    return () => { live = false; unsub1(); unsub2() }
  }, [selection?.facility_id, selection?.reporting_period_id])

  return data
}

export function Loading() {
  return (
    <div style={{ display: 'grid', gap: 10 }} aria-busy="true" aria-label="Loading">
      <div className="skeleton" /><div className="skeleton" /><div className="skeleton" />
    </div>
  )
}

export function DashboardPage() {
  const [sel, setSel] = useState<{ facility_id?: string; reporting_period_id?: string }>({})
  const { dataset, hotspots, recs, dashboard, error, sources, ids, facilities, facilityPeriods, activities } =
    usePhase1Data(sel)
  const changeFacility = (facilityId: string) => {
    setFacilitySelection(facilityId)
    setSel({ facility_id: facilityId })
  }
  const changePeriod = (periodId: string) => {
    setFacilitySelection(ids.facility_id, periodId)
    setSel(s => ({ ...s, facility_id: ids.facility_id, reporting_period_id: periodId }))
  }
  if (error) return <div className="notice"><b>Failed to load.</b> {error} — using cached/demo data where available.</div>
  if (!hotspots || !recs || !dataset) return <Loading />

  // N1 live when available; otherwise derive from (live or fallen-back) data.
  const derived = deriveDashboard(hotspots, recs)
  const n1Largest = dashboard?.largest_hotspot as
    | (Partial<typeof derived.largest_hotspot> & { severity?: string })
    | null
  const dash = {
    total_kgco2e: dashboard?.total_kgco2e ?? derived.total_kgco2e,
    carbon_intensity: dashboard?.carbon_intensity ?? derived.largest_hotspot?.carbon_intensity ?? null,
    largest_hotspot: n1Largest ?? derived.largest_hotspot,
    circularity_score: dashboard?.circularity_score ?? null,
    potential_reduction_kgco2e: dashboard?.potential_reduction_kgco2e ?? derived.potential_reduction_kgco2e,
    potential_annual_saving: dashboard?.potential_annual_saving ?? derived.potential_annual_saving,
    data_quality_score: derived.data_quality_score,
    budget_limit: derived.budget_limit,
    total_capex: derived.total_capex,
    empty_state: dashboard?.empty_state ?? derived.empty_state,
    unresolved_count: dashboard?.unresolved_count ?? 0,
  }
  const facility = dataset.facilities.find(f => f.id === ids.facility_id) ?? dataset.facilities[0]
  const period = dataset.reporting_periods.find(p => p.id === ids.reporting_period_id) ?? dataset.reporting_periods[0]
  // P1-01 (final): the boundary of the headline number is now explicit and
  // DERIVED from the data source, never assumed:
  //   N1 live  -> all-scope footprint (S1+S2+S3)
  //   derived  -> operational boundary (Scope 1+2, the hotspot denominator)
  const isAllScope = dashboard != null
  const scopeLabel = isAllScope
    ? 'All scopes (Scope 1 + 2 + 3)'
    : (hotspots.scope_boundary?.length > 0
        ? hotspots.scope_boundary.join(' + ').replace(/_/g, ' ')
        : 'Scope 1 + 2 (default boundary)')
  // P1-01: the N1 total includes Scope 3; hotspot shares are relative to the
  // operational (Scope 1+2) boundary. Keep both visible so neither is misread.
  const operationalKg = hotspots.total_emissions_kgco2e
  const recsAreMock = sources.recommendations === 'mock'
  const reductionPct =
    dash.total_kgco2e > 0
      ? `${(((dash.potential_reduction_kgco2e ?? 0) / dash.total_kgco2e) * 100).toFixed(1)}% of baseline`
      : 'baseline unavailable'

  const actionableId = dashboard?.top_actionable_hotspot_id ?? null
  const actionable = actionableId
    ? (hotspots.hotspots.find(h => h.id === actionableId) ?? null)
    : null

  return (
    <>
      {facilities.length > 0 && facilityPeriods.length > 0 && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }} aria-label="Facility and period selector">
          <label style={{ fontSize: '.8rem' }}>
            Facility
            <select
              value={ids.facility_id}
              onChange={e => changeFacility(e.target.value)}
              style={{ marginLeft: 8, font: 'inherit', padding: '5px 8px', borderRadius: 8, border: '1px solid var(--line-strong)' }}
            >
              {facilities.map(f => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: '.8rem' }}>
            Period
            <select
              value={ids.reporting_period_id}
              onChange={e => changePeriod(e.target.value)}
              style={{ marginLeft: 8, font: 'inherit', padding: '5px 8px', borderRadius: 8, border: '1px solid var(--line-strong)' }}
            >
              {facilityPeriods.map(p => (
                <option key={p.id} value={p.id}>{p.period_type} {p.start_date} → {p.end_date} ({p.status})</option>
              ))}
            </select>
          </label>
          <span style={{ fontSize: '.74rem', color: 'var(--legend)' }}>
            Data for {facilities.length} facilit{(facilities.length === 1 ? 'y' : 'ies')} × {facilityPeriods.length} period{(facilityPeriods.length === 1 ? '' : 's')} (P1-09)
          </span>
        </div>
      )}
      {actionable && (
        <div role="status" className="notice" style={{ border: '1px solid var(--accent)', marginBottom: 14 }}>
          <b>Best intervention target: {actionable.process_name ?? 'process'} (rank {actionable.rank})</b>
          {' '}— the largest leak ({dash.largest_hotspot?.process_name ?? '—'}) is NOT automatically the best
          action target; {actionable.process_name ?? 'it'} has the highest improvement potential
          ({actionable.improvement_potential_score ?? '—'}/100).
        </div>
      )}
      <div className="page-head">
        <div>
          <h1>Carbon leak bench</h1>
          <p>{facility?.name ?? 'Facility'} · {period?.start_date ?? '—'} → {period?.end_date ?? '—'} · {scopeLabel}</p>
          {dataset.facilities.length > 1 && (
            <select
              aria-label="Facility"
              value={facility?.id ?? ''}
              onChange={e => { setFacilitySelection(e.target.value); window.location.reload() }}
              style={{ marginTop: 6, fontSize: '.82rem', maxWidth: 360 }}
            >
              {dataset.facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          )}
        </div>
        <span className="provenance">
          {dashboard ? 'N1 live' : 'N1 derived'} · total {fmtKg(dash.total_kgco2e)} · hotspot data quality {dash.data_quality_score ?? '—'}/100
        </span>
      </div>

      {dash.unresolved_count > 0 && (
        <div className="notice" role="status">
          <b>{dash.unresolved_count} unresolved activit{dash.unresolved_count === 1 ? 'y' : 'ies'}.</b> No
          emission factor matched, so {dash.unresolved_count === 1 ? 'it is' : 'they are'} excluded from every
          total below — provenance is incomplete for these rows.
        </div>
      )}

      <div className="instrument-strip panel" role="region" aria-label="Key instruments" style={{ marginBottom: 18 }}>
        <div className="gauge">
          <div className="gauge-label">{isAllScope ? 'TOTAL FOOTPRINT (ALL SCOPES)' : 'TOTAL EMISSIONS (SCOPE 1+2)'}</div>
          <div className="gauge-value">{fmtTonnes(dash.total_kgco2e)}</div>
          <div className="gauge-sub">
            {isAllScope
              ? `S1 ${fmtKg(dashboard?.scope_breakdown.SCOPE_1 ?? 0)} · S2 ${fmtKg(dashboard?.scope_breakdown.SCOPE_2 ?? 0)} · S3 ${fmtKg(dashboard?.scope_breakdown.SCOPE_3 ?? 0)} · operational (S1+S2) ${fmtKg(operationalKg)}`
              : `${fmtKg(dash.total_kgco2e)} · hotspot shares use this same denominator`}
            {' '}· {dash.empty_state ? 'no data yet' : 'computed'}
          </div>
        </div>
        <div className="gauge">
          <div className="gauge-label">CARBON INTENSITY</div>
          <div className="gauge-value" style={{ fontSize: '1.15rem' }}>
            {dashboard?.carbon_intensity != null ? Number(dashboard.carbon_intensity).toFixed(1) : (dash.largest_hotspot?.carbon_intensity?.toFixed(1) ?? '—')}
          </div>
          <div className="gauge-sub">kgCO₂e / unit · {dashboard ? 'from N1' : 'proxy from largest hotspot'}</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">LARGEST LEAK</div>
          <div className="gauge-value" style={{ fontSize: '1.05rem' }}>
            #{dash.largest_hotspot?.rank ?? '—'} {dash.largest_hotspot?.process_name ?? 'none yet'}
          </div>
          <div className="gauge-sub">{fmtPct(dash.largest_hotspot?.contribution_percent)} of Scope 1+2 · {fmtKg(dash.largest_hotspot?.emissions_kgco2e)}</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">CIRCULARITY SCORE</div>
          <div className="gauge-value" style={{ fontSize: '1.15rem' }}>
            {dashboard?.circularity_score != null ? Number(dashboard.circularity_score).toFixed(1) : 'Unavailable'}
          </div>
          <div className="gauge-sub">Module L — shown when L1 provides a value</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">POTENTIAL REDUCTION</div>
          <div className="gauge-value">{fmtTonnes(dash.potential_reduction_kgco2e)}</div>
          <div className="gauge-sub">{reductionPct} · across ranked recs{recsAreMock ? ' (demo recs)' : ''}</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">POTENTIAL SAVING</div>
          <div className="gauge-value">{fmtINR(dash.potential_annual_saving)}</div>
          <div className="gauge-sub">Budget {fmtINR(dash.budget_limit)} · CAPEX {fmtINR(dash.total_capex)}{recsAreMock ? ' · demo recs' : ''}</div>
        </div>
      </div>

      <div className="split">
        <section aria-labelledby="hotspots-h">
          <h2 id="hotspots-h">Leak points, ranked</h2>
          <HotspotRail items={hotspots.hotspots} />
          <div className="panel panel-pad" style={{ marginTop: 14 }}>
            <h3>Carbon leak map (D3 drill-down)</h3>
            <p style={{ fontSize: '.84rem', color: 'var(--legend-ink)', marginTop: 0 }}>
              Facility → process → activity. N2 links stay <span className="mono">[]</span> in Phase 2 unless P4 serves them.
            </p>
            {/* BUG-4-06: live mode's /api/context dataset has no activity_data; use
                the separately-fetched activities group (live or fallback). */}
            <DrillMap
              dataset={{ ...dataset, activity_data: activities ?? dataset.activity_data }}
              hotspots={hotspots}
            />
            <Pareto items={hotspots.hotspots} />
            <h4 style={{ margin: '14px 0 6px' }}>Scope breakdown</h4>
            <ScopeDonut breakdown={dashboard?.scope_breakdown} total={dash.total_kgco2e} />
            <details>
              <summary className="link" style={{ cursor: 'pointer', fontSize: '.85rem' }}>Sequential rail + tabular fallback</summary>
              <div className="leak-rail">
                {hotspots.hotspots.map(h => (
                  <div key={h.id} className="leak-node">
                    <div
                      className="leak-dot"
                      style={{
                        width: 30 + (h.contribution_percent != null ? h.contribution_percent * 0.5 : 0),
                        height: 30 + (h.contribution_percent != null ? h.contribution_percent * 0.5 : 0)
                      }}
                      aria-hidden="true"
                    >
                      {h.rank}
                    </div>
                    <div>
                      <b>{h.process_name}</b> · <span className="mono">{fmtKg(h.emissions_kgco2e)} · {h.contribution_percent != null ? fmtPct(h.contribution_percent) : 'share unavailable'}</span>{' '}
                      <SeverityBadge severity={h.severity} />
                      <div style={{ fontSize: '.8rem', color: 'var(--legend)' }}>{h.activity_category ?? '—'} · intensity {h.carbon_intensity ?? '—'}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="table-wrap" style={{ marginTop: 10 }}>
                <table className="data">
                  <thead><tr><th>Rank</th><th>Process</th><th className="n">Emissions</th><th className="n">Share</th><th>Severity</th></tr></thead>
                  <tbody>
                    {hotspots.hotspots.map(h => (
                      <tr key={h.id}><td className="mono">{h.rank}</td><td>{h.process_name}</td>
                        <td className="n mono">{h.emissions_kgco2e.toLocaleString('en-IN')}</td>
                        <td className="n mono">{h.contribution_percent != null ? h.contribution_percent.toFixed(1) : '—'}%</td><td>{h.severity}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </section>

        <aside aria-labelledby="top-recs-h">
          <h2 id="top-recs-h">Act first</h2>
          {recs.recommendations.slice(0, 3).map(r => <RecommendationPlate key={r.id} rec={r} />)}
          <div className="notice">
            Ranked by weighted score (0.30 carbon + 0.25 financial + 0.15 feasibility + 0.15 circularity +
            0.10 speed + 0.05 confidence) — not carbon alone. Live J2 ranks the full 19-entry library.
            {recsAreMock ? ' Showing demo recommendations (live J2 unavailable).' : ''}
          </div>
        </aside>
      </div>
    </>
  )
}