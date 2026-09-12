import { useEffect, useMemo, useState } from 'react'
import { usePhase1Data, Loading } from './Dashboard'
import { fetchSimulate, simulateAdoption, type SimulateResult } from '../lib/api'
import { fmtINR, fmtPct, fmtTonnes, fmtYears } from '../lib/format'

// Modules O/K — Scenario UI + simulator (K1 live with local Module-K fallback).
// Phase 2: POST /api/scenarios/{id}/simulate (merged engine router) when
// reachable; otherwise the same Module-K math runs locally with a notice.
// O1–O7 scenario CRUD is not yet served by the merged surface (logged in
// docs/phase2/p1_integration_log.md §7 / contract_changes.md).
export function ScenariosPage() {
  const { hotspots, recs, ids, error } = usePhase1Data()
  const [adoption, setAdoption] = useState<Record<string, number>>({})
  const [budget, setBudget] = useState('5000000')
  const [name, setName] = useState('Monsoon retrofit bundle')
  const [sim, setSim] = useState<SimulateResult | null>(null)
  const [simKind, setSimKind] = useState<'k1-live' | 'local-math' | null>(null)
  const adoptionKey = JSON.stringify(adoption)

  // Local Module-K math (instant, always correct for the UI feedback loop).
  const localSim = useMemo(() => {
    if (!hotspots || !recs) return null
    const list = recs.recommendations.map(r => ({
      co2: r.impact?.estimated_co2_saving_kg ?? 0,
      saving: r.impact?.estimated_annual_saving ?? 0,
      capex: r.impact?.estimated_capex ?? 0,
      adoption: (JSON.parse(adoptionKey) as Record<string, number>)[r.id] ?? 100
    }))
    return simulateAdoption(hotspots.total_emissions_kgco2e, list)
  }, [hotspots, recs, adoptionKey])

  // K1 live attempt (per change); falls back silently to local math.
  useEffect(() => {
    if (!hotspots || !recs || !localSim) return
    let live = true
    const selections = recs.recommendations.map(r => ({
      intervention_id: r.intervention_id,
      adoption_percentage: (JSON.parse(adoptionKey) as Record<string, number>)[r.id] ?? 100,
    }))
    setSimKind('local-math')
    fetchSimulate(ids.facility_id, ids.reporting_period_id, selections, Number(budget) || undefined)
      .then(r => {
        if (!live) return
        if (r.data) { setSim(r.data); setSimKind('k1-live') }
        else setSim(localSim)
      })
      .catch(() => { if (live) setSim(localSim) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adoptionKey, budget, recs, hotspots, ids])

  const simFinal = sim ?? localSim
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!hotspots || !recs || !simFinal || !localSim) return <Loading />

  const items = recs.recommendations.map(r => ({
    id: r.id,
    code: r.intervention_code ?? r.id.slice(0, 8),
    title: r.intervention_title ?? 'Intervention',
    co2: r.impact?.estimated_co2_saving_kg ?? 0,
    saving: r.impact?.estimated_annual_saving ?? 0,
    capex: r.impact?.estimated_capex ?? 0,
    adoption: adoption[r.id] ?? 100
  }))
  const overBudget = Number(budget) >= 0 && simFinal.total_capex > Number(budget)

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
              <b>Over budget.</b> Scenario CAPEX {fmtINR(simFinal.total_capex)} exceeds {fmtINR(Number(budget))}.
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
              <div className="gauge-value">{fmtTonnes(simFinal.projected_emissions_kg)}</div>
              <div className="gauge-sub">Baseline {fmtTonnes(simFinal.baseline_emissions_kg)}</div>
            </div>
            <div className="gauge">
              <div className="gauge-label">REDUCTION</div>
              <div className="gauge-value">{fmtPct(simFinal.reduction_percent)}</div>
              <div className="gauge-sub">{fmtTonnes(simFinal.total_co2_saving_kg)} avoided</div>
            </div>
          </div>
          <div className="table-wrap" style={{ overflow: 'visible' }}>
            <table className="data" style={{ minWidth: 0 }}>
              <tbody>
                <tr><td>Total CAPEX</td><td className="n mono"><b>{fmtINR(simFinal.total_capex)}</b></td></tr>
                <tr><td>Annual saving</td><td className="n mono"><b>{fmtINR(simFinal.annual_saving)}</b></td></tr>
                <tr><td>Payback</td><td className="n mono"><b>{fmtYears(simFinal.payback_years)}</b></td></tr>
              </tbody>
            </table>
          </div>
          {simKind === 'k1-live' ? (
            <div className="notice" style={{ border: '1px solid var(--low)', color: 'var(--low)' }}>
              <b>K1 live simulation</b> — totals served by POST /api/scenarios/{'{id}'}/simulate.
            </div>
          ) : (
            <div className="notice">
              <b>Local Module-K math</b> — K1 simulate endpoint unreachable (or not yet served);
              same rules (payback null when saving ≤ 0, projected floored at 0). Logged in
              <span className="mono"> docs/phase2/p1_integration_log.md</span>.
            </div>
          )}
          <button className="btn btn-primary" type="button">Save scenario (demo)</button>
        </div>
      </div>
    </>
  )
}
