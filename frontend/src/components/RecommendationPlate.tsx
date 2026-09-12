import { useState } from 'react'
import type { RecommendationOutputItem } from '../lib/contracts'
import { fmtINR, fmtTonnes, fmtYears } from '../lib/format'
import { fmtCostPerTonne } from '../lib/format'
import { ScoreMeter } from './badges'

export function RecommendationPlate({ rec }: { rec: RecommendationOutputItem }) {
  const [status, setStatus] = useState(rec.status)
  const impact = rec.impact
  return (
    <article className="rec" aria-labelledby={`rec-${rec.id}-title`}>
      <div className="rec-top">
        <div className="rec-rank" aria-label={`Rank ${rec.rank}`}>
          {String(rec.rank).padStart(2, '0')}<small>RANK</small>
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="rec-code">{rec.intervention_code} · targets hotspot {rec.hotspot_id.slice(-4)}</div>
          <h3 id={`rec-${rec.id}-title`}>{rec.intervention_title}</h3>
          <div className="mono" style={{ fontSize: '.8rem' }}>
            Final <b>{rec.final_score?.toFixed(1) ?? '—'}</b> · Confidence {rec.confidence_score ?? '—'}/100 · {status}
          </div>
        </div>
      </div>
      <div className="score-grid">
        <ScoreMeter label="Carbon" value={rec.carbon_saving_score} />
        <ScoreMeter label="Financial" value={rec.financial_return_score} />
        <ScoreMeter label="Feasibility" value={rec.feasibility_score} />
        <ScoreMeter label="Circularity" value={rec.circularity_score} />
        <ScoreMeter label="Speed" value={rec.implementation_speed_score} />
        <ScoreMeter label="Confidence" value={rec.confidence_score} />
      </div>
      {rec.explanation && (
        <p style={{ padding: '0 16px', fontSize: '.86rem', color: 'var(--legend-ink)' }}>{rec.explanation}</p>
      )}
      <div className="impact-strip" role="table" aria-label="Impact assessment">
        <div role="cell"><span>CAPEX</span><b>{fmtINR(impact?.estimated_capex)}</b></div>
        <div role="cell"><span>Annual saving</span><b>{fmtINR(impact?.estimated_annual_saving)}</b></div>
        <div role="cell"><span>CO₂ saving</span><b>{fmtTonnes(impact?.estimated_co2_saving_kg)}</b></div>
        <div role="cell"><span>Payback</span><b>{fmtYears(impact?.payback_years)}</b></div>
        <div role="cell"><span>Cost per tCO₂e</span><b>{fmtCostPerTonne(impact?.cost_per_tonne_co2_avoided)}</b></div>
      </div>
      <div className="rec-actions">
        <button
          className="btn btn-primary"
          disabled={status !== 'SUGGESTED'}
          onClick={() => setStatus('SHORTLISTED')}
        >
          {status === 'SUGGESTED' ? 'Shortlist intervention' : `Status: ${status}`}
        </button>
        {status !== 'SUGGESTED' && (
          <button className="btn btn-ghost" onClick={() => setStatus('SUGGESTED')}>Reset (demo)</button>
        )}
        <span style={{ fontSize: '.76rem', color: 'var(--legend)' }}>
          J3 live: PATCH /api/recommendations/{rec.id.slice(0, 8)}… · M1 explanation stays evidence-bound
        </span>
      </div>
    </article>
  )
}
