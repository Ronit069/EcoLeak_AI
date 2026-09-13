// Module G — Carbon Leak Map: Process hotspot detector & hero instrument
import { useMemo, useState } from 'react'
import { fetchHotspots, fetchProcesses, fetchRecommendations } from '../lib/api'
import { fmtCo2e, fmtInr, fmtPct, fmtPayback, fmtScore, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import { ProcessNetwork, type NetNode } from '../components/ProcessNetwork'
import { EvidenceDrawer } from '../components/EvidenceDrawer'
import { Banner, Empty, Loading, SectionHead, SeverityBadge, SourceStamp, StatusStamp } from '../components/ui'

export function LeakMapPage() {
  const { ids, selection, select, refreshKey } = useApp()
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const processes = useGroup(() => fetchProcesses(ids.facility_id), [ids.facility_id, refreshKey])
  const recs = useGroup(() => fetchRecommendations(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])

  const hs = hotspots.data?.hotspots ?? []
  const netNodes: NetNode[] = useMemo(() => {
    const byProcess = new Map(hs.filter((h) => h.process_id).map((h) => [h.process_id as string, h]))
    const fromProcesses = (processes.data ?? []).map((p) => {
      const h = byProcess.get(p.id)
      return {
        id: p.id,
        name: p.name,
        emissions: h ? num(h.emissions_kgco2e) : null,
        contribution: h ? num(h.contribution_percent) : null,
        severity: h ? h.severity : null,
        muted: !h,
      }
    })
    return fromProcesses.length ? fromProcesses : hs.map((h, i) => ({
      id: h.process_id ?? `h-${i}`,
      name: h.process_name ?? 'Unassigned',
      emissions: num(h.emissions_kgco2e),
      contribution: num(h.contribution_percent),
      severity: h.severity,
    }))
  }, [hs, processes.data])

  const selected = useMemo(() => hs.find((h) => h.id === selection.hotspotId || h.process_id === selection.processId) ?? hs[0] ?? null, [hs, selection.hotspotId, selection.processId])
  const topRec = useMemo(() => (selected && recs.data ? recs.data.recommendations.find((r) => r.hotspot_id === selected.id) ?? recs.data.recommendations[0] ?? null : null), [selected, recs.data])
  const total = hotspots.data?.total_emissions_kgco2e ?? 0

  const edges: string[] = []
  if (hs.length === 1) edges.push('Single process facility — 100% contribution by definition; ranking is not meaningful.')
  if ((Number(total) || 0) === 0) edges.push('Zero total emissions detected — percentage attribution is not computed.')
  if (hs.length >= 2 && (Number(hs[0].contribution_percent) || 0) >= 60) edges.push('Dominant outlier detected: single process exceeds 60% of total footprint. Verify meter data for sensor calibration errors.')

  if (hotspots.loading) return <div className="panel-body"><Loading what="carbon leak streams" /></div>
  if (hotspots.error) return <div className="panel-body"><Banner kind="error" title="LEAK MAP CALCULATION FAILED">{hotspots.error.message}</Banner></div>

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">Process Carbon Leak Map</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>P&amp;ID PROCESS FLOW · SEVERITY ATTRIBUTION</span>
        </div>
        <div className="spacer" />
        <span className="badge">Scope 1 + 2 Operational</span>
        <SourceStamp source={hotspots.source} />
      </div>

      <div className="panel-body">
        {edges.map((e) => <Banner key={e} kind="warning" title="AUDIT EDGE CASE">{e}</Banner>)}

        <div className="split" style={{ marginBottom: 16 }}>
          {/* Main Network Visualizer */}
          <div className="section" style={{ margin: 0 }}>
            <div className="section-head">
              <h2>Plant Process Schematic</h2>
              <span className="mono tiny faint">6 MONITORED NODES · RECIRCULATION LOOPS</span>
            </div>
            <div className="section-body">
              {hs.length === 0 ? (
                <Empty>NO CARBON CALCULATION DETECTED</Empty>
              ) : (
                <ProcessNetwork
                  nodes={netNodes}
                  selectedId={selected?.process_id ?? null}
                  onSelect={(id) => {
                    const h = hs.find((x) => x.process_id === id)
                    if (h) select({ hotspotId: h.id, processId: id })
                  }}
                  onOpen={() => setEvidenceOpen(true)}
                />
              )}
              <div className="mono tiny faint" style={{ marginTop: 10 }}>
                Node border indicates severity rank · Node size scales with contribution % · Dashed links show closed-loop recycling &amp; heat recovery
              </div>
            </div>
          </div>

          {/* Selected Leak Telemetry / Best Action */}
          <div className="section" style={{ margin: 0 }}>
            <div className="section-head">
              <h2>Leak Intelligence Readout</h2>
              {selected ? <SeverityBadge severity={selected.severity} /> : null}
            </div>
            <div className="section-body">
              {!selected ? (
                <Empty>Select a process node</Empty>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div className="intel-title">{selected.process_name ?? 'Unassigned'}</div>
                    <span className="mono tiny">Rank #{selected.rank}</span>
                  </div>

                  <div className="stat-grid" style={{ marginTop: 12 }}>
                    <div className="stat">
                      <div className="k">Emissions</div>
                      <div className="v">{fmtCo2e(selected.emissions_kgco2e)}</div>
                    </div>
                    <div className="stat">
                      <div className="k">Contribution</div>
                      <div className="v">{fmtPct(selected.contribution_percent, 1)}</div>
                    </div>
                    <div className="stat">
                      <div className="k">Hotspot Score</div>
                      <div className="v">{fmtScore(selected.hotspot_score)}</div>
                    </div>
                    <div className="stat">
                      <div className="k">Inefficiency</div>
                      <div className="v">{fmtScore(selected.inefficiency_score)}</div>
                    </div>
                  </div>

                  {selected.explanation ? (
                    <div style={{ marginTop: 12, padding: 8, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-xs)', fontSize: 'var(--fs-xs)', color: 'var(--ink-2)' }}>
                      <strong style={{ color: 'var(--ink)' }}>Root Cause: </strong>
                      {selected.explanation}
                    </div>
                  ) : null}

                  {topRec ? (
                    <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <span className="label" style={{ color: 'var(--emerald)' }}>BEST CIRCULAR ACTION</span>
                        <StatusStamp status={topRec.status} />
                      </div>
                      <div style={{ fontWeight: 600, fontSize: 'var(--fs-sm)' }}>
                        <span className="mono tiny">{topRec.intervention_code}</span> {topRec.intervention_title}
                      </div>

                      <div className="strip-row" style={{ marginTop: 6 }}>
                        <span className="muted tiny">CO₂ Avoided</span>
                        <span className="num small" style={{ color: 'var(--emerald)' }}>{fmtCo2e(topRec.impact?.estimated_co2_saving_kg)}/yr</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Annual Saving</span>
                        <span className="num small" style={{ color: 'var(--amber)' }}>{fmtInr(topRec.impact?.estimated_annual_saving)}/yr</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Estimated Payback</span>
                        <span className="num small">{fmtPayback(topRec.impact?.payback_years, topRec.impact?.estimated_annual_saving)}</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">CAPEX Investment</span>
                        <span className="num small">{fmtInr(topRec.impact?.estimated_capex)}</span>
                      </div>

                      <div className="btn-row" style={{ marginTop: 14 }}>
                        <button className="primary" style={{ width: '100%' }} onClick={() => setEvidenceOpen(true)}>
                          Trace Full Evidence Chain →
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="tiny faint" style={{ marginTop: 14 }}>No linked circular intervention for this node.</p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Priority Hotspots Table */}
        <div className="section">
          <div className="section-head">
            <h2>Process Leak Registry</h2>
            <span className="mono tiny faint">6 MONITORED PROCESSES</span>
          </div>
          {hs.length === 0 ? (
            <div className="section-body"><Empty>No data</Empty></div>
          ) : (
            <table className="grid">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Process</th>
                  <th className="num">Emissions (kgCO₂e)</th>
                  <th className="num">Contribution</th>
                  <th className="num">Hotspot Score</th>
                  <th className="num">Inefficiency</th>
                  <th className="num">Improvement</th>
                  <th>Severity</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {hs.map((h) => (
                  <tr
                    key={h.id}
                    className={selected?.id === h.id ? 'selected' : ''}
                    onClick={() => select({ hotspotId: h.id, processId: h.process_id ?? null })}
                  >
                    <td className="num">{h.rank}</td>
                    <td style={{ fontWeight: 600 }}>{h.process_name ?? 'Unassigned'}</td>
                    <td className="num">{fmtCo2e(h.emissions_kgco2e)}</td>
                    <td className="num">{fmtPct(h.contribution_percent, 1)}</td>
                    <td className="num">{fmtScore(h.hotspot_score)}</td>
                    <td className="num">{fmtScore(h.inefficiency_score)}</td>
                    <td className="num">{fmtScore(h.improvement_potential_score)}</td>
                    <td><SeverityBadge severity={h.severity} /></td>
                    <td>
                      <span className="mono tiny" style={{ color: h.severity === 'CRITICAL' ? 'var(--coral)' : 'var(--ink-2)' }}>
                        {h.severity === 'CRITICAL' ? 'LEAK DETECTED' : 'MONITORED'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <EvidenceDrawer
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        facilityId={ids.facility_id}
        periodId={ids.reporting_period_id}
        processId={selected?.process_id ?? null}
        processName={selected?.process_name ?? 'Process'}
        contribution={selected ? num(selected.contribution_percent) : null}
        severity={selected?.severity ?? null}
        hotspotScore={selected ? num(selected.hotspot_score) : null}
        recommendation={topRec}
      />
    </>
  )
}
