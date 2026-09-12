// EcoLeak AI — Zod validation at the wire boundary.
// Lenient on unknown additive keys (contract allows additive), strict on the
// fields the UI actually depends on.
import { z } from 'zod'

const numOrStr = z.union([z.number(), z.string()])
const severity = z.enum(['LOW', 'MODERATE', 'HIGH', 'CRITICAL'])

export const hotspotItemSchema = z
  .object({
    id: z.string(),
    severity,
    emissions_kgco2e: numOrStr,
    rank: z.number(),
    process_name: z.string().nullable().optional(),
    contribution_percent: numOrStr.nullable().optional(),
  })
  .passthrough()

export const hotspotResultSchema = z
  .object({
    facility_id: z.string(),
    reporting_period_id: z.string(),
    total_emissions_kgco2e: numOrStr,
    hotspots: z.array(hotspotItemSchema),
  })
  .passthrough()

export const recommendationItemSchema = z
  .object({
    id: z.string(),
    rank: z.number(),
    status: z.enum(['SUGGESTED', 'SHORTLISTED', 'REJECTED', 'PLANNED', 'IMPLEMENTED']),
    final_score: numOrStr.nullable().optional(),
    impact: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .passthrough()

export const recommendationResultSchema = z
  .object({
    facility_id: z.string(),
    reporting_period_id: z.string(),
    recommendations: z.array(recommendationItemSchema),
  })
  .passthrough()

export const dashboardSchema = z
  .object({
    total_kgco2e: numOrStr,
    scope_breakdown: z.record(z.string(), numOrStr),
    empty_state: z.boolean(),
  })
  .passthrough()

export const normalizeResultSchema = z
  .object({
    original_value: numOrStr,
    original_unit: z.string(),
    normalized_value: numOrStr,
    normalized_unit: z.string(),
    conversion_factor: numOrStr.nullable(),
    conversion_source: z.string(),
  })
  .passthrough()
