// Signature "Trace the Leak" evidence chain:
// PROCESS → ACTIVITY → FACTOR → EMISSION → HOTSPOT → INTERVENTION.
import { useEffect, useMemo, useState } from 'react'
import { fetchActivities, fetchFactors } from '../lib/api'
import { fmtCo2e, fmtInr, fmtNumber, fmtPayback, fmtPct, fmtScore, num } from '../lib/format'
import { useAsync, useGroup } from '../lib/useApi'
import type { ActivityData, RecommendationItem, Severity } from '../lib/types'

interface Props {
  open: boolean
  onClose: () => void
  facilityId: string
  periodId: string
  processId: string | null
  processName: string
  contribution: number | null
  severity: Severity | null
  hotspotScore: number | null
  recommendation: RecommendationItem | null
}

interface Step { n: string; headline: string; value?: string; formula?: string }

export function EvidenceDrawer(props: Props) {
  const { open, onClose, facilityId, periodId, processId, processName, contribution, severity, hotspotScore, recommendation } = props
  const activities = useGroup(() => fetchActivities(facilityId, periodId), [facilityId, periodId, open])
  const factors = useAsync(() => fetchFactors(), [open])
  const [active, setActive] = useState(0)

  const activity: ActivityData | null = useMemo(() => {
    const rows = (activities.data ?? []).filter((a) => (processId ? a.process_id === processId : true))
    const pool = rows.length ? rows : (activities.data ?? [])
    if (!pool.length) return null
    return [...pool].sort((a, b) => (num(b.normalized_value) ?? num(b.original_value) ?? 0) - (num(a.normalized_value) ?? num(a.original_value) ?? 0))[0]
  }, [activities.data, processId])

  const factor = useMemo(() => {
    if (!activity || !factors.data) return null
    const matches = factors.data.filter(
      (f) => f.active && f.category.toUpperCase() === activity.activity_category.toUpperCase()
        && (f.input_unit || '').toLowerCase() === (activity.normalized_unit || '').toLowerCase(),
    )
    if (!matches.length) return null
    const india = matches.filter((f) => (f.region_country || '').toLowerCase() === 'india')
    const pool = india.length ? india : matches
    return [...pool].sort((a, b) => (b.source_year ?? 0) - (a.source_year ?? 0))[0]
  }, [activity, factors.data])

  const emissionKg = useMemo(() => {
    const v = num(activity?.normalized_value) ?? num(activity?.original_value)
    const f = num(factor?.total_co2e_factor)
    return v !== null && f !== null ? v * f : null
  }, [activity, factor])

  const steps: Step[] = useMemo(() => {
    const av = activity ? (num(activity.normalized_value) ?? num(activity.original_value)) : null
    return [
      { n: '01 · PROCESS', headline: processName, value: contribution === null ? undefined : `${fmtPct(contribution, 2)} of operational emissions` },
      activity
        ? { n: '02 · ACTIVITY', headline: activity.activity_subcategory, value: `${fmtNumber(activity.original_value, 2)} ${activity.original_unit} → ${fmtNumber(activity.normalized_value, 2)} ${activity.normalized_unit}` }
        : { n: '02 · ACTIVITY', headline: 'No activity linked to this process' },
      factor
        ? { n: '03 · FACTOR', headline: f2(factor.item_name), value: `${factor.total_co2e_factor} kgCO₂e/${factor.input_unit} · ${factor.factor_code}`, formula: `${factor.source_name} · v${factor.version} (${factor.source_year})` }
        : { n: '03 · FACTOR', headline: factor === null && activity ? 'UNRESOLVED' : '—', value: activity ? 'No active factor matched this category/unit' : undefined },
      av !== null && factor
        ? { n: '04 · EMISSION', headline: fmtCo2e(emissionKg), formula: `${fmtNumber(av, 2)} ${activity!.normalized_unit} × ${factor.total_co2e_factor} = ${fmtNumber(emissionKg, 2)} kgCO₂e` }
        : { n: '04 · EMISSION', headline: '—', value: 'Not calculated (missing factor or value)' },
      { n: '05 · HOTSPOT', headline: severity ?? '—', value: `contribution ${contribution === null ? '—' : fmtPct(contribution, 2)} · hotspot score ${fmtScore(hotspotScore)}` },
      recommendation
        ? { n: '06 · INTERVENTION', headline: `${recommendation.intervention_code ?? ''} ${f2(recommendation.intervention_title ?? '')}`.trim(), value: `CAPEX ${fmtInr(recommendation.impact?.estimated_capex)} · saving ${fmtInr(recommendation.impact?.estimated_annual_saving)}/yr · payback ${fmtPayback(recommendation.impact?.payback_years, recommendation.impact?.estimated_annual_saving)}` }
        : { n: '06 · INTERVENTION', headline: 'No linked assessment' },
    ]
  }, [processName, contribution, activity, factor, emissionKg, severity, hotspotScore, recommendation])

  useEffect(() => {
    if (!open) return
    setActive(0)
    const t = setInterval(() => setActive((s) => (s >= steps.length - 1 ? s : s + 1)), 520)
    return () => clearInterval(t)
  }, [open, steps.length])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div className="scrim" onClick={onClose} aria-hidden="true" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Evidence for ${processName}`}>
        <div className="drawer-head">
          <div>
            <div className="label">Trace the leak</div>
            <div className="drawer-title">{processName}</div>
          </div>
          <div className="spacer" />
          <button onClick={() => setActive(0)}>REPLAY</button>
          <button className="link" onClick={onClose} aria-label="Close evidence">CLOSE ✕</button>
        </div>
        <div className="drawer-body">
          <div className="trace">
            {steps.map((s, i) => (
              <div key={s.n} className={`trace-step ${i === active ? 'active' : i < active ? 'done' : ''}`}
                onClick={() => setActive(i)} role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') setActive(i) }}>
                <div className="n">{s.n}</div>
                <div className="headline">{s.headline}</div>
                {s.value ? <div className="val">{s.value}</div> : null}
                {s.formula ? <div className="formula">{s.formula}</div> : null}
              </div>
            ))}
          </div>
          <p className="tiny faint" style={{ marginTop: 14 }}>
            This chain is deterministic: the engine derived every value below from activity data and a versioned emission factor.
            The AI narrative (if present) is commentary only and never feeds these numbers.
          </p>
        </div>
      </aside>
    </>
  )
}

function f2(s: string): string {
  return s.length > 64 ? `${s.slice(0, 63)}…` : s
}
