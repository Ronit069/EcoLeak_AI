// Auth Gate — Industrial Terminal Sign-in
import { useState } from 'react'
import { ApiError, DEMO_IDS, clearAuth, probeAuth, setAuth, type StoredAuth } from '../lib/api'
import { useApp } from '../state/AppContext'

const ROLES = [
  'SUSTAINABILITY_ANALYST', 'FACTORY_OPERATOR', 'ORGANIZATION_ADMIN',
  'VIEWER', 'REGULATOR_READ_ONLY', 'SYSTEM_ADMIN',
]

export function Login() {
  const { login, setMode } = useApp()
  const [method, setMethod] = useState<'stub' | 'jwt'>('stub')
  const [organizationId, setOrganizationId] = useState(DEMO_IDS.organization_id)
  const [role, setRole] = useState('SUSTAINABILITY_ANALYST')
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setError(null); setBusy(true)
    const auth: StoredAuth = method === 'jwt'
      ? { method, organizationId, role, token }
      : { method, organizationId, role, token: '' }
    try {
      setAuth(auth)
      await probeAuth()
      login(auth)
    } catch (e) {
      clearAuth()
      if (e instanceof ApiError && e.status === 401) setError('401 — not authenticated. Verify API credentials or access token.')
      else if (e instanceof ApiError && e.status === 403) setError('403 — wrong tenant or insufficient role authorization.')
      else setError(e instanceof Error ? `Authentication service unreachable: ${e.message}` : 'Authentication failed.')
    } finally { setBusy(false) }
  }

  function demo() {
    setMode('mock')
    login({ method: 'stub', organizationId: DEMO_IDS.organization_id, role: 'SUSTAINABILITY_ANALYST', token: '' })
  }

  return (
    <div className="login-wrap">
      <div className="login">
        <div className="login-head">
          <div className="logo" style={{ fontSize: 'var(--fs-xl)', fontWeight: 700 }}>
            ECO<span style={{ color: 'var(--cyan)' }}>LEAK</span> <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--ink-3)', fontWeight: 400, fontFamily: 'var(--mono)' }}>INSTRUMENT v2</span>
          </div>
          <div className="mono tiny faint" style={{ marginTop: 4 }}>
            Industrial Emission Leak-Point Detector &amp; Circular Alternative Recommender
          </div>
        </div>

        <div style={{ margin: '20px 0 16px', padding: '10px 12px', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-xs)' }}>
          <div className="label">Plant Intelligence Access Gate</div>
          <p className="tiny muted" style={{ margin: '4px 0 0', lineHeight: 1.4 }}>
            Authenticate with organization context to access deterministic carbon accounting, hotspot detection, and circular ROI simulations.
          </p>
        </div>

        <div className="login-tabs" role="tablist" style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <button role="tab" aria-selected={method === 'stub'} className={method === 'stub' ? 'primary' : ''} onClick={() => setMethod('stub')}>
            Tenant Credentials
          </button>
          <button role="tab" aria-selected={method === 'jwt'} className={method === 'jwt' ? 'primary' : ''} onClick={() => setMethod('jwt')}>
            JWT Bearer Token
          </button>
        </div>

        {error ? (
          <div className="banner error" style={{ marginBottom: 12 }}>
            <div><strong>AUTH REJECTED: </strong>{error}</div>
          </div>
        ) : null}

        {method === 'stub' ? (
          <div className="form-grid" style={{ gridTemplateColumns: '1fr', gap: 10 }}>
            <div className="field">
              <label htmlFor="org">Organization Identifier (Tenant ID)</label>
              <input id="org" value={organizationId} onChange={(e) => setOrganizationId(e.target.value)} spellCheck={false} />
            </div>
            <div className="field">
              <label htmlFor="role">Operational User Role</label>
              <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
          </div>
        ) : (
          <div className="field" style={{ marginBottom: 12 }}>
            <label htmlFor="tok">JWT Access Token</label>
            <textarea id="tok" rows={3} value={token} onChange={(e) => setToken(e.target.value)} placeholder="eyJhbGciOi..." spellCheck={false} />
          </div>
        )}

        <div className="btn-row" style={{ marginTop: 16 }}>
          <button className="primary" onClick={submit} disabled={busy} style={{ flex: 1 }}>
            {busy ? 'AUTHENTICATING…' : 'SIGN IN TO WORKSTATION'}
          </button>
          <button onClick={demo} style={{ flex: 1 }}>
            EXPLORE DEMO FACTORY (OFFLINE)
          </button>
        </div>

        <div className="mono tiny faint" style={{ marginTop: 14, textAlign: 'center', lineHeight: 1.4 }}>
          Demo factory simulates Shakti Textiles (1,000 t/yr mill in Surat, Gujarat) using frozen audit datasets.
        </div>
      </div>
    </div>
  )
}
