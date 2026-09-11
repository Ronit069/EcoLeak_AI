import { NavLink, Route, Routes } from 'react-router-dom'
import { DashboardPage } from './pages/Dashboard'
import { RecommendationsPage } from './pages/Recommendations'
import { ProcessesPage } from './pages/Processes'
import { DataInputPage } from './pages/DataInput'
import { ProfilingPage } from './pages/Profiling'
import { ScenariosPage } from './pages/Scenarios'
import { useMockBadge } from './lib/api'

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
  { to: '/scenarios', label: 'Scenarios', icon: 'M4 19V5 M4 15c4-8 6 2 10-6 2-4 3-4 6-4 M4 19h16' }
]

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
          <span className="mode-pill"><span className="mode-dot" />{useMockBadge()}</span>
          <p style={{ margin: '10px 0 0' }}>
            Frozen contracts · Shakti Textiles mock · INR · swap to G2/J2/N1 without rewrites.
          </p>
        </div>
      </aside>
      <div className="main">
        <main className="content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/processes" element={<ProcessesPage />} />
            <Route path="/data" element={<DataInputPage />} />
            <Route path="/profiling" element={<ProfilingPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="*" element={<div className="notice"><b>Not found.</b> This Phase 1 build ships six routes only.</div>} />
          </Routes>
          <footer style={{ marginTop: 34, fontSize: '.76rem', color: 'var(--legend)' }}>
            Phase 1 operates on <span className="mono">mocks/*.json</span> (validated 9/9). Live swap map: hotspots → G2,
            recommendations → J2, dashboard → N1, leak-map → N2. Reports PDF returns 501 until Phase 2.
          </footer>
        </main>
      </div>
    </div>
  )
}
