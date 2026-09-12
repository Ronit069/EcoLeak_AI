import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { usePhase1Data, Loading } from './Dashboard'
import { profileFormSchema, type ProfileForm } from '../lib/zod'

// Module A — SME Profiling UI (A1–A9) with React Hook Form + Zod.
// Zod mirrors contracts/schemas.py: production ≥ 0 (=0 allowed, blocks intensity),
// working_days ≤ 366, working_hours ≤ 24, currency ^[A-Z]{3}$, end_date ≥ start_date.
export function ProfilingPage() {
  const { dataset, error, ready, sources, ids } = usePhase1Data()
  const [savedMsg, setSavedMsg] = useState<string | null>(null)
  const form = useForm<ProfileForm>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: {
      industry_sector: '', industry_subtype: '', country: '', state: '', city: '',
      organization_size: 'MEDIUM', currency_code: 'INR',
      annual_production: 1000, production_unit: 'tonne',
      working_days_per_year: 300, working_hours_per_day: 16,
      period_type: 'ANNUAL', start_date: '', end_date: '',
      scope_boundary: ['SCOPE_1', 'SCOPE_2']
    }
  })
  if (error) return <div className="notice"><b>Failed to load.</b> {error}</div>
  if (!dataset || !ready) return <Loading />
  const org = dataset.organization
  const fac = dataset.facilities.find(f => f.id === ids.facility_id) ?? dataset.facilities[0]
  const period = dataset.reporting_periods.find(p => p.id === ids.reporting_period_id) ?? dataset.reporting_periods[0]

  // Seed once from mock (org/facility/period read).
  if (!form.formState.isDirty && form.getValues('industry_sector') === '' && org.name) {
    form.reset({
      industry_sector: org.industry_sector, industry_subtype: org.industry_subtype ?? '',
      country: fac.country, state: fac.state ?? '', city: fac.city ?? '',
      organization_size: org.organization_size, currency_code: org.currency_code,
      annual_production: Number(fac.annual_production ?? 1000), production_unit: fac.production_unit ?? 'tonne',
      working_days_per_year: fac.working_days_per_year ?? 300,
      working_hours_per_day: Number(fac.working_hours_per_day ?? 16),
      period_type: period.period_type, start_date: period.start_date, end_date: period.end_date,
      scope_boundary: ['SCOPE_1', 'SCOPE_2']
    })
  }

  const prod = form.watch('annual_production')
  const errs = form.formState.errors

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Factory profile</h1>
          <p>{org.name} · A1–A9 · source: {sources.dataset === 'live' ? 'live API (/api/context)' : 'demo data (mock fallback)'}</p>
        </div>
        <span className="provenance">RHF + Zod · end_date ≥ start_date · currency ^[A-Z]{'{3}'}$</span>
      </div>
      {period.status !== 'DRAFT' && (
        <div className="notice" style={{ marginBottom: 14 }}>
          <b>Period {period.status}.</b> Activity, scenario, and calculation mutations require an explicit unlock audit event.
        </div>
      )}
      <div className="split">
        <div className="panel panel-pad">
          <h2>Seed values (read)</h2>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table className="data">
              <thead><tr><th>Field</th><th>Mock value</th><th>Rule</th></tr></thead>
              <tbody>
                <tr><td>Annual production</td><td className="mono">{String(fac.annual_production)} {fac.production_unit}</td><td>≥ 0 (=0 blocks intensity)</td></tr>
                <tr><td>Working days / year</td><td className="mono">{String(fac.working_days_per_year)}</td><td>≤ 366</td></tr>
                <tr><td>Working hours / day</td><td className="mono">{String(fac.working_hours_per_day)}</td><td>≤ 24</td></tr>
                <tr><td>Coordinates</td><td className="mono">{String(fac.latitude)}, {String(fac.longitude)}</td><td>lat ±90 · lon ±180</td></tr>
                <tr><td>Period</td><td className="mono">{period.period_type} · {period.start_date} → {period.end_date}</td><td>end ≥ start</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <form
          className="panel panel-pad"
          onSubmit={form.handleSubmit(v => {
            setSavedMsg(`Validated: ${v.industry_sector} · ${v.country} · ${v.annual_production} ${v.production_unit || ''} · scopes ${v.scope_boundary.join(', ')} (demo — live: PATCH A3/A7/A8)`)
          })}
          noValidate
        >
          <h2>Edit profile (A3/A7/A8)</h2>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-sector">Industry sector</label>
              <input id="pf-sector" {...form.register('industry_sector')} maxLength={100} />
              {errs.industry_sector && <span className="field-error">{errs.industry_sector.message}</span>}
            </div>
            <div className="field">
              <label htmlFor="pf-subtype">Industry subtype</label>
              <input id="pf-subtype" {...form.register('industry_subtype')} maxLength={100} placeholder="Dyeing and Finishing" />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-country">Country</label>
              <input id="pf-country" {...form.register('country')} maxLength={100} />
              {errs.country && <span className="field-error">{errs.country.message}</span>}
            </div>
            <div className="field">
              <label htmlFor="pf-state">State</label>
              <input id="pf-state" {...form.register('state')} maxLength={100} />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-city">City</label>
              <input id="pf-city" {...form.register('city')} maxLength={100} />
            </div>
            <div className="field">
              <label htmlFor="pf-size">Factory size</label>
              <select id="pf-size" {...form.register('organization_size')}>
                <option value="SMALL">SMALL</option>
                <option value="MEDIUM">MEDIUM</option>
              </select>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-prod">Production quantity (≥ 0)</label>
              <input id="pf-prod" type="number" min={0} step="any" {...form.register('annual_production', { valueAsNumber: true })} />
              {errs.annual_production && <span className="field-error">{errs.annual_production.message}</span>}
              {prod === 0 && <small>Production = 0 is allowed on the profile but blocks intensity calculations later.</small>}
            </div>
            <div className="field">
              <label htmlFor="pf-unit">Production unit</label>
              <input id="pf-unit" {...form.register('production_unit')} maxLength={30} placeholder="tonne" />
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-days">Working days / year (≤ 366)</label>
              <input id="pf-days" type="number" min={0} max={366} {...form.register('working_days_per_year', { valueAsNumber: true })} />
              {errs.working_days_per_year && <span className="field-error">{errs.working_days_per_year.message}</span>}
            </div>
            <div className="field">
              <label htmlFor="pf-hours">Working hours / day (≤ 24)</label>
              <input id="pf-hours" type="number" min={0} max={24} step="0.5" {...form.register('working_hours_per_day', { valueAsNumber: true })} />
              {errs.working_hours_per_day && <span className="field-error">{errs.working_hours_per_day.message}</span>}
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-ptype">Reporting period type</label>
              <select id="pf-ptype" {...form.register('period_type')}>
                <option value="MONTHLY">MONTHLY</option>
                <option value="QUARTERLY">QUARTERLY</option>
                <option value="ANNUAL">ANNUAL</option>
                <option value="CUSTOM">CUSTOM</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="pf-cur">Currency</label>
              <input id="pf-cur" {...form.register('currency_code')} maxLength={3} placeholder="INR" />
              {errs.currency_code && <span className="field-error">{errs.currency_code.message}</span>}
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="pf-start">Period start</label>
              <input id="pf-start" type="date" {...form.register('start_date')} />
            </div>
            <div className="field">
              <label htmlFor="pf-end">Period end</label>
              <input id="pf-end" type="date" {...form.register('end_date')} />
              {errs.end_date && <span className="field-error">{errs.end_date.message}</span>}
            </div>
          </div>
          <fieldset className="field" style={{ border: '1px solid var(--line)', borderRadius: 8, padding: 10 }}>
            <legend style={{ fontSize: '.8rem', fontWeight: 650, padding: '0 6px' }}>Scope boundary (F1/G1)</legend>
            {(['SCOPE_1', 'SCOPE_2', 'SCOPE_3'] as const).map(s => (
              <label key={s} style={{ display: 'flex', gap: 8, fontSize: '.86rem', fontWeight: 400 }}>
                <input type="checkbox" value={s} {...form.register('scope_boundary')} /> {s.replace('_', ' ')}
              </label>
            ))}
            {errs.scope_boundary && <span className="field-error">{errs.scope_boundary.message}</span>}
          </fieldset>
          {savedMsg && <div className="notice" style={{ marginBottom: 10 }}><b>Saved (demo).</b> {savedMsg}</div>}
          <button className="btn btn-primary" type="submit">Validate &amp; save (demo)</button>
          <p style={{ fontSize: '.78rem', color: 'var(--legend)' }}>Live: PATCH /api/organizations/{'{id}'} (A3) · PATCH /api/facilities/{'{id}'} (A7) · POST reporting-periods (A8)</p>
        </form>
      </div>
    </>
  )
}
