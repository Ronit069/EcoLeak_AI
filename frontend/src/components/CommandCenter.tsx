// Command Center — cinematic full-screen presentation mode.
import { useMemo } from 'react'
import { X } from 'lucide-react'
import { fetchHotspots, fetchProcesses, fetchRecommendations } from '../lib/api'
import { fmtCo2e, fmtInr, fmtPct, fmtPayback, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import { ProcessNetwork, type NetNode } from './ProcessNetwork'
import { SeverityBadge } from './ui'

export function CommandCenter() {
  const { ids, commandCenter, setCommandCenter, selection, select, refreshKey } = useApp()
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const processes = useGroup(() => fetchProcesses(ids.facility_id), [ids.facility_id, refreshKey])
  const recs = useGroup(() => fetchRecommendations(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])

  const hs = hotspots.data?.hotspots ?? []
  const total = num(hotspots.data?.total_emissions_kgco2e) ?? 0
  const reduction = (recs.data?.recommendations ?? []).reduce((s, r) => s + (num(r.impact?.estimated_co2_saving_kg) ?? 0), 0)
  const saving = (recs.data?.recommendations ?? []).reduce((s, r) => s + (num(r.impact?.estimated_annual_saving) ?? 0), 0)
  const top = hs[0] ?? null
  const best = useMemo(() => (top ? recs.data?.recommendations.find((r) => r.hotspot_id === top.id) ?? recs.data?.recommendations[0] : recs.data?.recommendations[0]), [top, recs.data])

  const netNodes: NetNode[] = useMemo(() => {
    const byProcess = new Map(hs.filter((h) => h.process_id).map((h) => [h.process_id as string, h]))
    const fromProcesses = (processes.data ?? []).map((p) => {
      const h = byProcess.get(p.id)
      return {
        id: p.id, name: p.name,
        emissions: h ? num(h.emissions_kgco2e) : null,
        contribution: h ? num(h.contribution_percent) : null,
        severity: h ? h.severity : null, muted: !h,
      }
    })
    return fromProcesses.length ? fromProcesses : hs.map((h, i) => ({
      id: h.process_id ?? `h-${i}`, name: h.process_name ?? 'Unassigned',
      emissions: num(h.emissions_kgco2e), contribution: num(h.contribution_percent), severity: h.severity,
    }))
  }, [hs, processes.data])

  if (!commandCenter) return null
  const projected = Math.max(0, total - reduction)
  const pct = total > 0 ? (reduction / total) * 100 : null

  return (
    <div className="cc" role="dialog" aria-modal="true" aria-label="Command Center">
      <div className="cc-head">
        <div>
          <div className="label">EcoLeak · Industrial Carbon Intelligence</div>
          <div className="cc-title">Facility Command Center</div>
        </div>
        <div className="spacer" />
        <button onClick={() => setCommandCenter(false)}><X size={16} /> Exit</button>
      </div>

      <div className="cc-kpis">
        <div className="cc-kpi"><div className="k">Total CO₂e</div><div className="v">{fmtCo2e(total)}</div></div>
        <div className="cc-kpi"><div className="k">Top hotspot</div><div className="v">{top?.process_name ?? '—'}</div><div className="tiny"><SeverityBadge severity={top?.severity} /> {fmtPct(top?.contribution_percent, 0)}</div></div>
        <div className="cc-kpi"><div className="k">Reduction potential</div><div className="v">{fmtCo2e(reduction)}</div><div className="tiny faint">{pct === null ? '' : `${fmtPct(pct, 1)} of footprint`}</div></div>
        <div className="cc-kpi"><div className="k">Annual saving</div><div className="v">{fmtInr(saving)}</div><div className="tiny faint">potential</div></div>
        <div className="cc-kpi"><div className="k">Best intervention</div><div className="v" style={{ fontSize: 'var(--fs-lg)' }}>{best?.intervention_title ?? '—'}</div><div className="tiny faint">{best ? fmtPayback(best.impact?.payback_years, best.impact?.estimated_annual_saving) : ''}</div></div>
      </div>

      <ProcessNetwork
        nodes={netNodes}
        selectedId={selection.hotspotId ? (hs.find((h) => h.id === selection.hotspotId)?.process_id ?? null) : null}
        onSelect={(id) => { const h = hs.find((x) => x.process_id === id); if (h) select({ hotspotId: h.id, processId: id }) }}
      />

      <div className="compare" style={{ marginTop: 26 }}>
        <div className="side">
          <span className="label">Current factory</span>
          <span className="big">{fmtCo2e(total)}</span>
          <span className="tiny faint">baseline operational emissions</span>
        </div>
        <div className="arrow">→</div>
        <div className="side">
          <span className="label">Optimized factory</span>
          <span className="big">{fmtCo2e(projected)}</span>
          <span className="delta">{fmtCo2e(reduction)} avoided · {fmtInr(saving)}/yr</span>
        </div>
      </div>
    </div>
  )
}
