// Module B — Process Intelligence: Graph + Selected Process Intelligence Readout
import { useMemo } from 'react'
import { fetchActivities, fetchHotspots, fetchProcesses } from '../lib/api'
import { fmtCo2e, fmtNumber, fmtPct, fmtScore, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import { ProcessNetwork, type NetNode } from '../components/ProcessNetwork'
import { Banner, Empty, Loading, SectionHead, SeverityBadge, SourceStamp } from '../components/ui'

export function ProcessMap() {
  const { ids, selection, select, refreshKey } = useApp()
  const processes = useGroup(() => fetchProcesses(ids.facility_id), [ids.facility_id, refreshKey])
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const activities = useGroup(() => fetchActivities(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])

  const hs = hotspots.data?.hotspots ?? []
  const netNodes: NetNode[] = useMemo(() => {
    const byProcess = new Map(hs.filter((h) => h.process_id).map((h) => [h.process_id as string, h]))
    return (processes.data ?? []).map((p) => {
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
  }, [processes.data, hs])

  const selectedProcess = processes.data?.find((p) => p.id === selection.processId) ?? processes.data?.[0] ?? null
  const selectedHotspot = hs.find((h) => h.process_id === selectedProcess?.id) ?? null
  const activityCount = (pid: string | undefined) => (activities.data ?? []).filter((a) => a.process_id === pid).length
  const highImpact = hs.filter((h) => h.severity === 'HIGH' || h.severity === 'CRITICAL').length
  const critical = hs.filter((h) => h.severity === 'CRITICAL').length

  if (processes.loading) return <div className="panel-body"><Loading what="processes" /></div>
  if (processes.error) return <div className="panel-body"><Banner kind="error" title="PROCESS RETRIEVAL FAILED">{processes.error.message}</Banner></div>

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">Process Topology &amp; Intelligence</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>
            {processes.data?.length ?? 0} NODES CONFIGURED · {critical} CRITICAL LEAKS · {highImpact} HIGH IMPACT
          </span>
        </div>
        <div className="spacer" />
        <SourceStamp source={hotspots.source} />
      </div>

      <div className="panel-body">
        {netNodes.length === 0 ? (
          <Empty>No processes found. Configure process flow in Factory Profile.</Empty>
        ) : (
          <div className="split" style={{ marginBottom: 16 }}>
            {/* Process Network SVG */}
            <div className="section" style={{ margin: 0 }}>
              <div className="section-head">
                <h2>Process Flow Network</h2>
                <span className="mono tiny faint">6 NODES MONITORED</span>
              </div>
              <div className="section-body">
                <ProcessNetwork
                  nodes={netNodes}
                  selectedId={selectedProcess?.id ?? null}
                  onSelect={(id) => select({ processId: id })}
                />
              </div>
            </div>

            {/* Selected Process Detail */}
            <div className="section" style={{ margin: 0 }}>
              <div className="section-head">
                <h2>Node Parameter Telemetry</h2>
                {selectedHotspot ? <SeverityBadge severity={selectedHotspot.severity} /> : null}
              </div>
              <div className="section-body">
                {!selectedProcess ? (
                  <Empty>Select a process node</Empty>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <div className="intel-title">{selectedProcess.name}</div>
                      <span className="mono tiny">{selectedProcess.process_code ?? 'PRC-00'}</span>
                    </div>
                    <div className="mono tiny faint" style={{ marginTop: 2 }}>
                      Category: {selectedProcess.process_category ?? 'Plant Utilities'} · Seq #{selectedProcess.sequence_no ?? 1}
                    </div>

                    <div className="stat-grid" style={{ marginTop: 12 }}>
                      <div className="stat">
                        <div className="k">Calculated CO₂e</div>
                        <div className="v">{selectedHotspot ? fmtCo2e(selectedHotspot.emissions_kgco2e) : '—'}</div>
                      </div>
                      <div className="stat">
                        <div className="k">Contribution</div>
                        <div className="v">{fmtPct(selectedHotspot?.contribution_percent, 1)}</div>
                      </div>
                      <div className="stat">
                        <div className="k">Logged Activities</div>
                        <div className="v">{activityCount(selectedProcess.id)}</div>
                      </div>
                      <div className="stat">
                        <div className="k">Hotspot Score</div>
                        <div className="v">{fmtScore(selectedHotspot?.hotspot_score)}</div>
                      </div>
                    </div>

                    {selectedProcess.description ? (
                      <p className="tiny muted" style={{ marginTop: 12, lineHeight: 1.45 }}>
                        {selectedProcess.description}
                      </p>
                    ) : (
                      <p className="tiny faint" style={{ marginTop: 12 }}>
                        Continuous production process with thermal and electrical energy inputs.
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Process Ledger Table */}
        <div className="section">
          <div className="section-head">
            <h2>Process Inventory Ledger</h2>
            <span className="mono tiny faint">
              {fmtNumber(netNodes.filter((n) => !n.muted).length, 0)} OF {netNodes.length} PROCESSES RESOLVED
            </span>
          </div>
          <table className="grid">
            <thead>
              <tr>
                <th className="num">Seq</th>
                <th>Process Name</th>
                <th>Category</th>
                <th className="num">Activities</th>
                <th className="num">Emissions (kgCO₂e)</th>
                <th className="num">Contribution</th>
                <th>Severity Status</th>
              </tr>
            </thead>
            <tbody>
              {(processes.data ?? []).map((p) => {
                const h = hs.find((x) => x.process_id === p.id)
                const isSelected = selection.processId === p.id
                return (
                  <tr
                    key={p.id}
                    className={isSelected ? 'selected' : ''}
                    onClick={() => select({ processId: p.id })}
                  >
                    <td className="num">{p.sequence_no ?? '—'}</td>
                    <td style={{ fontWeight: 600 }}>{p.name}</td>
                    <td className="tiny faint">{p.process_category ?? '—'}</td>
                    <td className="num">{activityCount(p.id)}</td>
                    <td className="num">{h ? fmtCo2e(h.emissions_kgco2e) : '—'}</td>
                    <td className="num">{fmtPct(h?.contribution_percent, 1)}</td>
                    <td>{h ? <SeverityBadge severity={h.severity} /> : <span className="faint">—</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
