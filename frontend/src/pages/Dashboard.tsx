import { useEffect, useState } from 'react'
import {
  fetchActivities, fetchBootstrapIds, fetchDashboard, fetchDataset,
  fetchHotspots, fetchProcesses, fetchRecommendations, resetFallbacks,
  subscribeFallbacks, subscribeMockMode, DEMO_IDS, type BootstrapIds,
  type DashboardPayload, type GroupResult, type Source,
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
import { deriveDashboard } from '../lib/api'

export interface Phase1Data {
  dataset: MockDataset | null
  hotspots: HotspotDetectionResult | null
  recs: RecommendationGenerationResult | null
  dashboard: DashboardPayload | null
  processes: MockDataset['processes'] | null
  activities: MockDataset['activity_data'] | null
  ids: BootstrapIds
  sources: Record<string, Source | 'derived'>
  error: string | null
  ready: boolean
}

/**
 * Phase 2 bootstrap: resolve IDs from the live /api/context, then fetch each
 * endpoint group live-first with per-group mock fallback (auto mode).
 * One endpoint failing never blanks the UI — it falls back per group.
 */
export function usePhase1Data() {
  const [data, setData] = useState<Phase1Data>({
    dataset: null, hotspots: null, recs: null, dashboard: null,
    processes: null, activities: null, ids: DEMO_IDS,
    sources: {}, error: null, ready: false,
  })

  useEffect(() => {
    let live = true
    const seen: Record<string, Source | 'derived'> = {}

    const run = async () => {
      resetFallbacks()
      try {
        const datasetR = await fetchDataset()
        seen.dataset = datasetR.source
        const ids = await fetchBootstrapIds()

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
  }, [])

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
  const { dataset, hotspots, recs, dashboard, error } = usePhase1Data()
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
  }
  const facility = dataset.facilities[0]
  const period = dataset.reporting_periods[0]
  const scopeLabel =
    hotspots.scope_boundary?.length > 0
      ? hotspots.scope_boundary.join(' + ').replace(/_/g, ' ')
      : 'Scope 1 + 2 (default boundary)'

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Carbon leak bench</h1>
          <p>{facility?.name ?? 'Facility'} · {period?.start_date ?? '—'} → {period?.end_date ?? '—'} · {scopeLabel}</p>
        </div>
        <span className="provenance">
          {dashboard ? 'N1 live' : 'N1 derived'} · total {fmtKg(dash.total_kgco2e)} · quality {dash.data_quality_score ?? '—'}/100
        </span>
      </div>

      <div className="instrument-strip panel" role="region" aria-label="Key instruments" style={{ marginBottom: 18 }}>
        <div className="gauge">
          <div className="gauge-label">TOTAL EMISSIONS</div>
          <div className="gauge-value">{fmtTonnes(dash.total_kgco2e)}</div>
          <div className="gauge-sub">{fmtKg(dash.total_kgco2e)} · {dash.empty_state ? 'no data yet' : 'computed'}</div>
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
          <div className="gauge-sub">{fmtPct(dash.largest_hotspot?.contribution_percent)} of total · {fmtKg(dash.largest_hotspot?.emissions_kgco2e)}</div>
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
          <div className="gauge-sub">{fmtPct((dash.potential_reduction_kgco2e / dash.total_kgco2e) * 100)} of baseline · across ranked recs</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">POTENTIAL SAVING</div>
          <div className="gauge-value">{fmtINR(dash.potential_annual_saving)}</div>
          <div className="gauge-sub">Budget {fmtINR(dash.budget_limit)} · CAPEX {fmtINR(dash.total_capex)}</div>
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
            <DrillMap dataset={dataset} hotspots={hotspots} />
            <Pareto items={hotspots.hotspots} />
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
            0.10 speed + 0.05 confidence) — not carbon alone. Live J2 ranks the full library; the mock showed 5.
          </div>
        </aside>
      </div>
    </>
  )
}