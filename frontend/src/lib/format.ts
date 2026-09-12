const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0
})
const num = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const num1 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })
const num2 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

export const fmtINR = (v: number | null | undefined) =>
  v == null ? '—' : inr.format(v)
export const fmtKg = (v: number | null | undefined) =>
  v == null ? '—' : `${num.format(v)} kgCO₂e`
export const fmtTonnes = (v: number | null | undefined) =>
  v == null ? '—' : `${num1.format(v / 1000)} tCO₂e`
export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${digits === 2 ? num2.format(v) : num1.format(v)}%`
export const fmtYears = (v: number | null | undefined) =>
  v == null ? 'No payback' : `${num1.format(v)} yr`
export const fmtScore = (v: number | null | undefined) =>
  v == null ? '—' : num1.format(v)
export const fmtCostPerTonne = (v: number | null | undefined) =>
  v == null ? '—' : `${inr.format(v)} / tCO₂e avoided`
