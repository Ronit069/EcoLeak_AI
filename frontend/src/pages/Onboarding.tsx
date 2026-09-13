// Modules A/B — Onboarding wizard: Organization → Facility → Reporting Period → Process.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ApiError, createFacility, createOrganization, createProcess, createReportingPeriod,
} from '../lib/api'
import { useApp } from '../state/AppContext'
import { Banner, SectionHead } from '../components/ui'

const STEPS = ['Organization', 'Facility', 'Reporting Period', 'Process'] as const

export function Onboarding() {
  const { refresh } = useApp()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [orgId, setOrgId] = useState('')
  const [facilityId, setFacilityId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const [org, setOrg] = useState({ name: '', industry_sector: 'Textile', country: 'India', state: 'Gujarat', currency_code: 'INR', organization_size: 'MEDIUM' })
  const [facility, setFacility] = useState({ name: '', facility_code: '', country: 'India', state: 'Gujarat', annual_production: '1000', production_unit: 'tonne', working_days_per_year: '300', working_hours_per_day: '16' })
  const [period, setPeriod] = useState({ period_type: 'ANNUAL', start_date: '2025-04-01', end_date: '2026-03-31', status: 'DRAFT' })
  const [process, setProcess] = useState({ name: 'Boiler', process_code: 'PRC-BLR', sequence_no: '1', process_category: 'Utilities' })

  async function submit() {
    setError(null)
    try {
      if (step === 0) {
        const r = await createOrganization({ ...org })
        setOrgId(r.id); setStep(1)
      } else if (step === 1) {
        const r = await createFacility({
          organization_id: orgId || undefined, ...facility,
          annual_production: facility.annual_production, working_days_per_year: Number(facility.working_days_per_year), working_hours_per_day: facility.working_hours_per_day,
        })
        setFacilityId(r.id); setStep(2)
      } else if (step === 2) {
        await createReportingPeriod(facilityId, { ...period })
        setStep(3)
      } else {
        await createProcess(facilityId, { ...process, sequence_no: Number(process.sequence_no) })
        setDone('Facility profile complete. You can continue mapping processes in Process Map.')
        refresh()
      }
    } catch (e) {
      setError(e instanceof ApiError ? `${e.errorCode ?? e.status}: ${e.message}` : (e instanceof Error ? e.message : 'Failed'))
    }
  }

  return (
    <>
      <div className="panel-head">
        <span className="panel-title">Factory Onboarding</span>
        <span className="panel-sub">profile · facility · period · process</span>
      </div>
      <div className="panel-body">
        <div className="wizard-steps">
          {STEPS.map((s, i) => (
            <div key={s} className={`step ${i === step ? 'active' : ''}`}>{String(i + 1).padStart(2, '0')} {s}</div>
          ))}
        </div>

        {error ? <Banner kind="error" title="VALIDATION">{error}</Banner> : null}
        {done ? (
          <>
            <Banner kind="info" title="COMPLETE">{done}</Banner>
            <button className="primary" onClick={() => navigate('/')}>GO TO DASHBOARD</button>
          </>
        ) : null}

        {!done && step === 0 ? (
          <div className="form-grid">
            <div className="field"><label htmlFor="on">Organization name</label><input id="on" value={org.name} onChange={(e) => setOrg({ ...org, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="os">Industry sector</label><input id="os" value={org.industry_sector} onChange={(e) => setOrg({ ...org, industry_sector: e.target.value })} /></div>
            <div className="field"><label htmlFor="oc">Country</label><input id="oc" value={org.country} onChange={(e) => setOrg({ ...org, country: e.target.value })} /></div>
            <div className="field"><label htmlFor="oss">Size</label>
              <select id="oss" value={org.organization_size} onChange={(e) => setOrg({ ...org, organization_size: e.target.value })}>
                <option value="SMALL">SMALL</option><option value="MEDIUM">MEDIUM</option>
              </select>
            </div>
            <div className="field"><label htmlFor="ocur">Currency (ISO)</label><input id="ocur" value={org.currency_code} onChange={(e) => setOrg({ ...org, currency_code: e.target.value.toUpperCase() })} /></div>
          </div>
        ) : null}

        {!done && step === 1 ? (
          <div className="form-grid">
            <div className="field"><label htmlFor="fn">Facility name</label><input id="fn" value={facility.name} onChange={(e) => setFacility({ ...facility, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="fc">Facility code</label><input id="fc" value={facility.facility_code} onChange={(e) => setFacility({ ...facility, facility_code: e.target.value })} /></div>
            <div className="field"><label htmlFor="fp">Annual production</label><input id="fp" value={facility.annual_production} onChange={(e) => setFacility({ ...facility, annual_production: e.target.value })} inputMode="decimal" /></div>
            <div className="field"><label htmlFor="fpu">Production unit</label><input id="fpu" value={facility.production_unit} onChange={(e) => setFacility({ ...facility, production_unit: e.target.value })} /></div>
            <div className="field"><label htmlFor="fd">Working days/year (0–366)</label><input id="fd" value={facility.working_days_per_year} onChange={(e) => setFacility({ ...facility, working_days_per_year: e.target.value })} inputMode="numeric" /></div>
            <div className="field"><label htmlFor="fh">Working hours/day (0–24)</label><input id="fh" value={facility.working_hours_per_day} onChange={(e) => setFacility({ ...facility, working_hours_per_day: e.target.value })} inputMode="decimal" /></div>
          </div>
        ) : null}

        {!done && step === 2 ? (
          <div className="form-grid">
            <div className="field"><label htmlFor="pt">Period type</label>
              <select id="pt" value={period.period_type} onChange={(e) => setPeriod({ ...period, period_type: e.target.value })}>
                <option>ANNUAL</option><option>QUARTERLY</option><option>MONTHLY</option><option>CUSTOM</option>
              </select>
            </div>
            <div className="field"><label htmlFor="psd">Start date</label><input id="psd" type="date" value={period.start_date} onChange={(e) => setPeriod({ ...period, start_date: e.target.value })} /></div>
            <div className="field"><label htmlFor="ped">End date (≥ start)</label><input id="ped" type="date" value={period.end_date} onChange={(e) => setPeriod({ ...period, end_date: e.target.value })} /></div>
          </div>
        ) : null}

        {!done && step === 3 ? (
          <div className="form-grid">
            <div className="field"><label htmlFor="pn">Process name</label><input id="pn" value={process.name} onChange={(e) => setProcess({ ...process, name: e.target.value })} /></div>
            <div className="field"><label htmlFor="pc">Process code</label><input id="pc" value={process.process_code} onChange={(e) => setProcess({ ...process, process_code: e.target.value })} /></div>
            <div className="field"><label htmlFor="pseq">Sequence (&gt;0)</label><input id="pseq" value={process.sequence_no} onChange={(e) => setProcess({ ...process, sequence_no: e.target.value })} inputMode="numeric" /></div>
            <div className="field"><label htmlFor="pcat">Category</label><input id="pcat" value={process.process_category} onChange={(e) => setProcess({ ...process, process_category: e.target.value })} /></div>
          </div>
        ) : null}

        {!done ? (
          <div className="section">
            <SectionHead title={`Step ${step + 1} of ${STEPS.length}`} />
            <div className="btn-row">
              <button onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>BACK</button>
              <button className="primary" onClick={submit}>{step === STEPS.length - 1 ? 'FINISH' : 'CONTINUE'}</button>
            </div>
          </div>
        ) : null}
      </div>
    </>
  )
}
