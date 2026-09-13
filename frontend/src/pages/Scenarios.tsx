// Modules K/O — Scenario Simulator: baseline vs projected comparison worksheet.
import { useMemo, useState } from 'react'
import { ApiError, fetchRecommendations, simulate } from '../lib/api'
import { fmtCo2e, fmtInr, fmtPayback, fmtPct, fmtScore, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import { Waterfall } from '../components/Waterfall'
import type { RecommendationItem, ScenarioEnvelope } from '../lib/types'
import {
  Banner, Empty, Loading, SectionHead, SourceStamp,
} from '../components/ui'

interface Draft { selected: boolean; adoption: number }

export function Scenarios() {
  const { ids, refreshKey } = useApp()
  const recs = useGroup(() => fetchRecommendations(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const items = recs.data?.recommendations ?? []

  const [name, setName] = useState('Scenario A — 2026 Decarbonization Plan')
  const [budget, setBudget] = useState('2500000')
  const [target, setTarget] = useState('18')
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [envelope, setEnvelope] = useState<ScenarioEnvelope | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [via, setVia] = useState<'engine' | 'local' | null>(null)

  const draftOf = (r: RecommendationItem): Draft => drafts[r.id] ?? { selected: r.rank <= 3, adoption: r.rank === 1 ? 80 : 50 }

  const localEstimate = useMemo(() => {
    const chosen = items.filter((r) => draftOf(r).selected)
    let co2 = 0, saving = 0, capex = 0
    for (const r of chosen) {
      const f = Math.max(0, Math.min(100, draftOf(r).adoption)) / 100
      co2 += (num(r.impact?.estimated_co2_saving_kg) ?? 0) * f
      saving += (num(r.impact?.estimated_annual_saving) ?? 0) * f
      capex += (num(r.impact?.estimated_capex) ?? 0) * f
    }
    return { co2, saving, capex, count: chosen.length }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, drafts])

  const reductions = useMemo(
    () => items.filter((r) => draftOf(r).selected).map((r) => ({
      label: r.intervention_code ?? r.intervention_title ?? 'intervention',
      value: (num(r.impact?.estimated_co2_saving_kg) ?? 0) * draftOf(r).adoption / 100,
    })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, drafts],
  )

  const baselineCo2 = 565050 // Standard factory baseline operational emissions
  const projectedCo2 = Math.max(0, baselineCo2 - localEstimate.co2)
  const achievedReductionPct = baselineCo2 > 0 ? (localEstimate.co2 / baselineCo2) * 100 : 0
  const budgetNum = Number(budget) || 0
  const isOverBudget = budgetNum > 0 && localEstimate.capex > budgetNum

  async function run() {
    setBusy(true); setError(null)
    const selections = items
      .filter((r) => draftOf(r).selected)
      .map((r) => ({ intervention_id: r.intervention_id, adoption_percentage: draftOf(r).adoption, selected: true }))
    if (selections.length === 0) {
      setError('Select at least one intervention to simulate.')
      setBusy(false); return
    }
    try {
      const env = await simulate(ids.facility_id, ids.reporting_period_id, selections, budget ? Number(budget) : undefined)
      setEnvelope(env); setVia('engine')
    } catch (e) {
      setEnvelope(null); setVia('local')
      setError(e instanceof ApiError ? `ENGINE UNAVAILABLE (${e.errorCode ?? e.status}) — computed via DETERMINISTIC LOCAL MODEL.` : 'Engine service offline — computed via DETERMINISTIC LOCAL MODEL.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">What-If Scenario Simulator</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>DIGITAL TWIN LITE · IMPACT &amp; ROI PROJECTION</span>
        </div>
        <div className="spacer" />
        {via ? (
          <span className={`badge ${via === 'engine' ? 'source-live' : 'source-mock'}`}>
            {via === 'engine' ? 'ENGINE-COMPUTED ●' : 'LOCAL MODEL EVALUATION'}
          </span>
        ) : null}
      </div>

      <div className="panel-body">
        {recs.loading ? <Loading what="recommendations" /> : null}
        {recs.error ? <Banner kind="error" title={recs.error.message}>{'\u00a0'}</Banner> : null}
        {error ? <Banner kind={via === 'local' ? 'warning' : 'error'} title={via === 'local' ? 'EVALUATION ENGINE NOTE' : 'ERROR'}>{error}</Banner> : null}

        {isOverBudget ? (
          <Banner kind="error" title="BUDGET CONSTRAINT EXCEEDED">
            Projected CAPEX of {fmtInr(localEstimate.capex)} exceeds user-specified budget ceiling of {fmtInr(budgetNum)} by {fmtInr(localEstimate.capex - budgetNum)}. Adjust adoption rates or deselect interventions.
          </Banner>
        ) : null}

        {/* Scenario Parameters Definition */}
        <div className="section">
          <div className="section-head">
            <h2>Scenario Parameters</h2>
            <span className="mono tiny faint">TARGET REDUCTION &amp; CAPITAL BUDGET</span>
          </div>
          <div className="section-body">
            <div className="form-grid">
              <div className="field">
                <label htmlFor="nm">Scenario Plan Name</label>
                <input id="nm" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="bg">Capital Budget Limit (₹ INR)</label>
                <input id="bg" value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="numeric" />
              </div>
              <div className="field">
                <label htmlFor="tg">Target Emission Reduction (%)</label>
                <input id="tg" value={target} onChange={(e) => setTarget(e.target.value)} inputMode="numeric" />
              </div>
            </div>
          </div>
        </div>

        {/* Interventions & Adoption Sliders */}
        <div className="section">
          <div className="section-head">
            <h2>Intervention Adoption Worksheet</h2>
            <span className="mono tiny faint">{localEstimate.count} OF {items.length} ACTIONS ACTIVE</span>
          </div>
          {items.length === 0 ? (
            <div className="section-body"><Empty>NO INTERVENTIONS AVAILABLE</Empty></div>
          ) : (
            <table className="grid">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>Use</th>
                  <th>Intervention</th>
                  <th style={{ width: 220 }}>Adoption % Slider</th>
                  <th className="num">Scaled CAPEX</th>
                  <th className="num">Scaled Saving</th>
                  <th className="num">CO₂ Avoided</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => {
                  const d = draftOf(r)
                  const f = d.adoption / 100
                  const capex = (num(r.impact?.estimated_capex) ?? 0) * f
                  const sav = (num(r.impact?.estimated_annual_saving) ?? 0) * f
                  const co2 = (num(r.impact?.estimated_co2_saving_kg) ?? 0) * f
                  return (
                    <tr key={r.id} className={d.selected ? 'selected' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          checked={d.selected}
                          onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, selected: e.target.checked } })}
                          aria-label={`Select ${r.intervention_code}`}
                        />
                      </td>
                      <td>
                        <div className="mono tiny" style={{ color: 'var(--cyan)' }}>{r.intervention_code}</div>
                        <div style={{ fontWeight: 600 }}>{r.intervention_title}</div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <input
                            type="range"
                            min={0}
                            max={100}
                            step={5}
                            disabled={!d.selected}
                            value={d.adoption}
                            onChange={(e) => setDrafts({ ...drafts, [r.id]: { ...d, adoption: Number(e.target.value) } })}
                            style={{ flex: 1 }}
                          />
                          <span className="num mono tiny" style={{ width: 34 }}>{d.adoption}%</span>
                        </div>
                      </td>
                      <td className="num">{d.selected ? fmtInr(capex) : '—'}</td>
                      <td className="num" style={{ color: d.selected ? 'var(--emerald)' : undefined }}>
                        {d.selected ? fmtInr(sav) : '—'}
                      </td>
                      <td className="num" style={{ color: d.selected ? 'var(--cyan)' : undefined }}>
                        {d.selected ? fmtCo2e(co2) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          <div style={{ padding: 12, background: 'var(--surface-2)', borderTop: '1px solid var(--border)' }}>
            <button className="primary" onClick={run} disabled={busy}>
              {busy ? 'SIMULATING WORKSHEET…' : 'RUN DIGITAL TWIN SIMULATION ▶'}
            </button>
          </div>
        </div>

        {/* Baseline vs Projected Comparison Worksheet */}
        <div className="section">
          <div className="section-head">
            <h2>Baseline vs. Projected Scenario Outcome</h2>
            <span className="mono tiny faint">
              {achievedReductionPct >= Number(target) ? '✓ TARGET ACHIEVED' : 'TARGET GAP: ' + (Number(target) - achievedReductionPct).toFixed(1) + '%'}
            </span>
          </div>
          <div className="section-body">
            <div className="kpi-grid" style={{ marginBottom: 16 }}>
              <div className="kpi">
                <div className="k-label">Baseline Footprint</div>
                <div className="k-value">{fmtCo2e(baselineCo2)}</div>
                <div className="k-foot">Current FY 2025–26</div>
              </div>
              <div className="kpi">
                <div className="k-label">Projected Footprint</div>
                <div className="k-value" style={{ color: 'var(--cyan)' }}>{fmtCo2e(projectedCo2)}</div>
                <div className="k-foot">Post-Intervention</div>
              </div>
              <div className="kpi">
                <div className="k-label">Emission Reduction</div>
                <div className="k-value" style={{ color: 'var(--emerald)' }}>{fmtCo2e(localEstimate.co2)}</div>
                <div className="k-foot">
                  <span className="mono" style={{ color: 'var(--emerald)', fontWeight: 700 }}>
                    -{fmtPct(achievedReductionPct, 1)}
                  </span>
                  <span> of plant total</span>
                </div>
              </div>
              <div className="kpi">
                <div className="k-label">Required CAPEX</div>
                <div className="k-value" style={{ color: isOverBudget ? 'var(--coral)' : 'var(--ink)' }}>
                  {fmtInr(localEstimate.capex)}
                </div>
                <div className="k-foot">
                  {isOverBudget ? (
                    <span style={{ color: 'var(--coral)', fontWeight: 600 }}>Over budget!</span>
                  ) : (
                    <span>Within ₹{budgetNum / 100000}L limit</span>
                  )}
                </div>
              </div>
              <div className="kpi">
                <div className="k-label">Annual Cost Savings</div>
                <div className="k-value" style={{ color: 'var(--amber)' }}>{fmtInr(localEstimate.saving)}/yr</div>
                <div className="k-foot">Direct utility savings</div>
              </div>
              <div className="kpi">
                <div className="k-label">Blended Payback</div>
                <div className="k-value">
                  {localEstimate.saving > 0 ? `${(localEstimate.capex / localEstimate.saving).toFixed(1)} yr` : '—'}
                </div>
                <div className="k-foot">Net ROI Horizon</div>
              </div>
            </div>

            {/* Waterfall Chart */}
            <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-xs)', padding: 14 }}>
              <div className="label" style={{ marginBottom: 10 }}>Emission Abatement Waterfall (kgCO₂e)</div>
              <Waterfall
                baseline={baselineCo2}
                reductions={reductions}
                projected={projectedCo2}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
