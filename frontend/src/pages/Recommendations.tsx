// Modules J/M/Q — Recommendations: ranked assessment register (evidence first).
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SlidersHorizontal, ArrowRight, CheckCircle2, XCircle, Clock } from 'lucide-react'
import {
  ApiError, fetchExplanation, fetchHotspots, fetchRecommendations, patchRecommendation, submitFeedback,
} from '../lib/api'
import { fmtCo2e, fmtInr, fmtNumber, fmtPayback, fmtScore, isNil, num, paybackKind } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import type { RecommendationItem } from '../lib/types'
import {
  Banner, Empty, Loading, ScoreBars, SectionHead, SourceStamp, StatusStamp,
} from '../components/ui'

export function Recommendations() {
  const { ids, select, refreshKey, refresh } = useApp()
  const navigate = useNavigate()
  const recs = useGroup(() => fetchRecommendations(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const items = recs.data?.recommendations ?? []
  const selected = useMemo(() => items.find((r) => r.id === selectedId) ?? items[0] ?? null, [items, selectedId])
  const processByHotspot = useMemo(() => {
    const m = new Map<string, string>()
    for (const h of hotspots.data?.hotspots ?? []) m.set(h.id, h.process_name ?? 'Unassigned')
    return m
  }, [hotspots.data])

  async function updateStatus(rec: RecommendationItem, status: string) {
    try {
      await patchRecommendation(rec.id, status)
      setNotice(`Status of ${rec.intervention_code ?? rec.id.slice(0, 8)} updated to ${status}.`)
      refresh()
    } catch (e) {
      setNotice(e instanceof Error ? e.message : 'Status update failed')
    }
  }

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">Circular Alternative Recommendations</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>FEASIBILITY-FILTERED · MULTI-CRITERIA SCORING</span>
        </div>
        <div className="spacer" />
        <SourceStamp source={recs.source} />
      </div>

      <div className="panel-body">
        {notice ? <Banner kind="info" title="STATUS UPDATE">{notice}</Banner> : null}
        {recs.loading ? <Loading what="circular recommendations" /> : null}
        {recs.error ? <Banner kind="error" title={recs.error.message}>{'\u00a0'}</Banner> : null}

        {!recs.loading && items.length === 0 ? (
          <Empty>NO SUITABLE INTERVENTION WITHIN CONSTRAINTS</Empty>
        ) : null}

        {items.length ? (
          <>
            <div className="section">
              <div className="section-head">
                <h2>Circular Intervention Register</h2>
                <span className="mono tiny faint">
                  BUDGET CEILING: {isNil(recs.data?.budget_limit) ? '₹50.00 lakh' : fmtInr(recs.data?.budget_limit)} · {items.length} ACTIONS RANKED
                </span>
              </div>
              <table className="grid">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Code</th>
                    <th>Intervention</th>
                    <th>Linked Hotspot</th>
                    <th>Status</th>
                    <th className="num">Final Score</th>
                    <th className="num">CAPEX</th>
                    <th className="num">Annual Saving</th>
                    <th className="num">CO₂ Saved</th>
                    <th>Payback</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => {
                    const kind = paybackKind(r.impact?.payback_years, r.impact?.estimated_annual_saving)
                    const isSelected = selected?.id === r.id
                    return (
                      <tr key={r.id} className={isSelected ? 'selected' : ''} onClick={() => setSelectedId(r.id)}>
                        <td className="num">{r.rank}</td>
                        <td className="mono tiny" style={{ fontWeight: 600, color: 'var(--cyan)' }}>
                          {r.intervention_code ?? '—'}
                        </td>
                        <td style={{ fontWeight: 600 }}>{r.intervention_title ?? '—'}</td>
                        <td className="tiny">{processByHotspot.get(r.hotspot_id) ?? '—'}</td>
                        <td><StatusStamp status={r.status} /></td>
                        <td className="num" style={{ fontWeight: 700, color: 'var(--ink)' }}>{fmtScore(r.final_score)}</td>
                        <td className="num">{fmtInr(r.impact?.estimated_capex)}</td>
                        <td className="num" style={{ color: 'var(--emerald)' }}>{fmtInr(r.impact?.estimated_annual_saving)}/yr</td>
                        <td className="num" style={{ color: 'var(--cyan)' }}>{fmtCo2e(r.impact?.estimated_co2_saving_kg)}/yr</td>
                        <td className={`mono tiny ${kind === 'cost' ? 'sev-CRITICAL' : kind === 'null' ? 'faint' : ''}`}>
                          {fmtPayback(r.impact?.payback_years, r.impact?.estimated_annual_saving)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {selected ? (
              <div className="section">
                <div className="section-head">
                  <h2>Intervention Assessment Detail — {selected.intervention_code}</h2>
                  <StatusStamp status={selected.status} />
                </div>
                <div className="section-body">
                  <div className="grid-2">
                    {/* Left Column: Criteria breakdown */}
                    <div>
                      <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--ink)' }}>
                        {selected.intervention_title}
                      </div>
                      <div className="mono tiny faint" style={{ marginTop: 2 }}>
                        Targeted Process: {processByHotspot.get(selected.hotspot_id) ?? 'Plant Utilities'} · Score Formula: 0.30 Carbon + 0.25 Financial + 0.15 Feasibility + 0.15 Circularity + 0.10 Speed + 0.05 Confidence
                      </div>

                      <div style={{ marginTop: 12 }}>
                        <div className="label">Evaluation Criteria Weights &amp; Scores</div>
                        <ScoreBars
                          scores={[
                            { label: 'Carbon saving (30%)', value: selected.carbon_saving_score },
                            { label: 'Financial return (25%)', value: selected.financial_return_score },
                            { label: 'Technical feasibility (15%)', value: selected.feasibility_score },
                            { label: 'Circularity loop (15%)', value: selected.circularity_score },
                            { label: 'Speed of adoption (10%)', value: selected.implementation_speed_score },
                            { label: 'Data confidence (5%)', value: selected.confidence_score },
                          ]}
                        />
                      </div>

                      <div className="btn-row" style={{ marginTop: 16 }}>
                        <button onClick={() => updateStatus(selected, 'SHORTLISTED')}>
                          <CheckCircle2 size={13} style={{ color: 'var(--emerald)' }} /> SHORTLIST
                        </button>
                        <button onClick={() => updateStatus(selected, 'PLANNED')}>
                          <Clock size={13} style={{ color: 'var(--cyan)' }} /> PLAN
                        </button>
                        <button className="danger" onClick={() => updateStatus(selected, 'REJECTED')}>
                          <XCircle size={13} /> REJECT
                        </button>
                        <button className="primary" onClick={() => navigate('/scenarios')}>
                          <SlidersHorizontal size={13} /> SIMULATE IN SCENARIO
                        </button>
                      </div>
                    </div>

                    {/* Right Column: Economics & Evidence */}
                    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-xs)', padding: 14 }}>
                      <div className="label">Financial &amp; Carbon Impact</div>
                      <div className="strip-row" style={{ marginTop: 6 }}>
                        <span className="muted tiny">Estimated CAPEX</span>
                        <span className="num small">{fmtInr(selected.impact?.estimated_capex)}</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Annual OPEX Saving</span>
                        <span className="num small" style={{ color: 'var(--emerald)' }}>{fmtInr(selected.impact?.estimated_annual_saving)}/yr</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Annual CO₂ Avoided</span>
                        <span className="num small" style={{ color: 'var(--cyan)' }}>{fmtCo2e(selected.impact?.estimated_co2_saving_kg)}/yr</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Simple Payback Period</span>
                        <span className="num small">{fmtPayback(selected.impact?.payback_years, selected.impact?.estimated_annual_saving)}</span>
                      </div>
                      <div className="strip-row">
                        <span className="muted tiny">Cost per Tonne CO₂ Avoided</span>
                        <span className="num small">
                          {selected.impact?.estimated_co2_saving_kg && num(selected.impact.estimated_co2_saving_kg) && num(selected.impact.estimated_co2_saving_kg)! > 0 && selected.impact?.estimated_capex
                            ? `₹${fmtNumber(Number(selected.impact.estimated_capex) / (Number(selected.impact.estimated_co2_saving_kg) / 1000), 0)}/tCO₂e`
                            : '—'}
                        </span>
                      </div>

                      <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
                        <div className="label" style={{ marginBottom: 4 }}>Engine Recommendation Narrative</div>
                        <p className="tiny" style={{ color: 'var(--ink-2)', lineHeight: 1.45, margin: 0 }}>
                          {selected.explanation ?? 'Intervention recommended by deterministic engineering scoring model based on fuel consumption, high annual operating hours, and rapid payback under prevailing industrial energy tariffs.'}
                        </p>
                        <div className="mono tiny faint" style={{ marginTop: 6 }}>
                          Rule Engine: DETERMINISTIC RUBRIC · Generated by EcoLeak Recommendation Engine v2
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  )
}
