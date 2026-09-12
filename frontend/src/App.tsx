import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { DashboardPage } from './pages/Dashboard'
import { RecommendationsPage } from './pages/Recommendations'
import { ProcessesPage } from './pages/Processes'
import { DataInputPage } from './pages/DataInput'
import { ProfilingPage } from './pages/Profiling'
import { ScenariosPage } from './pages/Scenarios'
import { ReportsPage } from './pages/Reports'
import {
  getFallbackGroups, resolveMockMode, setMockModeOverride, subscribeFallbacks,
  subscribeMockMode, usePhase2ModeLabel,
} from './lib/api'

function Icon({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

const LINKS = [
  { to: '/', label: 'Dashboard', end: true, icon: 'M3 12l9-8 9 8 M5 10v10h5v-6h4v6h5V10' },
  { to: '/recommendations', label: 'Recommendations', icon: 'M12 2l2.6 5.6 6 .7-4.4 4.1 1.2 5.9L12 15.4 6.6 18.3l1.2-5.9L3.4 8.3l6-.7z' },
  { to: '/processes', label: 'Processes', icon: 'M4 6h16 M4 12h16 M4 18h16 M8 6v12 M16 6v12' },
  { to: '/data', label: 'Data input', icon: 'M12 3v12 M7 10l5 5 5-5 M4 21h16' },
  { to: '/profiling', label: 'Profiling', icon: 'M4 21V10l8-6 8 6v11 M9 21v-6h6v6' },
  { to: '/scenarios', label: 'Scenarios', icon: 'M4 19V5 M4 15c4-8 6 2 10-6 2-4 3-4 6-4 M4 19h16' },
  { to: '/reports', label: 'Reports', icon: 'M6 3h9l4 4v14H6z M15 3v4h4 M9 12h7 M9 16h7' }
]

/**
 * Phase 2: "using demo data" banner. Appears when USE_MOCK_DATA=mock mode
 * (forced) or when any endpoint group has fallen back to mocks in auto mode.
 * Also exposes the runtime mode toggle (localStorage override) so a demo or
 * audit check can force either side without rebuilding.
 */
export function DemoDataBanner() {
  const [groups, setGroups] = useState<string[]>(getFallbackGroups())
  const [mode, setMode] = useState(resolveMockMode())
  const [tick, setTick] = useState(0)
  useEffect(() => subscribeFallbacks(() => { setGroups(getFallbackGroups()); setTick(t => t + 1) }), [])
  useEffect(() => subscribeMockMode(() => setMode(resolveMockMode())), [])
  void tick

  const forcedMock = mode === 'mock'
  const fellBack = groups.length > 0
  if (!forcedMock && !fellBack) return null

  const next = (m: typeof mode) => { setMockModeOverride(m); setMode(m) }
  return (
    <div role="status" aria-live="polite"
      style={{
        background: '#FFF4E0', border: '1px solid #E4A11B', color: '#5C4400',
        borderRadius: 10, padding: '8px 14px', marginBottom: 14,
        display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', fontSize: '.86rem',
      }}>
      <b>Using demo data</b>
      {forcedMock
        ? <span>USE_MOCK_DATA is forced to mock mode — Phase 1 frozen payloads shown.</span>
        : <span>live API unavailable for: <b>{groups.join(', ')}</b> — fallen back to Phase 1 mocks for those groups.</span>}
      <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6 }}>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '.76rem' }} onClick={() => next('live')}>Force live</button>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '.76rem' }} onClick={() => next('mock')}>Force mock</button>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '.76rem' }} onClick={() => { localStorage.removeItem('ecoleak.useMockData'); next('auto') }}>Auto</button>
      </span>
    </div>
  )
}

export function App() {
  return (
    <div className="shell">
      <aside className="rail" aria-label="Primary">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">E</span>
          <span><b>EcoLeak AI</b><small>CARBON LEAK BENCH · P1</small></span>
        </div>
        <nav className="nav">
          {LINKS.map(l => (
            <NavLink key={l.to} to={l.to} end={l.end}>
              <span className="tick" aria-hidden="true" />
              <Icon d={l.icon} />
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <span className="mode-pill"><span className="mode-dot" />{usePhase2ModeLabel()}</span>
          <p style={{ margin: '10px 0 0' }}>
            Phase 2 live API with per-group mock fallback · USE_MOCK_DATA gate · G2/J2/N1/N2/B2/C3/K1.
          </p>
        </div>
      </aside>
      <div className="main">
        <main className="content">
          <DemoDataBanner />
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/processes" element={<ProcessesPage />} />
            <Route path="/data" element={<DataInputPage />} />
            <Route path="/profiling" element={<ProfilingPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="*" element={<div className="notice"><b>Not found.</b> This build ships six routes only.</div>} />
          </Routes>
          <footer style={{ marginTop: 34, fontSize: '.76rem', color: 'var(--legend)' }}>
            Phase 2 · USE_MOCK_DATA gate (auto: live → per-group mock fallback). Live map: A2/A5/A9 · B2 · C3 · G2 · J2 · M1 · N1 · N2 · K1.
            Integration log: <span className="mono">docs/phase2/p1_integration_log.md</span>
          </footer>
        </main>
      </div>
    </div>
  )
}