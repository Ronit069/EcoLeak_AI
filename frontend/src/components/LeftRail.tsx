// EcoLeak AI — Industrial Left Navigation Rail
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Activity, CircleDollarSign, Database, FileText, GitBranch,
  LayoutDashboard, Radar, Recycle, Settings, SlidersHorizontal, Building2, ChevronDown, ChevronRight,
} from 'lucide-react'
import { fetchHotspots } from '../lib/api'
import { useGroup } from '../lib/useApi'
import { fmtPct } from '../lib/format'
import { useApp } from '../state/AppContext'
import { SeverityBadge } from './ui'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/leak-map', label: 'Carbon Leak Map', icon: Radar },
  { to: '/data', label: 'Data & Activities', icon: Database },
  { to: '/processes', label: 'Process Map', icon: GitBranch },
  { to: '/recommendations', label: 'Recommendations', icon: Recycle },
  { to: '/scenarios', label: 'Scenario Simulator', icon: SlidersHorizontal },
  { to: '/roi', label: 'Carbon ROI', icon: CircleDollarSign },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/onboarding', label: 'Factory Profile', icon: Building2 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function LeftRail() {
  const { ids, facilities, selection, select, refreshKey } = useApp()
  const hotspots = useGroup(() => fetchHotspots(ids.facility_id, ids.reporting_period_id), [ids.facility_id, ids.reporting_period_id, refreshKey])
  const activeFacility = facilities.find((f) => f.id === ids.facility_id)
  const leaks = hotspots.data?.hotspots ?? []
  const [leaksOpen, setLeaksOpen] = useState(true)

  return (
    <nav className="rail" aria-label="Primary Instrument Navigation">
      <div className="facility-card">
        <div className="name">{activeFacility?.name ?? 'Shakti Textiles — Surat Unit 1'}</div>
        <div className="meta">
          <span>{activeFacility?.city ?? 'Surat'}, {activeFacility?.state ?? 'Gujarat'}</span>
          <span>1,000 t/yr</span>
        </div>
      </div>

      <div className="rail-group">
        <span className="label">INSTRUMENT MODULES</span>
      </div>
      <div className="rail-nav">
        {NAV_ITEMS.map((it) => {
          const Icon = it.icon
          return (
            <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => (isActive ? 'active' : '')}>
              <Icon aria-hidden="true" />
              <span>{it.label}</span>
            </NavLink>
          )
        })}
      </div>

      <div className="rail-group" style={{ marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button
          onClick={() => setLeaksOpen(!leaksOpen)}
          style={{
            background: 'transparent',
            border: 0,
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            cursor: 'pointer',
            textAlign: 'left'
          }}
        >
          <span className="label">PROCESS LEAK INDEX</span>
          {leaksOpen ? <ChevronDown size={11} style={{ color: 'var(--ink-faint)' }} /> : <ChevronRight size={11} style={{ color: 'var(--ink-faint)' }} />}
        </button>
      </div>

      {leaksOpen ? (
        <div className="leak-rail-list">
          {hotspots.loading ? (
            <div className="tiny faint" style={{ padding: '6px 8px' }}>Auditing process streams…</div>
          ) : null}
          {!hotspots.loading && leaks.length === 0 ? (
            <div className="tiny faint" style={{ padding: '6px 8px' }}>No leaks detected</div>
          ) : null}
          {leaks.map((h) => {
            const isSelected = selection.hotspotId === h.id || selection.processId === h.process_id
            return (
              <div
                key={h.id}
                role="button"
                tabIndex={0}
                className={`leak-rail-item ${isSelected ? 'active' : ''}`}
                onClick={() => select({ hotspotId: h.id, processId: h.process_id ?? null })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    select({ hotspotId: h.id, processId: h.process_id ?? null })
                  }
                }}
              >
                <span className="proc-name">{h.process_name ?? 'Unassigned'}</span>
                <span className="proc-pct">{fmtPct(h.contribution_percent, 1)}</span>
                <SeverityBadge severity={h.severity} />
              </div>
            )
          })}
        </div>
      ) : null}
    </nav>
  )
}
