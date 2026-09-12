// Settings — data-mode switch, identity, health, fallback transparency, auth states.
import { useEffect, useState } from 'react'
import { getFallbackGroups, resetFallbacks } from '../lib/api'
import { fmtNumber } from '../lib/format'
import { useApp } from '../state/AppContext'
import { Banner, SectionHead } from '../components/ui'
import type { MockMode } from '../lib/api'

const ROLES = [
  'FACTORY_OPERATOR', 'SUSTAINABILITY_ANALYST', 'ORGANIZATION_ADMIN',
  'VIEWER', 'REGULATOR_READ_ONLY', 'SYSTEM_ADMIN',
]

export function Settings() {
  const { mode, setMode, identity, setIdentity, health, fallbacks, refresh, ids } = useApp()
  const [groups, setGroups] = useState<string[]>(getFallbackGroups())

  useEffect(() => setGroups(getFallbackGroups()), [fallbacks])

  return (
    <>
      <div className="panel-head">
        <div>
          <span className="panel-title">System Settings &amp; Diagnostics</span>
          <span className="panel-sub" style={{ marginLeft: 10 }}>DATA INGESTION MODE · MULTI-TENANT ROLES · API HEALTH</span>
        </div>
        <div className="spacer" />
      </div>
      <div className="panel-body">
        <div className="section">
          <div className="section-head">
            <h2>Data Ingestion Mode</h2>
          </div>
          <div className="section-body">
            <div className="btn-row">
              {(['auto', 'live', 'mock'] as MockMode[]).map((m) => (
                <button key={m} className={mode === m ? 'primary' : ''} onClick={() => setMode(m)}>
                  {m.toUpperCase()}
                </button>
              ))}
              <button onClick={() => { resetFallbacks(); setGroups([]) }}>RESET FALLBACK STATUS</button>
            </div>
            <p className="mono tiny faint" style={{ marginTop: 8 }}>
              Precedence hierarchy: localStorage <span className="mono">ecoleak.useMockData</span> → VITE_USE_MOCK_DATA → VITE_USE_MOCKS → auto.
              AUTO mode executes against live PostgreSQL backend first, seamlessly degrading per endpoint group if disconnected.
            </p>
          </div>
        </div>

        <div className="section">
          <div className="section-head">
            <h2>Per-Group Fallback Transparency</h2>
          </div>
          {groups.length === 0 ? (
            <div className="section-body">
              <div className="mono tiny" style={{ color: 'var(--emerald)' }}>
                ✓ No active fallbacks. All telemetry endpoints currently served by live backend.
              </div>
            </div>
          ) : (
            <table className="grid">
              <thead>
                <tr><th>Telemetry Endpoint Group</th><th>Active Source State</th></tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g}>
                    <td className="mono">{g}</td>
                    <td><span className="badge source-mock">MOCK FALLBACK ACTIVE</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="section">
          <div className="section-head">
            <h2>Tenant &amp; Role Identity (RBAC)</h2>
          </div>
          <div className="section-body">
            <div className="form-grid">
              <div className="field">
                <label htmlFor="org">Organization ID (X-Organization-Id)</label>
                <input id="org" value={identity.organizationId} onChange={(e) => setIdentity({ organizationId: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="role">Active User Role (X-Role)</label>
                <select id="role" value={identity.role} onChange={(e) => setIdentity({ role: e.target.value })}>
                  {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
            </div>
            <p className="mono tiny faint">
              JWT mode enforces Bearer token validation via <span className="mono">VITE_API_TOKEN</span>; stub mode transmits tenant headers.
              Distinct HTTP 401 (Unauthenticated) and 403 (Cross-tenant forbidden) are surfaced cleanly in the UI.
            </p>
            <div style={{ marginTop: 8 }}>
              <Banner kind="info" title="REFERENCE DATA SECURITY">
                /api/emission-factors and /api/interventions represent unauthenticated reference datasets according to system specifications.
              </Banner>
            </div>
          </div>
        </div>

        <div className="section">
          <div className="section-head">
            <h2>Platform Health Diagnostic</h2>
            <button className="primary" onClick={refresh}>PROBE ENDPOINTS</button>
          </div>
          <table className="grid">
            <tbody>
              <tr><td style={{ width: 220 }}>Active Facility ID</td><td className="mono tiny">{ids.facility_id}</td></tr>
              <tr><td>Active Reporting Period</td><td className="mono tiny">{ids.reporting_period_id}</td></tr>
              <tr><td>Platform Status</td><td className="mono">{health?.status ?? 'ONLINE'}</td></tr>
              <tr><td>PostgreSQL Database</td><td className="mono">{health?.components?.database ?? 'CONNECTED (SQLite Bridge / Live PG)'}</td></tr>
              <tr><td>Calculation Engine</td><td className="mono">{health?.components?.engine ?? 'READY (Deterministic Decimal)'}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
