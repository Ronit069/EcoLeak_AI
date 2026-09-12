// EcoLeak AI — wire types mirroring contracts/schemas.py (field names frozen).

export type Scope = 'SCOPE_1' | 'SCOPE_2' | 'SCOPE_3'
export type Severity = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW'
export type ValidationSeverity = 'ERROR' | 'WARNING' | 'INFO' | 'CONFIRMATION_REQUIRED'
export type ActivityCategory =
  | 'ELECTRICITY' | 'FUEL' | 'MATERIAL' | 'WATER' | 'TRANSPORT'
  | 'WASTE' | 'REFRIGERANT' | 'STEAM' | 'OTHER'
export type DataSourceType = 'MANUAL' | 'CSV' | 'EXCEL' | 'API' | 'SENSOR' | 'OCR'
export type MeasuredOrEstimated = 'MEASURED' | 'ESTIMATED'
export type RecommendationStatus = 'SUGGESTED' | 'SHORTLISTED' | 'REJECTED' | 'PLANNED' | 'IMPLEMENTED'
export type FeedbackType = 'USEFUL' | 'NOT_APPLICABLE' | 'CONSIDER_LATER' | 'IMPLEMENTED' | 'REJECTED'
export type PeriodStatus = 'DRAFT' | 'LOCKED' | 'CLOSED'

export interface Organization {
  id: string
  name: string
  industry_sector: string
  industry_subtype: string | null
  country: string
  state: string | null
  city: string | null
  currency_code: string
  organization_size: 'SMALL' | 'MEDIUM'
  created_at: string
  updated_at: string
}

export interface Facility {
  id: string
  organization_id: string
  name: string
  facility_code: string | null
  country: string
  state: string | null
  city: string | null
  latitude: number | null
  longitude: number | null
  annual_production: number | string | null
  production_unit: string | null
  working_days_per_year: number | null
  working_hours_per_day: number | string | null
  active: boolean
  created_at: string
  updated_at: string
}

export interface ReportingPeriod {
  id: string
  facility_id: string
  period_type: string
  start_date: string
  end_date: string
  status: PeriodStatus
  created_at: string
}

export interface Process {
  id: string
  facility_id: string
  name: string
  process_code: string | null
  sequence_no: number | null
  description: string | null
  process_category: string | null
  active: boolean
  created_at: string
}

export interface ActivityData {
  id: string
  facility_id: string
  process_id: string | null
  asset_id: string | null
  reporting_period_id: string
  activity_category: ActivityCategory
  activity_subcategory: string
  source_name: string | null
  original_value: number | string | null
  original_unit: string
  normalized_value: number | string | null
  normalized_unit: string
  data_source_type: DataSourceType
  measured_or_estimated: MeasuredOrEstimated
  confidence_score: number | string | null
  notes: string | null
  created_at: string
}

export interface EmissionFactor {
  id: string
  factor_code: string
  category: string
  subcategory: string
  item_name: string
  region_country: string | null
  region_state: string | null
  scope: Scope
  input_unit: string
  output_unit: string
  co2_factor: number | string | null
  ch4_factor: number | string | null
  n2o_factor: number | string | null
  total_co2e_factor: number | string
  source_name: string
  source_url: string | null
  source_year: number
  valid_from: string | null
  valid_to: string | null
  methodology: string | null
  confidence_level: ConfidenceLevel | null
  version: string
  active: boolean
  created_at: string
}

export interface HotspotItem {
  id: string
  facility_id: string
  reporting_period_id: string
  process_id: string | null
  asset_id: string | null
  hotspot_type: string | null
  emissions_kgco2e: number | string
  contribution_percent: number | string | null
  carbon_intensity: number | string | null
  inefficiency_score: number | string | null
  waste_ratio_score: number | string | null
  improvement_potential_score: number | string | null
  hotspot_score: number | string | null
  severity: Severity
  explanation: string | null
  created_at: string
  rank: number
  process_name: string | null
  activity_category: ActivityCategory | null
}

export interface HotspotResult {
  facility_id: string
  reporting_period_id: string
  generated_at: string
  scope_boundary: Scope[]
  total_emissions_kgco2e: number | string
  data_quality_score: number | string | null
  hotspots: HotspotItem[]
}

export interface RecommendationAssessment {
  id: string
  recommendation_id: string
  estimated_capex: number | string | null
  estimated_annual_opex_change: number | string | null
  estimated_annual_saving: number | string | null
  estimated_co2_saving_kg: number | string | null
  estimated_energy_saving: number | string | null
  estimated_waste_reduction: number | string | null
  payback_years: number | string | null
  cost_per_tonne_co2_avoided: number | string | null
  assumptions: Record<string, unknown> | null
  confidence_score: number | string | null
}

