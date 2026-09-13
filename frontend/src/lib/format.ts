// EcoLeak AI — instrument readout formatters.
// Full precision in state; round only at render. null -> "—" (never 0).

export const DASH = '—'

export function isNil(v: unknown): v is null | undefined {
  return v === null || v === undefined || (typeof v === 'string' && v.trim() === '')
}

/** Coerce a value that may arrive as a number OR a string (report payload). */
export function num(v: unknown): number | null {
  if (isNil(v)) return null
  const n = typeof v === 'number' ? v : Number(String(v).replace(/[,\s]/g, ''))
  return Number.isFinite(n) ? n : null
}

export function fmtNumber(v: unknown, digits = 0): string {
  const n = num(v)
  if (n === null) return DASH
  return n.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtInt(v: unknown): string {
  return fmtNumber(v, 0)
}

/** kgCO2e with automatic tCO2e scaling, always unit-labelled. */
export function fmtCo2e(kg: unknown): string {
  const n = num(kg)
  if (n === null) return DASH
  if (Math.abs(n) >= 1000) return `${fmtNumber(n / 1000, 1)} tCO₂e`
  return `${fmtNumber(n, 0)} kgCO₂e`
}

export function fmtPct(v: unknown, digits = 1): string {
  const n = num(v)
  if (n === null) return DASH
  return `${fmtNumber(n, digits)}%`
}

export function fmtScore(v: unknown): string {
  const n = num(v)
  if (n === null) return DASH
  return fmtNumber(n, 1)
}

export function fmtInr(v: unknown): string {
  const n = num(v)
  if (n === null) return DASH
  if (Math.abs(n) >= 10000000) return `₹${fmtNumber(n / 10000000, 2)} Cr`
  if (Math.abs(n) >= 100000) return `₹${fmtNumber(n / 100000, 2)} lakh`
  return `₹${fmtNumber(n, 0)}`
}

export function fmtPayback(years: unknown, annualSaving: unknown): string {
  const y = num(years)
  const s = num(annualSaving)
  if (s !== null && s <= 0) return 'NO FINANCIAL PAYBACK ESTIMATED'
  if (y === null) return DASH
  if (y === 0) return 'IMMEDIATE'
  return `${fmtNumber(y, 1)} yr`
}

export function paybackKind(years: unknown, annualSaving: unknown): 'null' | 'immediate' | 'cost' | 'normal' {
  const y = num(years)
  const s = num(annualSaving)
  if (s !== null && s <= 0) return 'cost'
  if (y === null) return 'null'
  if (y === 0) return 'immediate'
  return 'normal'
}

export function fmtTimestamp(iso: unknown): string {
  if (isNil(iso)) return DASH
  try {
    const d = new Date(String(iso))
    if (Number.isNaN(d.getTime())) return String(iso)
    return d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
  } catch {
    return String(iso)
  }
}

export function withUnit(value: unknown, unit: string | null | undefined, digits = 0): string {
  const s = fmtNumber(value, digits)
  if (s === DASH) return DASH
  return unit ? `${s} ${unit}` : s
}

export function shortId(id: unknown): string {
  const s = isNil(id) ? '' : String(id)
  return s.length > 12 ? s.slice(0, 8) : s
}
