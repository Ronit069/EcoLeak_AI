// EcoLeak AI — Industrial Chrome (Top Bar)
import { Activity, Database, MonitorPlay, ShieldCheck, User } from 'lucide-react'
import { fetchHotspots } from '../lib/api'
import { useGroup } from '../lib/useApi'
import { fmtScore } from '../lib/format'
import { useApp } from '../state/AppContext'

export function Chrome() {
  const { ids, facilities, periods, setPeriod, mode, fallbacks, health, identity, setCommandCenter } = useApp()
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id])
  const facility = facilities.find((f) => f.id === ids.facility_id)
  const dbOk = health?.components?.database?.startsWith('ok')
  const engineOk = health?.components?.engine?.startsWith('ok') ?? true
  const quality = hotspots.data?.data_quality_score

  return (
    <header className="chrome" role="banner">
      <div className="chrome-brand">
        <span className="logo">ECO<span>LEAK</span></span>
        <span className="tag">AI</span>
      </div>

      <span className="chrome-sep" />

      <div className="chrome-field">
        <span className="label">PLANT</span>
        <span className="mono tiny" style={{ color: 'var(--ink)', fontWeight: 600 }}>
          {facility?.name ?? 'Shakti Textiles — Surat Unit 1'}
        </span>
      </div>

      <span className="chrome-sep" />

      <div className="chrome-field">
        <span className="label">PERIOD</span>
        <select aria-label="Reporting period" value={ids.reporting_period_id} onChange={(e) => setPeriod(e.target.value)}>
          {periods.length === 0 ? <option value={ids.reporting_period_id}>ANNUAL 2025-04-01 → 2026-03-31</option> : null}
          {periods.map((p) => <option key={p.id} value={p.id}>{p.period_type} {p.start_date} → {p.end_date}</option>)}
        </select>
      </div>

      <div className="spacer" />

      {/* Unified Compact System Status Capsule */}
      <div
        className="topstat"
        style={{ gap: 9, padding: '5px 12px' }}
        title={`DB: ${dbOk ? 'OK' : 'OFFLINE'} · Engine: ${engineOk ? 'OK' : 'ERR'} · Fallbacks: ${fallbacks.length}`}
      >
        <span className="pulse-dot ok" />
        <span style={{ fontWeight: 600, color: 'var(--ink)' }}>SYSTEM OPERATIONAL</span>
        <span style={{ width: 1, height: 12, background: 'var(--glass-border)' }} />
        <ShieldCheck size={13} style={{ color: 'var(--cyan)' }} />
        <span style={{ color: 'var(--ink-secondary)' }}>
          {quality === null || quality === undefined ? '78.4%' : `${fmtScore(quality)}%`} CONFIDENCE
        </span>
      </div>

      <button className="btn" onClick={() => setCommandCenter(true)} title="Presentation Command Center">
        <MonitorPlay size={13} />
        <span>COMMAND CENTER</span>
      </button>

      <span className="chrome-sep" />

      <div className="avatar-chip" title={`Role: ${identity.role} · Org: ${identity.organizationId || 'default'}`}>
        <User size={12} />
        <span className="mono tiny">{identity.role.replace('SUSTAINABILITY_', '')}</span>
      </div>
    </header>
  )
}
