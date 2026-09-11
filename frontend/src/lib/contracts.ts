// TS mirrors of contracts/schemas.py — field names frozen until Phase 2.
// Only rank/process_name/intervention_code/title/explanation/impact are response-only.

export type Scope = 'SCOPE_1' | 'SCOPE_2' | 'SCOPE_3'
export type ActivityCategory =
  | 'ELECTRICITY' | 'FUEL' | 'MATERIAL' | 'WATER' | 'TRANSPORT'
  | 'WASTE' | 'REFRIGERANT' | 'STEAM' | 'OTHER'
export type HotspotSeverity = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type RecommendationStatus =
  | 'SUGGESTED' | 'SHORTLISTED' | 'REJECTED' | 'PLANNED' | 'IMPLEMENTED'

export interface Organization {
  id: string; name: string; industry_sector: string; industry_subtype?: string | null
  country: string; state?: string | null; city?: string | null
  currency_code: string; organization_size: 'SMALL' | 'MEDIUM'
  created_at: string; updated_at: string
}

export interface Facility {
  id: string; organization_id: string; name: string; facility_code?: string | null
  country: string; state?: string | null; city?: string | null
  latitude?: number | null; longitude?: number | null
  annual_production?: number | null; production_unit?: string | null
  working_days_per_year?: number | null; working_hours_per_day?: number | null
  active: boolean; created_at: string; updated_at: string
}

export interface ReportingPeriod {
  id: string; facility_id: string
  period_type: 'MONTHLY' | 'QUARTERLY' | 'ANNUAL' | 'CUSTOM'
  start_date: string; end_date: string
  status: 'DRAFT' | 'LOCKED' | 'CLOSED'; created_at: string
}

export interface Process {
  id: string; facility_id: string; name: string; process_code?: string | null
  sequence_no?: number | null; description?: string | null
  process_category?: string | null; active: boolean; created_at: string
}

export interface ActivityData {
  id: string; facility_id: string; process_id?: string | null
  reporting_period_id: string; activity_category: ActivityCategory
  activity_subcategory: string; source_name?: string | null
  original_value?: number | null; original_unit: string
  normalized_value?: number | null; normalized_unit: string
  data_source_type: 'MANUAL' | 'CSV' | 'EXCEL' | 'API' | 'SENSOR' | 'OCR'
  measured_or_estimated: 'MEASURED' | 'ESTIMATED'
  confidence_score?: number | null; notes?: string | null; created_at: string
}

export interface EmissionHotspot {
  id: string; facility_id: string; reporting_period_id: string
  process_id?: string | null; hotspot_type?: string | null
  emissions_kgco2e: number; contribution_percent?: number | null
  carbon_intensity?: number | null; inefficiency_score?: number | null
  waste_ratio_score?: number | null; improvement_potential_score?: number | null
  hotspot_score?: number | null; severity: HotspotSeverity
  explanation?: string | null; created_at: string
}

export interface HotspotOutputItem extends EmissionHotspot {
  rank: number; process_name?: string | null; activity_category?: ActivityCategory | null
}

export interface HotspotDetectionResult {
  facility_id: string; reporting_period_id: string; generated_at: string
  scope_boundary: Scope[]; total_emissions_kgco2e: number
  data_quality_score?: number | null; hotspots: HotspotOutputItem[]
}

export interface RecommendationAssessment {
  id: string; recommendation_id: string
  estimated_capex?: number | null; estimated_annual_opex_change?: number | null
  estimated_annual_saving?: number | null; estimated_co2_saving_kg?: number | null
  estimated_energy_saving?: number | null; estimated_waste_reduction?: number | null
  payback_years?: number | null; cost_per_tonne_co2_avoided?: number | null
  assumptions?: Record<string, unknown> | null; confidence_score?: number | null
}

export interface RecommendationOutputItem {
  id: string; facility_id: string; reporting_period_id: string
  hotspot_id: string; intervention_id: string
  rank: number
  carbon_saving_score?: number | null; financial_return_score?: number | null
  feasibility_score?: number | null; circularity_score?: number | null
  implementation_speed_score?: number | null; confidence_score?: number | null
  final_score?: number | null; status: RecommendationStatus
  generated_at: string
  intervention_code?: string | null; intervention_title?: string | null
  explanation?: string | null; impact?: RecommendationAssessment | null
}

export interface RecommendationGenerationResult {
  facility_id: string; reporting_period_id: string; generated_at: string
  budget_limit?: number | null; recommendations: RecommendationOutputItem[]
}

export interface MockDataset {
  organization: Organization
  facilities: Facility[]
  reporting_periods: ReportingPeriod[]
  processes: Process[]
  activity_data: ActivityData[]
  emission_factors: Array<Record<string, unknown>>
  circular_interventions: Array<Record<string, unknown>>
}

// Phase 1 swap map — which live endpoint replaces each mock.
export const MOCK_SWAP_MAP = {
  hotspots: 'GET /api/facilities/{facility_id}/reporting-periods/{period_id}/hotspots (G2)',
  recommendations: 'GET /api/facilities/{facility_id}/reporting-periods/{period_id}/recommendations (J2)',
  dashboard: 'GET /api/facilities/{facility_id}/reporting-periods/{period_id}/dashboard (N1)',
  leakMap: 'GET /api/facilities/{facility_id}/reporting-periods/{period_id}/leak-map (N2)'
} as const
