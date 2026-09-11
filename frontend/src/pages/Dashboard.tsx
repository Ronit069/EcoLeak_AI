import { useEffect, useState } from 'react'
import { fetchDataset, fetchHotspots, fetchRecommendations, deriveDashboard, useMockBadge } from '../lib/api'
import type { HotspotDetectionResult, RecommendationGenerationResult, MockDataset } from '../lib/contracts'
import { fmtKg, fmtINR, fmtPct, fmtTonnes } from '../lib/format'
import { HotspotRail } from '../components/HotspotRail'
import { RecommendationPlate } from '../components/RecommendationPlate'
import { SeverityBadge } from '../components/badges'
import { DrillMap } from '../components/DrillMap'

export function usePhase1Data() {
  const [dataset, setDataset] = useState<MockDataset | null>(null)
  const [hotspots, setHotspots] = useState<HotspotDetectionResult | null>(null)
  const [recs, setRecs] = useState<RecommendationGenerationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    Promise.all([fetchDataset(), fetchHotspots(), fetchRecommendations()])
      .then(([d, h, r]) => { if (live) { setDataset(d); setHotspots(h); setRecs(r) } })
      .catch(e => { if (live) setError(e instanceof Error ? e.message : String(e)) })
    return () => { live = false }
  }, [])
  return { dataset, hotspots, recs, error }
}

export function Loading() {
  return (
    <div style={{ display: 'grid', gap: 10 }} aria-busy="true" aria-label="Loading">
      <div className="skeleton" /><div className="skeleton" /><div className="skeleton" />
    </div>
  )
}

export function DashboardPage() {
  const { dataset, hotspots, recs, error } = usePhase1Data()
  if (error) return <div className="notice"><b>Failed to load frozen mocks.</b> {error}</div>
  if (!hotspots || !recs || !dataset) return <Loading />
  const dash = deriveDashboard(hotspots, recs)
  const facility = dataset.facilities[0]
  const period = dataset.reporting_periods[0]

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Carbon leak bench</h1>
          <p>{facility.name} · {period.start_date} → {period.end_date} · Scope 1+2 operational</p>
        </div>
        <span className="provenance">{useMockBadge()} · total {fmtKg(dash.total_kgco2e)} · quality {dash.data_quality_score ?? '—'}/100</span>
      </div>

      <div className="instrument-strip panel" role="region" aria-label="Key instruments" style={{ marginBottom: 18 }}>
        <div className="gauge">
          <div className="gauge-label">TOTAL EMISSIONS</div>
          <div className="gauge-value">{fmtTonnes(dash.total_kgco2e)}</div>
          <div className="gauge-sub">565,050 kgCO₂e fixture · CEA/IPCC mock factors</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">CARBON INTENSITY</div>
          <div className="gauge-value" style={{ fontSize: '1.15rem' }}>{dash.largest_hotspot?.carbon_intensity?.toFixed(1) ?? '—'}</div>
          <div className="gauge-sub">kgCO₂e / unit · proxy from largest hotspot (facility-level awaits N1/F3)</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">LARGEST LEAK</div>
          <div className="gauge-value" style={{ fontSize: '1.05rem' }}>
            #{dash.largest_hotspot?.rank} {dash.largest_hotspot?.process_name}
          </div>
          <div className="gauge-sub">{fmtPct(dash.largest_hotspot?.contribution_percent)} of total · {fmtKg(dash.largest_hotspot?.emissions_kgco2e)}</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">CIRCULARITY SCORE</div>
          <div className="gauge-value" style={{ fontSize: '1.15rem' }}>Unavailable</div>
          <div className="gauge-sub">Module L — L1 endpoint + methodology uncommitted; shows when live</div>
        </div>
        <div className="gauge">
          <div className="gauge-label">POTENTIAL REDUCTION</div>
          <div className="gauge-value">{fmtTonnes(dash.potential_reduction_kgco2e)}</div>
          <div className="gauge-sub">{fmtPct((dash.potential_reduction_kgco2e / dash.total_kgco2e) * 100)} of baseline · all 5 recs</div>
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
              Facility → process → activity. Built against the hotspot + dataset mocks; N2 links stay <span className="mono">[]</span> in Phase 1.
            </p>
            <DrillMap dataset={dataset} hotspots={hotspots} />
            <details>
              <summary className="link" style={{ cursor: 'pointer', fontSize: '.85rem' }}>Sequential rail + tabular fallback (Phase 1 N2 alternatives)</summary>
              <div className="leak-rail">
              {hotspots.hotspots.map(h => (
                <div key={h.id} className="leak-node">
                  <div
                    className="leak-dot"
                    style={{
                      width: 30 + (h.contribution_percent ?? 0) * 0.5,
                      height: 30 + (h.contribution_percent ?? 0) * 0.5
                    }}
                    aria-hidden="true"
                  >
                    {h.rank}
                  </div>
                  <div>
                    <b>{h.process_name}</b> · <span className="mono">{fmtKg(h.emissions_kgco2e)} · {fmtPct(h.contribution_percent)}</span>{' '}
                    <SeverityBadge severity={h.severity} />
                    <div style={{ fontSize: '.8rem', color: 'var(--legend)' }}>{h.activity_category} · intensity {h.carbon_intensity ?? '—'}</div>
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
                        <td className="n mono">{h.contribution_percent?.toFixed(1)}%</td><td>{h.severity}</td></tr>
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
            0.10 speed + 0.05 confidence) — not carbon alone. Solar saves most CO₂ but ranks 5th on payback.
          </div>
        </aside>
      </div>
    </>
  )
}