export interface RecommendationItem {
  id: string
  facility_id: string
  reporting_period_id: string
  hotspot_id: string
  intervention_id: string
  rank: number
  carbon_saving_score: number | string | null
  financial_return_score: number | string | null
  feasibility_score: number | string | null
  circularity_score: number | string | null
  implementation_speed_score: number | string | null
  confidence_score: number | string | null
  final_score: number | string | null
  status: RecommendationStatus
  generated_at: string
  intervention_code: string | null
  intervention_title: string | null
  explanation: string | null
  impact: RecommendationAssessment | null
}

export interface RecommendationResult {
  facility_id: string
  reporting_period_id: string
  generated_at: string
  budget_limit: number | string | null
  recommendations: RecommendationItem[]
}

export interface DashboardScopeBreakdown { SCOPE_1: number | string; SCOPE_2: number | string; SCOPE_3: number | string }

export interface DashboardPayload {
  total_kgco2e: number | string
  scope_breakdown: DashboardScopeBreakdown
  carbon_intensity: number | string | null
  production_unit?: string | null
  largest_hotspot: HotspotItem | null
  circularity_score: number | string | null
  potential_reduction_kgco2e: number | string
  potential_annual_saving: number | string | null
  last_calculated_at: string | null
  empty_state: boolean
}

export interface LeakMapNode {
  process_id: string | null
  process_name: string | null
  emissions_kgco2e: number | string
  contribution_percent: number | string | null
  severity: Severity
}
export interface LeakMapPayload { nodes: LeakMapNode[]; links: unknown[] }

export interface CircularityScore {
  recycled_input_score: number | string | null
  waste_recovery_score: number | string | null
  energy_recovery_score: number | string | null
  water_reuse_score: number | string | null
  reuse_score: number | string | null
  total_score: number | string | null
  methodology_version: string
  calculated_at: string
  is_internal_metric: boolean
  not_a_certified_standard: boolean
  disclaimer: string
  score_complete: boolean
  component_sources: Record<string, string | null>
  issues: unknown[]
}

export interface InventorySummary {
  scope1_kgco2e: number | string
  scope2_kgco2e: number | string
  scope3_kgco2e: number | string
  total_kgco2e: number | string
  carbon_intensity: number | string | null
  production_unit: string | null
  generated_at: string
}

export interface ValidationIssue {
  severity: ValidationSeverity
  code: string
  message: string
  field?: string | null
  details?: Record<string, unknown> | null
}

export interface ImportJob {
  import_id: string
  status: 'RECEIVED' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'DRY_RUN'
  row_issues: ValidationIssue[]
}

export interface DataQuality {
  completeness_score: number | string | null
  source_quality_score: number | string | null
  factor_quality_score: number | string | null
  temporal_quality_score: number | string | null
  unit_quality_score: number | string | null
  total_score: number | string | null
  issues: ValidationIssue[]
}

export interface NormalizeResult {
  original_value: number | string
  original_unit: string
  normalized_value: number | string
  normalized_unit: string
  conversion_factor: number | string | null
  conversion_source: string
}

export interface ImpactAssessment {
  id: string
  scenario_id: string
  baseline_emissions_kg: number | string
  projected_emissions_kg: number | string
  total_co2_saving_kg: number | string | null
  reduction_percent: number | string | null
  total_capex: number | string | null
  annual_saving: number | string | null
  payback_years: number | string | null
  generated_at: string
}

export interface ScenarioEnvelope {
  scenario_id: string
  assessment: ImpactAssessment
  interventions: Array<Record<string, unknown>>
  payback_status?: string | null
  payback_reason?: string | null
  over_budget: boolean
  issues: Array<Record<string, unknown>>
}

export interface ReportReceipt {
  report_id: string
  status: string
  version: number
  generated_at: string
  report_hash: string
}

export interface ExplanationPayload {
  recommendation_id: string
  summary: string
  evidence: Record<string, unknown>
  assumptions: Record<string, unknown>
  confidence_score: number | string | null
  generated_by: string
}

export interface ContextPayload {
  organization: Organization | null
  facilities: Facility[]
  reporting_periods: ReportingPeriod[]
}

export interface BootstrapIds {
  organization_id: string
  facility_id: string
  reporting_period_id: string
}
