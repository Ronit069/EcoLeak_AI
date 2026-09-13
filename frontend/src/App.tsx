import { Navigate, Route, Routes } from 'react-router-dom'
import { Chrome } from './components/Chrome'
import { LeftRail } from './components/LeftRail'
import { CommandCenter } from './components/CommandCenter'
import { AppProvider, useApp } from './state/AppContext'
import { Dashboard } from './pages/Dashboard'
import { LeakMapPage } from './pages/LeakMapPage'
import { DataActivities } from './pages/DataActivities'
import { ProcessMap } from './pages/ProcessMap'
import { Recommendations } from './pages/Recommendations'
import { Scenarios } from './pages/Scenarios'
import { Reports } from './pages/Reports'
import { Settings } from './pages/Settings'
import { Onboarding } from './pages/Onboarding'
import { ROI } from './pages/ROI'
import { Login } from './pages/Login'

function AuthenticatedApp() {
  return (
    <div className="app">
      <Chrome />
      <div className="body">
        <LeftRail />
        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leak-map" element={<LeakMapPage />} />
            <Route path="/data" element={<DataActivities />} />
            <Route path="/processes" element={<ProcessMap />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/scenarios" element={<Scenarios />} />
            <Route path="/roi" element={<ROI />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <CommandCenter />
    </div>
  )
}

function Gate() {
  const { authed } = useApp()
  return authed ? <AuthenticatedApp /> : <Login />
}

export function App() {
  return (
    <AppProvider>
      <Gate />
    </AppProvider>
  )
}
