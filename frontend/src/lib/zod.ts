import { z } from 'zod'

// Mirrors contracts/schemas.py ranges/enums. Strict: reject unknown keys.
export const activityCategory = z.enum([
  'ELECTRICITY','FUEL','MATERIAL','WATER','TRANSPORT','WASTE','REFRIGERANT','STEAM','OTHER'
])
export const hotspotSeverity = z.enum(['LOW','MODERATE','HIGH','CRITICAL'])
export const recommendationStatus = z.enum([
  'SUGGESTED','SHORTLISTED','REJECTED','PLANNED','IMPLEMENTED'
])
export const scope = z.enum(['SCOPE_1','SCOPE_2','SCOPE_3'])
const confidence = z.number().min(0).max(100)
const pct = z.number().min(0).max(100)

export const reportingPeriodSchema = z.object({
  id: z.string().uuid(),
  facility_id: z.string().uuid(),
  period_type: z.enum(['MONTHLY','QUARTERLY','ANNUAL','CUSTOM']),
  start_date: z.string(),
  end_date: z.string(),
  status: z.enum(['DRAFT','LOCKED','CLOSED']),
  created_at: z.string()
}).strict()
.refine(v => v.end_date >= v.start_date, { message: 'end_date cannot be before start_date', path: ['end_date'] })

export const facilitySchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  name: z.string().min(1).max(200),
  facility_code: z.string().max(50).nullable().optional(),
  country: z.string().min(1).max(100),
  state: z.string().max(100).nullable().optional(),
  city: z.string().max(100).nullable().optional(),
  annual_production: z.number().min(0).nullable().optional(),
  production_unit: z.string().max(30).nullable().optional(),
  working_days_per_year: z.number().int().min(0).max(366).nullable().optional(),
  working_hours_per_day: z.number().min(0).max(24).nullable().optional(),
  active: z.boolean(),
  created_at: z.string(),
  updated_at: z.string()
}).strict()

const hotspotItem = z.object({
  id: z.string().uuid(),
  rank: z.number().int().min(1),
  facility_id: z.string().uuid(),
  reporting_period_id: z.string().uuid(),
  process_id: z.string().uuid().nullable().optional(),
  asset_id: z.string().uuid().nullable().optional(),
  process_name: z.string().max(150).nullable().optional(),
  activity_category: activityCategory.nullable().optional(),
  hotspot_type: z.string().max(30).nullable().optional(),
  emissions_kgco2e: z.number().min(0),
  contribution_percent: z.number().min(0).max(100).nullable().optional(),
  carbon_intensity: z.number().min(0).nullable().optional(),
  inefficiency_score: z.number().min(0).max(100).nullable().optional(),
  waste_ratio_score: z.number().min(0).max(100).nullable().optional(),
  improvement_potential_score: z.number().min(0).max(100).nullable().optional(),
  hotspot_score: z.number().min(0).max(100).nullable().optional(),
  severity: hotspotSeverity,
  explanation: z.string().nullable().optional(),
  created_at: z.string()
}).strict()

export const hotspotResultSchema = z.object({
  facility_id: z.string().uuid(),
  reporting_period_id: z.string().uuid(),
  generated_at: z.string(),
  scope_boundary: z.array(scope),
  total_emissions_kgco2e: z.number().min(0),
  data_quality_score: z.number().min(0).max(100).nullable().optional(),
  hotspots: z.array(hotspotItem)
}).strict()

const impactSchema = z.object({
  id: z.string().uuid(),
  recommendation_id: z.string().uuid(),
  estimated_capex: z.number().min(0).nullable().optional(),
  estimated_annual_opex_change: z.number().nullable().optional(),
  estimated_annual_saving: z.number().nullable().optional(),
  estimated_co2_saving_kg: z.number().min(0).nullable().optional(),
  estimated_energy_saving: z.number().min(0).nullable().optional(),
  estimated_waste_reduction: z.number().min(0).nullable().optional(),
  payback_years: z.number().min(0).nullable().optional(),
  cost_per_tonne_co2_avoided: z.number().nullable().optional(),
  assumptions: z.record(z.unknown()).nullable().optional(),
  confidence_score: confidence.nullable().optional()
}).strict()

