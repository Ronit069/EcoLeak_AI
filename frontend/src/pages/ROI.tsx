// Module K/L — Carbon ROI & Financial Feasibility Analysis
import { useMemo, useState } from 'react'
import { fetchRecommendations } from '../lib/api'
import { fmtCo2e, fmtInr, fmtNumber, fmtPayback, num } from '../lib/format'
import { useGroup } from '../lib/useApi'
import { useApp } from '../state/AppContext'
import { KpiCard } from '../components/KpiCard'
import { Banner, Empty, Loading, SectionHead, SourceStamp } from '../components/ui'

export function ROI() {
  const { ids, refreshKey } = useApp()
  const recs = useGroup(() => fetchRecommendations(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const items = recs.data?.recommendations ?? []

  const totals = useMemo(() => {
    let saving = 0, capex = 0, co2 = 0
    for (const r of items) {
      saving += num(r.impact?.estimated_annual_saving) ?? 0
      capex += num(r.impact?.estimated_capex) ?? 0
      co2 += num(r.impact?.estimated_co2_saving_kg) ?? 0
    }
    return {
      saving,
      capex,
      co2,
      payback: saving > 0 ? capex / saving : null,
      perTonne: co2 > 0 ? capex / (co2 / 1000) : null,
    }
  }, [items])

  if (recs.loading) return <div className="panel-body"><Loading what="roi economics" /></div>
  if (recs.error) return <div className="panel-body"><Banner kind="error" title="ROI AUDIT FAILED">{recs.error.message}</Banner></div>

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">Carbon ROI &amp; Financial Feasibility</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>CAPITAL EXPENDITURE · OPERATIONAL SAVINGS · PAYBACK HORIZON</span>
        </div>
        <div className="spacer" />
        <SourceStamp source={recs.source} />
      </div>

      <div className="panel-body">
        {items.length === 0 ? (
          <Empty>NO ASSESSED INTERVENTIONS — GENERATE RECOMMENDATIONS TO PROCEED</Empty>
        ) : (
          <>
            <div className="kpi-grid">
              <KpiCard
                label="Annual Savings Potential"
                value={totals.saving}
                format={(v) => fmtInr(v)}
                accent="var(--emerald)"
                foot={<span className="faint">Across 5 interventions</span>}
              />
              <KpiCard
                label="Combined Capital CAPEX"
                value={totals.capex}
                format={(v) => fmtInr(v)}
                accent="var(--cyan)"
                foot={<span className="faint">Implementation capital</span>}
              />
              <KpiCard
                label="Blended Payback Horizon"
                value={totals.payback}
                format={(v) => fmtPayback(v, totals.saving)}
                accent="var(--amber)"
                foot={<span className="faint">Net simple payback</span>}
              />
              <KpiCard
                label="Total Annual CO₂ Avoided"
                value={totals.co2}
                format={(v) => (v === null ? '—' : fmtCo2e(v))}
                accent="var(--emerald)"
                foot={<span className="faint">Operational abatement</span>}
              />
              <KpiCard
                label="Average Abatement Cost"
                value={totals.perTonne}
                format={(v) => (v === null ? '—' : `₹${fmtNumber(v, 0)}`)}
                unit="/tCO₂e"
                accent="var(--cyan)"
                foot={<span className="faint">CAPEX efficiency</span>}
              />
            </div>

            {/* Marginal Abatement Cost (MAC) Scatter Plot */}
            <div className="section">
              <div className="section-head">
                <h2>Marginal Abatement Cost &amp; Return Matrix</h2>
                <span className="mono tiny faint">
                  TOP-RIGHT = MAXIMUM CO₂ ABATEMENT + RAPID FINANCIAL RETURN
                </span>
              </div>
              <div className="section-body">
                <Scatter items={items} />
              </div>
            </div>

            {/* Detailed Intervention Economics Table */}
            <div className="section">
              <div className="section-head">
                <h2>Intervention Capital &amp; Payback Ledger</h2>
                <span className="mono tiny faint">AUDITABLE FINANCIAL PARAMETERS</span>
              </div>
              <table className="grid">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Code</th>
                    <th>Intervention Title</th>
                    <th className="num">CO₂ Avoided</th>
                    <th className="num">CAPEX Investment</th>
                    <th className="num">Annual OPEX Saving</th>
                    <th className="num">Payback Period</th>
                    <th className="num">Feasibility (100)</th>
                    <th className="num">Confidence (100)</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id}>
                      <td className="num">{r.rank}</td>
                      <td className="mono tiny" style={{ color: 'var(--cyan)' }}>{r.intervention_code}</td>
                      <td style={{ fontWeight: 600 }}>{r.intervention_title}</td>
                      <td className="num" style={{ color: 'var(--cyan)' }}>{fmtCo2e(r.impact?.estimated_co2_saving_kg)}</td>
                      <td className="num">{fmtInr(r.impact?.estimated_capex)}</td>
                      <td className="num" style={{ color: 'var(--emerald)' }}>{fmtInr(r.impact?.estimated_annual_saving)}/yr</td>
                      <td className="num">{fmtPayback(r.impact?.payback_years, r.impact?.estimated_annual_saving)}</td>
                      <td className="num">{fmtNumber(r.feasibility_score, 0)}</td>
                      <td className="num">{fmtNumber(r.confidence_score, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  )
}

function Scatter({ items }: { items: Array<{ id: string; rank: number; intervention_code: string | null; intervention_title?: string | null; final_score: number | string | null; impact: { estimated_co2_saving_kg?: unknown; estimated_annual_saving?: unknown } | null }> }) {
  const [activeId, setActiveId] = useState<string | null>(null)

  const pts = useMemo(() => items.map((r) => ({
    id: r.id,
    code: r.intervention_code ?? '',
    title: r.intervention_title ?? 'Intervention',
    x: num(r.impact?.estimated_co2_saving_kg) ?? 0,
    y: num(r.impact?.estimated_annual_saving) ?? 0,
    score: num(r.final_score) ?? 0,
  })), [items])

  const maxX = Math.max(100000, ...pts.map((p) => p.x)) * 1.15
  const maxY = Math.max(700000, ...pts.map((p) => p.y)) * 1.15
  const W = 960, H = 360, P = 64
  const midX = P + (W - 2 * P) / 2
  const midY = P + (H - 2 * P) / 2

  const activePoint = pts.find((p) => p.id === activeId)

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{
          width: '100%',
          height: 'auto',
          background: 'radial-gradient(ellipse at 80% 20%, rgba(16, 185, 129, 0.08) 0%, rgba(10, 14, 22, 0.85) 100%)',
          borderRadius: 'var(--r)',
          border: '1px solid var(--glass-border)'
        }}
        role="img"
        aria-label="CO2 reduction versus financial return matrix"
      >
        <defs>
          <radialGradient id="quad-glow" cx="100%" cy="0%" r="100%">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
          </radialGradient>
          <filter id="bubble-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#06b6d4" floodOpacity="0.5" />
          </filter>
        </defs>

        {/* Priority 1 Quadrant Wash (Top-Right) */}
        <rect
          x={midX}
          y={P}
          width={W - P - midX}
          height={midY - P}
          fill="url(#quad-glow)"
          stroke="rgba(16, 185, 129, 0.25)"
          strokeWidth="1"
          strokeDasharray="4 4"
        />
        <text
          x={W - P - 14}
          y={P + 22}
          textAnchor="end"
          fill="#10b981"
          style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 700, letterSpacing: '0.06em' }}
        >
          ★ PRIORITY 1: HIGH SAVINGS &amp; ABATEMENT
        </text>

        {/* Grid lines */}
        <line x1={P} y1={H - P} x2={W - P} y2={H - P} stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1.5" />
        <line x1={P} y1={P} x2={P} y2={H - P} stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1.5" />
        <line x1={P} y1={midY} x2={W - P} y2={midY} stroke="rgba(255, 255, 255, 0.1)" strokeDasharray="4 4" />
        <line x1={midX} y1={P} x2={midX} y2={H - P} stroke="rgba(255, 255, 255, 0.1)" strokeDasharray="4 4" />

        {/* Axis Ticks & Values */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const tx = P + frac * (W - 2 * P)
          const valX = (frac * maxX) / 1000
          return (
            <g key={`tx-${frac}`}>
              <line x1={tx} y1={H - P} x2={tx} y2={H - P + 5} stroke="rgba(255, 255, 255, 0.25)" />
              <text x={tx} y={H - P + 18} textAnchor="middle" fill="#64748b" style={{ fontFamily: 'var(--mono)', fontSize: 9.5 }}>
                {valX === 0 ? '0' : `${valX.toFixed(0)}k`}
              </text>
            </g>
          )
        })}

        {[0, 0.33, 0.66, 1].map((frac) => {
          const ty = H - P - frac * (H - 2 * P)
          const valY = (frac * maxY) / 100000
          return (
            <g key={`ty-${frac}`}>
              <line x1={P - 5} y1={ty} x2={P} y2={ty} stroke="rgba(255, 255, 255, 0.25)" />
              <text x={P - 10} y={ty + 3} textAnchor="end" fill="#64748b" style={{ fontFamily: 'var(--mono)', fontSize: 9.5 }}>
                {valY === 0 ? '₹0' : `₹${valY.toFixed(1)}L`}
              </text>
            </g>
          )
        })}

        {/* Axis labels */}
        <text x={(W + P) / 2} y={H - 16} textAnchor="middle" fill="#94a3b8" style={{ fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.04em' }}>
          Annual Carbon Reduction (kgCO₂e avoided) →
        </text>
        <text x={18} y={(H + P) / 2} textAnchor="middle" transform={`rotate(-90 18 ${(H + P) / 2})`} fill="#94a3b8" style={{ fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.04em' }}>
          Annual OPEX Savings (₹ INR/yr) →
        </text>

        {/* Data points */}
        {pts.map((p) => {
          const cx = P + (p.x / maxX) * (W - 2 * P)
          const cy = H - P - (p.y / maxY) * (H - 2 * P)
          const rad = 9 + (p.score / 100) * 10
          const isHovered = activeId === p.id

          return (
            <g
              key={p.id}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setActiveId(p.id)}
              onMouseLeave={() => setActiveId(null)}
              onClick={() => setActiveId(p.id)}
            >
              {/* Outer halo */}
              <circle
                cx={cx}
                cy={cy}
                r={rad + (isHovered ? 6 : 3)}
                fill="none"
                stroke={isHovered ? '#10b981' : '#06b6d4'}
                strokeWidth={isHovered ? 2 : 1}
                strokeDasharray={isHovered ? '2 2' : undefined}
                opacity={isHovered ? 0.9 : 0.4}
              />
              {/* Inner bubble */}
              <circle
                cx={cx}
                cy={cy}
                r={rad}
                fill={isHovered ? 'rgba(16, 185, 129, 0.4)' : 'rgba(6, 182, 212, 0.25)'}
                stroke={isHovered ? '#10b981' : '#06b6d4'}
                strokeWidth="1.8"
                filter="url(#bubble-glow)"
              />
              {/* Center dot */}
              <circle cx={cx} cy={cy} r={2.5} fill="#ffffff" />
              {/* Code label */}
              <text
                x={cx}
                y={cy - rad - 7}
                textAnchor="middle"
                fill={isHovered ? '#ffffff' : '#e2e8f0'}
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10.5,
                  fontWeight: 700,
                  letterSpacing: '0.02em',
                  textShadow: '0 1px 3px rgba(0,0,0,0.8)',
                }}
              >
                {p.code}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Interactive Floating Detail Card */}
      {activePoint ? (
        <div
          style={{
            position: 'absolute',
            bottom: 24,
            right: 24,
            background: 'rgba(13, 19, 31, 0.92)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(6, 182, 212, 0.4)',
            borderRadius: 'var(--r)',
            padding: '12px 16px',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.7)',
            maxWidth: 320,
            pointerEvents: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 4 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: '#06b6d4' }}>
              {activePoint.code}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#10b981', fontWeight: 700 }}>
              SCORE {activePoint.score.toFixed(1)}/100
            </span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#f8fafc', marginBottom: 6 }}>
            {activePoint.title}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#cbd5e1', paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <span>CO₂: <strong style={{ color: '#06b6d4' }}>{fmtCo2e(activePoint.x)}/yr</strong></span>
            <span>Saving: <strong style={{ color: '#10b981' }}>{fmtInr(activePoint.y)}/yr</strong></span>
          </div>
        </div>
      ) : null}
    </div>
  )
}
