import { useMemo, useState } from 'react'
import { usePhase1Data, Loading } from './Dashboard'
import { simulateAdoption } from '../lib/api'
import { fmtINR, fmtPct, fmtTonnes, fmtYears } from '../lib/format'

// Modules O/K — Scenario UI + simulator prototype (O1–O7, K1–K3).
// Phase 1 math is local (Module K rules); live swap: POST /scenarios, POST /simulate.
export function ScenariosPage() {
  const { hotspots, recs, error } = usePhase1Data()
  const [adoption, setAdoption] = useState<Record<string, number>>({})
  const [budget, setBudget] = useState('5000000')
  const [name, setName] = useState('Monsoon retrofit bundle')
  const adoptionKey = JSON.stringify(adoption)
  const sim = useMemo(() => {
    if (!hotspots || !recs) return null
    const list = recs.recommendations.map(r => ({
      co2: r.impact?.estimated_co2_saving_kg ?? 0,
      saving: r.impact?.estimated_annual_saving ?? 0,
      capex: r.impact?.estimated_capex ?? 0,
      adoption: (JSON.parse(adoptionKey) as Record<string, number>)[r.id] ?? 100
    }))
    return simulateAdoption(hotspots.total_emissions_kgco2e, list)
  }, [hotspots, recs, adoptionKey])
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!hotspots || !recs || !sim) return <Loading />

  const items = recs.recommendations.map(r => ({
    id: r.id,
    code: r.intervention_code ?? r.id.slice(0, 8),
    title: r.intervention_title ?? 'Intervention',
    co2: r.impact?.estimated_co2_saving_kg ?? 0,
    saving: r.impact?.estimated_annual_saving ?? 0,
    capex: r.impact?.estimated_capex ?? 0,
    adoption: adoption[r.id] ?? 100
  }))
  const overBudget = Number(budget) >= 0 && sim.total_capex > Number(budget)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>What-if scenarios</h1>
          <p>Adoption % scales each intervention · payback = CAPEX ÷ saving (null when saving ≤ 0) · projected floored at 0</p>
        </div>
        <span className="provenance">O1–O7 · K1 simulate · adoption 0–100</span>
      </div>
      <div className="split">
        <div className="panel panel-pad">
          <div className="form-grid">
            <div className="field">
              <label htmlFor="sc-name">Scenario name</label>
              <input id="sc-name" value={name} onChange={e => setName(e.target.value)} maxLength={150} />
            </div>
            <div className="field">
              <label htmlFor="sc-budget">Budget limit (INR, ≥ 0)</label>
              <input id="sc-budget" type="number" min={0} value={budget} onChange={e => setBudget(e.target.value)} />
            </div>
          </div>
          {overBudget && (
            <div className="notice" style={{ marginBottom: 12 }}>
              <b>Over budget.</b> Scenario CAPEX {fmtINR(sim.total_capex)} exceeds {fmtINR(Number(budget))}.
              Drop an intervention or lower adoption %.
            </div>
          )}
          {items.map(it => (
            <div key={it.id} className="adoption-row">
              <div>
                <b style={{ fontSize: '.88rem' }}>{it.code}</b>
                <div style={{ fontSize: '.8rem', color: 'var(--legend-ink)' }}>{it.title}</div>
                <div className="mono" style={{ fontSize: '.75rem', color: 'var(--legend)' }}>
                  {fmtTonnes(it.co2)} · {fmtINR(it.saving)}/yr · {fmtINR(it.capex)}
                </div>
              </div>
              <input
                type="range" min={0} max={100} step={5}
                value={it.adoption}
                aria-label={`Adoption percentage for ${it.code}`}
                onChange={e => setAdoption(a => ({ ...a, [it.id]: Number(e.target.value) }))}
              />
              <b className="mono" aria-live="polite">{it.adoption}%</b>
            </div>
          ))}
          <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" type="button" onClick={() => setAdoption({})}>Reset to 100%</button>
            <button className="btn btn-ghost" type="button" onClick={() => setAdoption(Object.fromEntries(items.map(i => [i.id, 0])))}>Clear all</button>
          </div>
        </div>
        <div className="panel panel-pad" aria-live="polite">
          <h2>{name || 'Untitled scenario'}</h2>
          <div className="instrument-strip panel" style={{ position: 'static', margin: '12px 0' }}>
            <div className="gauge">
              <div className="gauge-label">PROJECTED</div>
              <div className="gauge-value">{fmtTonnes(sim.projected_emissions_kg)}</div>
              <div className="gauge-sub">Baseline {fmtTonnes(sim.baseline_emissions_kg)}</div>
            </div>
            <div className="gauge">
              <div className="gauge-label">REDUCTION</div>
              <div className="gauge-value">{fmtPct(sim.reduction_percent)}</div>
              <div className="gauge-sub">{fmtTonnes(sim.total_co2_saving_kg)} avoided</div>
            </div>
          </div>
          <div className="table-wrap" style={{ overflow: 'visible' }}>
            <table className="data" style={{ minWidth: 0 }}>
              <tbody>
                <tr><td>Total CAPEX</td><td className="n mono"><b>{fmtINR(sim.total_capex)}</b></td></tr>
                <tr><td>Annual saving</td><td className="n mono"><b>{fmtINR(sim.annual_saving)}</b></td></tr>
                <tr><td>Payback</td><td className="n mono"><b>{fmtYears(sim.payback_years)}</b></td></tr>
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: '.8rem', color: 'var(--legend)' }}>
            Live: POST /api/scenarios → POST /api/scenarios/{'{id}'}/interventions (adoption 0–100, duplicates rejected) →
            POST /api/scenarios/{'{id}'}/simulate (202 ImpactAssessment). Compare via K3.
          </p>
          <button className="btn btn-primary" type="button">Save scenario (demo)</button>
        </div>
      </div>
    </>
  )
}