const recommendationItem = z.object({
  id: z.string().uuid(),
  rank: z.number().int().min(1),
  facility_id: z.string().uuid(),
  reporting_period_id: z.string().uuid(),
  hotspot_id: z.string().uuid(),
  intervention_id: z.string().uuid(),
  intervention_code: z.string().max(80).nullable().optional(),
  intervention_title: z.string().max(200).nullable().optional(),
  carbon_saving_score: z.number().min(0).max(100).nullable().optional(),
  financial_return_score: z.number().min(0).max(100).nullable().optional(),
  feasibility_score: z.number().min(0).max(100).nullable().optional(),
  circularity_score: z.number().min(0).max(100).nullable().optional(),
  implementation_speed_score: z.number().min(0).max(100).nullable().optional(),
  confidence_score: confidence.nullable().optional(),
  final_score: z.number().min(0).max(100).nullable().optional(),
  status: recommendationStatus,
  explanation: z.string().nullable().optional(),
  impact: impactSchema.nullable().optional(),
  generated_at: z.string()
}).strict()

export const recommendationResultSchema = z.object({
  facility_id: z.string().uuid(),
  reporting_period_id: z.string().uuid(),
  generated_at: z.string(),
  budget_limit: z.number().min(0).nullable().optional(),
  recommendations: z.array(recommendationItem)
}).strict()

export const activityInputSchema = z.object({
  process_id: z.string().uuid({ message: 'Select a process' }),
  activity_category: activityCategory,
  activity_subcategory: z.string().min(1, 'Subcategory is required').max(100),
  original_value: z.number({ invalid_type_error: 'Value must be a number' }).min(0, 'Value cannot be negative'),
  original_unit: z.string().min(1, 'Unit is required').max(30),
  data_source_type: z.enum(['MANUAL','CSV','EXCEL','API','SENSOR','OCR']),
  measured_or_estimated: z.enum(['MEASURED','ESTIMATED']),
  confidence_score: confidence.nullable().optional()
})

export const scenarioInputSchema = z.object({
  name: z.string().min(1, 'Scenario name is required').max(150),
  budget_limit: z.number().min(0, 'Budget cannot be negative').nullable().optional(),
  target_reduction_pct: pct.nullable().optional()
})

export const profileFormSchema = z.object({
  industry_sector: z.string().min(1, 'Sector is required').max(100),
  industry_subtype: z.string().max(100).optional().or(z.literal('')),
  country: z.string().min(1, 'Country is required').max(100),
  state: z.string().max(100).optional().or(z.literal('')),
  city: z.string().max(100).optional().or(z.literal('')),
  organization_size: z.enum(['SMALL', 'MEDIUM']),
  currency_code: z.string().regex(/^[A-Z]{3}$/, 'Currency must be 3 uppercase letters'),
  annual_production: z.number({ invalid_type_error: 'Production must be a number' }).min(0, 'Production cannot be negative'),
  production_unit: z.string().max(30).optional().or(z.literal('')),
  working_days_per_year: z.number({ invalid_type_error: 'Days must be a number' }).int().min(0).max(366, 'Must be ≤ 366'),
  working_hours_per_day: z.number({ invalid_type_error: 'Hours must be a number' }).min(0).max(24, 'Must be ≤ 24'),
  period_type: z.enum(['MONTHLY', 'QUARTERLY', 'ANNUAL', 'CUSTOM']),
  start_date: z.string().min(1, 'Start date is required'),
  end_date: z.string().min(1, 'End date is required'),
  scope_boundary: z.array(z.enum(['SCOPE_1', 'SCOPE_2', 'SCOPE_3'])).min(1, 'Select at least one scope')
}).refine(v => v.end_date >= v.start_date, { message: 'end_date cannot be before start_date', path: ['end_date'] })

export type ProfileForm = z.infer<typeof profileFormSchema>

export const adoptionSchema = z.number().min(0).max(100)

export type ActivityInput = z.infer<typeof activityInputSchema>
