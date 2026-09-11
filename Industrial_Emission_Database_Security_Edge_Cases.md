# Industrial Emission Leak-Point Detector & Circular Alternative Recommender
## Database Design, Security Checklist, and Module-wise Edge Cases

**Purpose:** Implementation reference for students building the hackathon solution.  
**Recommended stack:** React + FastAPI + PostgreSQL + Python ML services + REST APIs.

---

# 1. Database Design

## 1.1 Design Principles

The database should support:

- Multiple organizations and facilities.
- Process-level carbon accounting.
- Versioned emission factors.
- Scope 1, Scope 2, and selected Scope 3 calculations.
- Materials, energy, transportation, water, and waste activity data.
- Carbon hotspot detection.
- Circular intervention recommendations.
- Cost and CO₂ impact simulation.
- Scenario comparison.
- Auditability and reproducibility.
- Data-quality/confidence scoring.
- Future integration with external APIs, sensors, OCR, and regulatory reporting.

Use PostgreSQL with UUID primary keys where possible.

---

## 1.2 High-Level Entity Relationship

```text
Organization
   |
   +---- Facility
            |
            +---- Process
            |       |
            |       +---- ProcessAsset / Machine
            |       |
            |       +---- ActivityData
            |              |
            |              +---- EmissionCalculation
            |
            +---- ReportingPeriod
            |
            +---- EmissionHotspot
            |
            +---- Recommendation
            |       |
            |       +---- RecommendationAssessment
            |
            +---- Scenario
                    |
                    +---- ScenarioIntervention
                    |
                    +---- ScenarioResult

EmissionFactor
MaterialMaster
EnergySourceMaster
WasteTypeMaster
CircularInterventionMaster
IndustryBenchmark
RecommendationRule
DataQualityAssessment
AuditLog
```

---

# 2. Core Master Tables

## 2.1 `organizations`

Stores SME/company-level information.

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Organization ID |
| name | VARCHAR(200) | NOT NULL | Company name |
| industry_sector | VARCHAR(100) | NOT NULL | Textile, foundry, food, etc. |
| industry_subtype | VARCHAR(100) | NULL | Dyeing, machining, casting, etc. |
| country | VARCHAR(100) | NOT NULL | Country |
| state | VARCHAR(100) | NULL | State/region |
| city | VARCHAR(100) | NULL | City |
| currency_code | CHAR(3) | NOT NULL DEFAULT 'INR' | Currency |
| organization_size | VARCHAR(30) | CHECK | SMALL/MEDIUM |
| created_at | TIMESTAMPTZ | NOT NULL | Created timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Updated timestamp |

### Recommended Constraints
```sql
CHECK (organization_size IN ('SMALL', 'MEDIUM'))
```

---

## 2.2 `facilities`

One organization may have multiple manufacturing facilities.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| organization_id | UUID | FK organizations.id, NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| facility_code | VARCHAR(50) | UNIQUE within organization |
| country | VARCHAR(100) | NOT NULL |
| state | VARCHAR(100) | NULL |
| city | VARCHAR(100) | NULL |
| latitude | NUMERIC(9,6) | NULL |
| longitude | NUMERIC(9,6) | NULL |
| annual_production | NUMERIC(18,4) | CHECK >= 0 |
| production_unit | VARCHAR(30) | NULL |
| working_days_per_year | INT | CHECK 0..366 |
| working_hours_per_day | NUMERIC(5,2) | CHECK 0..24 |
| active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

### Unique Index
```sql
UNIQUE (organization_id, facility_code)
```

---

## 2.3 `reporting_periods`

Ensures all activity data has an explicit reporting time window.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| facility_id | UUID | FK |
| period_type | VARCHAR(20) | MONTHLY/QUARTERLY/ANNUAL/CUSTOM |
| start_date | DATE | NOT NULL |
| end_date | DATE | NOT NULL |
| status | VARCHAR(20) | DRAFT/LOCKED/CLOSED |
| created_at | TIMESTAMPTZ | NOT NULL |

### Constraint
```sql
CHECK (end_date >= start_date)
```

---

# 3. Process Mapping Tables

## 3.1 `processes`

Represents manufacturing stages.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| facility_id | UUID | FK |
| name | VARCHAR(150) | NOT NULL |
| process_code | VARCHAR(50) | NULL |
| sequence_no | INT | CHECK > 0 |
| description | TEXT | NULL |
| process_category | VARCHAR(100) | NULL |
| active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

### Example
```text
Raw Material Preparation
Dyeing
Drying
Boiler
Finishing
Packaging
```

---

## 3.2 `process_links`

Supports process flow / Sankey / carbon graph.

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| source_process_id | UUID FK processes.id |
| target_process_id | UUID FK processes.id |
| flow_type | VARCHAR(50) |
| quantity | NUMERIC(18,4) |
| unit | VARCHAR(30) |
| description | TEXT |

### Important Rule
Prevent self-loops unless explicitly permitted.

```sql
CHECK (source_process_id <> target_process_id)
```

---

## 3.3 `process_assets`

Machines/equipment associated with processes.

| Column | Type |
|---|---|
| id | UUID PK |
| process_id | UUID FK |
| asset_name | VARCHAR(150) |
| asset_type | VARCHAR(100) |
| manufacturer | VARCHAR(100) |
| rated_capacity | NUMERIC(18,4) |
| capacity_unit | VARCHAR(30) |
| operating_hours | NUMERIC(18,2) |
| installation_year | INT |
| active | BOOLEAN |

---

# 4. Activity Data Tables

## 4.1 `activity_data`

Generic activity-data table.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| facility_id | UUID | FK |
| process_id | UUID | FK nullable |
| asset_id | UUID | FK nullable |
| reporting_period_id | UUID | FK |
| activity_category | VARCHAR(40) | NOT NULL |
| activity_subcategory | VARCHAR(100) | NOT NULL |
| source_name | VARCHAR(150) | NULL |
| original_value | NUMERIC(20,6) | CHECK >= 0 |
| original_unit | VARCHAR(30) | NOT NULL |
| normalized_value | NUMERIC(20,6) | CHECK >= 0 |
| normalized_unit | VARCHAR(30) | NOT NULL |
| data_source_type | VARCHAR(30) | MANUAL/CSV/EXCEL/API/SENSOR/OCR |
| measured_or_estimated | VARCHAR(20) | MEASURED/ESTIMATED |
| confidence_score | NUMERIC(5,2) | CHECK 0..100 |
| notes | TEXT | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

### Allowed Activity Categories
```text
ELECTRICITY
FUEL
MATERIAL
WATER
TRANSPORT
WASTE
REFRIGERANT
STEAM
OTHER
```

---

## 4.2 Optional Specialized Tables

For a hackathon, `activity_data` may be enough. For a production system, specialized tables improve validation.

### `energy_activity`
- electricity_kwh
- renewable_fraction
- grid_region
- provider

### `fuel_activity`
- fuel_type
- volume_or_mass
- calorific_basis

### `material_activity`
- material_id
- virgin_fraction
- recycled_fraction
- supplier_factor_available

### `waste_activity`
- waste_type_id
- treatment_method
- quantity
- recycled_quantity
- landfill_quantity
- incinerated_quantity

### `transport_activity`
- mode
- distance_km
- load_tonnes
- tonne_km
- fuel_type

---

# 5. Master Reference Tables

## 5.1 `energy_sources`

| Column | Type |
|---|---|
| id | UUID PK |
| name | VARCHAR(100) |
| category | VARCHAR(50) |
| renewable | BOOLEAN |
| standard_unit | VARCHAR(30) |

Examples:
- Grid Electricity
- Solar
- Diesel
- Natural Gas
- LPG
- Coal
- Furnace Oil

---

## 5.2 `materials`

| Column | Type |
|---|---|
| id | UUID PK |
| name | VARCHAR(150) |
| category | VARCHAR(100) |
| standard_unit | VARCHAR(30) |
| recyclable | BOOLEAN |
| renewable_material | BOOLEAN |

---

## 5.3 `waste_types`

| Column | Type |
|---|---|
| id | UUID PK |
| name | VARCHAR(150) |
| category | VARCHAR(100) |
| hazardous | BOOLEAN |
| recyclable | BOOLEAN |
| standard_unit | VARCHAR(30) |

---

# 6. Emission Factor Database

## 6.1 `emission_factors`

This is a critical table. Never hard-code factors in application code.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| factor_code | VARCHAR(80) | UNIQUE |
| category | VARCHAR(50) | NOT NULL |
| subcategory | VARCHAR(100) | NOT NULL |
| item_name | VARCHAR(150) | NOT NULL |
| region_country | VARCHAR(100) | NULL |
| region_state | VARCHAR(100) | NULL |
| scope | VARCHAR(20) | SCOPE_1/SCOPE_2/SCOPE_3 |
| input_unit | VARCHAR(30) | NOT NULL |
| output_unit | VARCHAR(30) | DEFAULT kgCO2e |
| co2_factor | NUMERIC(20,8) | NULL |
| ch4_factor | NUMERIC(20,8) | NULL |
| n2o_factor | NUMERIC(20,8) | NULL |
| total_co2e_factor | NUMERIC(20,8) | NOT NULL |
| source_name | VARCHAR(255) | NOT NULL |
| source_url | TEXT | NULL |
| source_year | INT | NOT NULL |
| valid_from | DATE | NULL |
| valid_to | DATE | NULL |
| methodology | TEXT | NULL |
| confidence_level | VARCHAR(20) | HIGH/MEDIUM/LOW |
| version | VARCHAR(30) | NOT NULL |
| active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

### Important Requirements

- Factors must be versioned.
- Historical calculations must continue pointing to the original factor used.
- Never overwrite old factor values.
- Set old factors `active = false` when superseded.

---

# 7. Carbon Calculation Tables

## 7.1 `emission_calculations`

| Column | Type |
|---|---|
| id | UUID PK |
| activity_data_id | UUID FK |
| emission_factor_id | UUID FK |
| calculation_version | VARCHAR(30) |
| scope | VARCHAR(20) |
| co2e_kg | NUMERIC(20,6) |
| calculation_formula | TEXT |
| assumptions | JSONB |
| confidence_score | NUMERIC(5,2) |
| calculated_at | TIMESTAMPTZ |

### Calculation

```text
CO2e = normalized_activity_value × emission_factor
```

### Requirement

The system must preserve:
- activity value
- factor ID
- factor version
- formula
- assumptions
- timestamp

This allows full reproducibility.

---

## 7.2 `carbon_inventory_summary`

Optional materialized summary table for dashboards.

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| scope1_kgco2e | NUMERIC |
| scope2_kgco2e | NUMERIC |
| scope3_kgco2e | NUMERIC |
| total_kgco2e | NUMERIC |
| carbon_intensity | NUMERIC |
| production_unit | VARCHAR |
| generated_at | TIMESTAMPTZ |

---

# 8. Data Quality Tables

## 8.1 `data_quality_assessments`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| completeness_score | NUMERIC(5,2) |
| source_quality_score | NUMERIC(5,2) |
| factor_quality_score | NUMERIC(5,2) |
| temporal_quality_score | NUMERIC(5,2) |
| unit_quality_score | NUMERIC(5,2) |
| total_score | NUMERIC(5,2) |
| issues | JSONB |
| generated_at | TIMESTAMPTZ |

---

# 9. Hotspot Detection Tables

## 9.1 `emission_hotspots`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| process_id | UUID FK nullable |
| asset_id | UUID FK nullable |
| hotspot_type | VARCHAR(30) |
| emissions_kgco2e | NUMERIC |
| contribution_percent | NUMERIC(8,4) |
| carbon_intensity | NUMERIC |
| inefficiency_score | NUMERIC |
| waste_ratio_score | NUMERIC |
| improvement_potential_score | NUMERIC |
| hotspot_score | NUMERIC |
| severity | VARCHAR(20) |
| explanation | TEXT |
| created_at | TIMESTAMPTZ |

### Severity
```text
LOW
MODERATE
HIGH
CRITICAL
```

---

# 10. Anomaly / Inefficiency Tables

## 10.1 `anomaly_results`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| process_id | UUID FK |
| activity_data_id | UUID FK nullable |
| model_name | VARCHAR(100) |
| model_version | VARCHAR(50) |
| anomaly_score | NUMERIC |
| threshold | NUMERIC |
| is_anomaly | BOOLEAN |
| explanation | TEXT |
| confidence_score | NUMERIC(5,2) |
| detected_at | TIMESTAMPTZ |

---

# 11. Circular Intervention Knowledge Base

## 11.1 `circular_interventions`

| Column | Type |
|---|---|
| id | UUID PK |
| intervention_code | VARCHAR(80) UNIQUE |
| title | VARCHAR(200) |
| industry_sector | VARCHAR(100) |
| process_category | VARCHAR(100) |
| current_practice | TEXT |
| alternative_practice | TEXT |
| description | TEXT |
| min_capex | NUMERIC |
| max_capex | NUMERIC |
| currency | CHAR(3) |
| expected_co2_reduction_min_pct | NUMERIC |
| expected_co2_reduction_max_pct | NUMERIC |
| energy_reduction_min_pct | NUMERIC |
| energy_reduction_max_pct | NUMERIC |
| waste_reduction_min_pct | NUMERIC |
| waste_reduction_max_pct | NUMERIC |
| implementation_months_min | INT |
| implementation_months_max | INT |
| complexity | VARCHAR(20) |
| risk_level | VARCHAR(20) |
| evidence_source | TEXT |
| active | BOOLEAN |

---

## 11.2 `intervention_applicability`

Maps interventions to materials, energy sources, processes, and waste types.

| Column | Type |
|---|---|
| id | UUID PK |
| intervention_id | UUID FK |
| applicability_type | VARCHAR(30) |
| reference_id | UUID |
| condition_json | JSONB |

---

# 12. Recommendation Tables

## 12.1 `recommendations`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| hotspot_id | UUID FK |
| intervention_id | UUID FK |
| rank | INT |
| carbon_saving_score | NUMERIC |
| financial_return_score | NUMERIC |
| feasibility_score | NUMERIC |
| circularity_score | NUMERIC |
| implementation_speed_score | NUMERIC |
| confidence_score | NUMERIC |
| final_score | NUMERIC |
| status | VARCHAR(30) |
| generated_at | TIMESTAMPTZ |

### Recommendation Status
```text
SUGGESTED
SHORTLISTED
REJECTED
PLANNED
IMPLEMENTED
```

---

## 12.2 `recommendation_assessments`

Stores calculated impact.

| Column | Type |
|---|---|
| id | UUID PK |
| recommendation_id | UUID FK |
| estimated_capex | NUMERIC |
| estimated_annual_opex_change | NUMERIC |
| estimated_annual_saving | NUMERIC |
| estimated_co2_saving_kg | NUMERIC |
| estimated_energy_saving | NUMERIC |
| estimated_waste_reduction | NUMERIC |
| payback_years | NUMERIC |
| cost_per_tonne_co2_avoided | NUMERIC |
| assumptions | JSONB |
| confidence_score | NUMERIC |

---

# 13. Scenario Simulation Tables

## 13.1 `scenarios`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| name | VARCHAR(150) |
| scenario_type | VARCHAR(30) |
| budget_limit | NUMERIC |
| target_reduction_pct | NUMERIC |
| created_at | TIMESTAMPTZ |

---

## 13.2 `scenario_interventions`

| Column | Type |
|---|---|
| id | UUID PK |
| scenario_id | UUID FK |
| recommendation_id | UUID FK |
| adoption_percentage | NUMERIC CHECK 0..100 |
| selected | BOOLEAN |

---

## 13.3 `scenario_results`

| Column | Type |
|---|---|
| id | UUID PK |
| scenario_id | UUID FK |
| baseline_emissions_kg | NUMERIC |
| projected_emissions_kg | NUMERIC |
| total_co2_saving_kg | NUMERIC |
| reduction_percent | NUMERIC |
| total_capex | NUMERIC |
| annual_saving | NUMERIC |
| payback_years | NUMERIC |
| generated_at | TIMESTAMPTZ |

---

# 14. Circularity Score Tables

## 14.1 `circularity_scores`

| Column | Type |
|---|---|
| id | UUID PK |
| facility_id | UUID FK |
| reporting_period_id | UUID FK |
| recycled_input_score | NUMERIC |
| waste_recovery_score | NUMERIC |
| energy_recovery_score | NUMERIC |
| water_reuse_score | NUMERIC |
| reuse_score | NUMERIC |
| total_score | NUMERIC |
| methodology_version | VARCHAR(30) |
| calculated_at | TIMESTAMPTZ |

---

# 15. Recommendation Feedback Tables

## 15.1 `recommendation_feedback`

| Column | Type |
|---|---|
| id | UUID PK |
| recommendation_id | UUID FK |
| feedback_type | VARCHAR(30) |
| reason | TEXT |
| actual_capex | NUMERIC |
| actual_annual_saving | NUMERIC |
| actual_co2_saving_kg | NUMERIC |
| submitted_at | TIMESTAMPTZ |

### Feedback Types
```text
USEFUL
NOT_APPLICABLE
CONSIDER_LATER
IMPLEMENTED
REJECTED
```

---

# 16. Benchmark Tables

## 16.1 `industry_benchmarks`

| Column | Type |
|---|---|
| id | UUID PK |
| industry_sector | VARCHAR(100) |
| process_category | VARCHAR(100) |
| region | VARCHAR(100) |
| metric_name | VARCHAR(100) |
| p25 | NUMERIC |
| median | NUMERIC |
| p75 | NUMERIC |
| unit | VARCHAR(30) |
| source | TEXT |
| source_year | INT |

Example metrics:
- kWh/tonne product
- kgCO₂e/tonne product
- water m³/tonne
- waste kg/tonne

---

# 17. Audit and Traceability Tables

## 17.1 `audit_logs`

| Column | Type |
|---|---|
| id | UUID PK |
| actor_id | UUID nullable |
| organization_id | UUID |
| event_type | VARCHAR(100) |
| entity_type | VARCHAR(100) |
| entity_id | UUID |
| old_value | JSONB |
| new_value | JSONB |
| ip_hash | VARCHAR(128) nullable |
| user_agent_hash | VARCHAR(128) nullable |
| created_at | TIMESTAMPTZ |

Important events:
- factor change
- calculation rerun
- activity data edit
- recommendation override
- scenario creation
- report generation
- file import

---

# 18. Recommended Indexes

```sql
CREATE INDEX idx_activity_facility_period
ON activity_data(facility_id, reporting_period_id);

CREATE INDEX idx_activity_process
ON activity_data(process_id);

CREATE INDEX idx_emission_factor_lookup
ON emission_factors(category, subcategory, region_country, active);

CREATE INDEX idx_emission_calc_activity
ON emission_calculations(activity_data_id);

CREATE INDEX idx_hotspot_facility_period
ON emission_hotspots(facility_id, reporting_period_id);

CREATE INDEX idx_recommendation_facility
ON recommendations(facility_id, reporting_period_id);

CREATE INDEX idx_audit_entity
ON audit_logs(entity_type, entity_id);
```

---

# 19. Database Integrity Rules

Mandatory rules:

1. Never delete emission factors used in historical calculations.
2. Never modify a locked reporting period without an explicit unlock/audit event.
3. Never allow negative consumption, production, emissions, or costs unless the field is explicitly designed for credits/exports.
4. Store original and normalized units.
5. Store calculation assumptions.
6. Keep factor source/version with every calculation.
7. Prevent duplicate activity records when same facility/process/source/period/import row is submitted twice.
8. Soft-delete business data where auditability matters.
9. Use database transactions for calculations affecting multiple tables.
10. Use row-level tenant filtering by `organization_id`.

---

# 20. Security Checklist

# Level 1 — Basic / Mandatory Hackathon Security

## Authentication and Session
- [ ] Use authenticated access for internal/admin functionality.
- [ ] Never hard-code passwords.
- [ ] Hash passwords using Argon2id or bcrypt.
- [ ] Never store plain-text passwords.
- [ ] Use secure password-reset tokens.
- [ ] Enforce session/token expiration.
- [ ] Logout must revoke/clear active session credentials.

## API Security
- [ ] All API endpoints use HTTPS in deployment.
- [ ] Validate all request payloads using Pydantic/schema validation.
- [ ] Reject unexpected fields when possible.
- [ ] Apply request size limits.
- [ ] Apply file upload size limits.
- [ ] Return generic server errors; never expose stack traces.
- [ ] Use proper HTTP status codes.
- [ ] Never trust IDs supplied by frontend without authorization checks.

## Input Validation
- [ ] Reject negative energy/material/fuel values.
- [ ] Validate units against an allow-list.
- [ ] Validate dates.
- [ ] Validate enum values.
- [ ] Sanitize filenames.
- [ ] Restrict file extensions.
- [ ] Validate MIME types.
- [ ] Validate CSV/Excel headers before import.

## SQL Security
- [ ] Use ORM/prepared statements.
- [ ] Never concatenate user input into SQL queries.
- [ ] Apply least privilege to database user.
- [ ] Do not expose DB port publicly.

## Secrets
- [ ] Store secrets in environment variables.
- [ ] `.env` must be excluded from Git.
- [ ] Rotate accidentally committed credentials immediately.
- [ ] API keys must never be sent to React/browser code.

## Frontend
- [ ] Escape all user-displayed content.
- [ ] Prevent XSS.
- [ ] Avoid `dangerouslySetInnerHTML` unless sanitized.
- [ ] Do not expose secrets in browser storage.

---

# Level 2 — Intermediate / Production-Ready Security

## Authorization
- [ ] Implement tenant isolation.
- [ ] Organization A must never access Organization B data.
- [ ] Implement roles if multiple actor types are introduced.
- [ ] Sensitive actions require explicit authorization.
- [ ] Facility access should inherit organization permission.

Suggested roles:
```text
SYSTEM_ADMIN
ORGANIZATION_ADMIN
SUSTAINABILITY_ANALYST
FACTORY_OPERATOR
VIEWER
REGULATOR_READ_ONLY
```

## Token Security
- [ ] Use short-lived access tokens.
- [ ] Use refresh-token rotation.
- [ ] Store refresh tokens securely.
- [ ] Revoke refresh tokens after password reset.
- [ ] Detect reuse of revoked refresh tokens.

## HTTP Security
- [ ] HSTS
- [ ] Content-Security-Policy
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy
- [ ] Frame protection / CSP frame-ancestors
- [ ] Strict CORS allow-list

## Rate Limiting
- [ ] Login rate limiting.
- [ ] API request rate limiting.
- [ ] File upload throttling.
- [ ] Report generation throttling.
- [ ] LLM/API usage quotas.

## File Upload Security
- [ ] Store uploads outside executable/static directories.
- [ ] Generate internal random filenames.
- [ ] Virus/malware scanning for production.
- [ ] Disable macro execution.
- [ ] Reject password-protected files unless supported safely.
- [ ] Prevent ZIP bombs.
- [ ] Prevent path traversal.
- [ ] Never execute uploaded files.

## Logging
- [ ] Log authentication failures.
- [ ] Log privileged actions.
- [ ] Log imports and factor changes.
- [ ] Do not log passwords, access tokens, API keys, or full sensitive payloads.
- [ ] Assign request/correlation IDs.

---

# Level 3 — Advanced Security

## Data Protection
- [ ] Database encryption at rest.
- [ ] TLS for database connections.
- [ ] Encrypted object/file storage.
- [ ] Field-level encryption for sensitive business fields if required.
- [ ] Centralized key management.
- [ ] Regular key rotation.

## Database Isolation
- [ ] PostgreSQL Row-Level Security for multi-tenant deployments.
- [ ] Separate read/write DB roles.
- [ ] Read-only analytics role.
- [ ] Deny destructive SQL to application runtime role.
- [ ] Database audit logging.

## Secure Deployment
- [ ] Containers run as non-root.
- [ ] Read-only container filesystem where feasible.
- [ ] Minimal production images.
- [ ] Dependency vulnerability scanning.
- [ ] Secret scanning.
- [ ] SAST.
- [ ] DAST.
- [ ] SBOM generation.
- [ ] Signed container images.

## Infrastructure
- [ ] Private database subnet.
- [ ] Web Application Firewall.
- [ ] Reverse proxy/API gateway.
- [ ] DDoS protection.
- [ ] Centralized logs.
- [ ] Automated backup.
- [ ] Tested restoration procedure.

---

# Level 4 — Advanced AI/ML/LLM Security

## LLM Safety
- [ ] Never let the LLM calculate authoritative emissions without deterministic verification.
- [ ] Use structured inputs to the LLM.
- [ ] Do not expose internal prompts/secrets.
- [ ] Defend against prompt injection from uploaded files.
- [ ] Treat extracted document text as untrusted data.
- [ ] Constrain tool/API calls.
- [ ] Validate LLM-generated recommendation IDs against the intervention database.
- [ ] Require deterministic post-validation of numbers.
- [ ] Label generated narrative separately from calculated values.
- [ ] Log model/version used.

## Recommendation Safety
- [ ] Do not recommend interventions unsupported by applicability rules.
- [ ] Do not fabricate CAPEX or savings.
- [ ] Show uncertainty/confidence.
- [ ] Show source/assumptions.
- [ ] Prevent duplicate/incompatible recommendations.
- [ ] Flag recommendations requiring engineering review.

## ML Model Security
- [ ] Version models.
- [ ] Version feature pipelines.
- [ ] Validate feature schema.
- [ ] Monitor distribution shift.
- [ ] Prevent training-serving skew.
- [ ] Verify model artifact integrity.
- [ ] Keep model registry metadata.

---

# Level 5 — Enterprise / Regulatory Security

- [ ] Immutable audit trail for finalized reports.
- [ ] Signed report checksum/hash.
- [ ] Data retention policy.
- [ ] Data deletion policy.
- [ ] Backup retention policy.
- [ ] Disaster recovery plan.
- [ ] Business continuity plan.
- [ ] Incident response plan.
- [ ] Access recertification.
- [ ] Security event monitoring.
- [ ] Segregation of duties.
- [ ] Factor/version approval workflow.
- [ ] Calculation engine change-control process.
- [ ] Penetration testing before regulated deployment.
- [ ] Privacy and regulatory assessment based on target geography.

---

# 21. Module-Wise Edge Cases

# Module A — SME / Factory Profiling

| Edge Case | Expected Handling |
|---|---|
| Organization name missing | Reject submission |
| Duplicate organization registration | Warn and verify before creating |
| Facility production = 0 | Allow profile, but block carbon-intensity calculations |
| Negative annual production | Reject |
| Unknown industry sector | Allow "Other" with text description |
| Unsupported currency | Store ISO currency if valid; otherwise reject |
| More than one facility | Keep separate facility records |
| Factory location missing | Allow if non-location-dependent calculations are possible; lower factor confidence |
| Working days > 366 | Reject |
| Working hours/day > 24 | Reject |
| Production unit not recognized | Require mapping before intensity calculations |
| Factory temporarily shut down | Mark reporting period/facility status without deleting history |

---

# Module B — Industrial Process Mapper

| Edge Case | Expected Handling |
|---|---|
| Process has no incoming flow | Allow for source/start process |
| Process has no outgoing flow | Allow for terminal process |
| Circular process loop | Allow only if intentionally modeled |
| Accidental self-loop | Reject |
| Duplicate process names | Allow only with unique codes or warn user |
| One machine used by multiple processes | Support shared asset allocation |
| Process sequence missing | Permit graph-based ordering |
| Process deleted after calculations | Soft delete only |
| Asset moved to another process | Preserve historical association |
| Unknown process category | Allow "Other" with manual label |

---

# Module C — Data Input & Ingestion

| Edge Case | Expected Handling |
|---|---|
| CSV missing mandatory columns | Reject import with clear error report |
| Duplicate CSV upload | Detect using hash/import key |
| Excel contains multiple sheets | Ask user/select mapped sheet |
| Empty file | Reject |
| Very large file | Enforce size/row limits |
| Mixed units in one column | Validate row by row |
| Formula cells | Read calculated values safely; never execute macros |
| Password-protected file | Reject unless explicitly supported |
| Corrupt file | Reject without crashing |
| Unknown column names | Offer mapping UI |
| Same activity entered manually and by file | Flag possible duplicate |
| OCR extraction uncertain | Mark as estimated and request confirmation |
| Numeric field contains commas/currency symbols | Parse only using controlled normalization |

---

# Module D — Unit Normalization & Data Quality

| Edge Case | Expected Handling |
|---|---|
| `1 tonne` entered as `1 kg` accidentally | Flag extreme intensity anomaly |
| Unknown unit | Do not calculate until mapped |
| Unit case variations | Normalize safely (`kWh`, `KWH`) |
| Volume-to-mass conversion needed | Require density/source assumption |
| Energy content conversion needed | Store conversion factor and source |
| Missing original unit | Reject or mark unusable |
| Estimated data mixed with measured data | Keep provenance and lower confidence |
| Missing month in annual period | Flag incomplete coverage |
| Overlapping reporting periods | Warn or reject depending on context |
| Value unexpectedly high | Flag but do not silently modify |
| Data quality < threshold | Show warning before recommendation generation |

---

# Module E — Emission Factor Knowledge Base

| Edge Case | Expected Handling |
|---|---|
| No exact factor available | Use approved fallback factor and lower confidence |
| Multiple valid factors | Select by geography/year/method priority |
| Factor unit does not match activity unit | Normalize before calculation |
| Expired factor | Keep for historical calculations; avoid for new periods |
| Factor updated | Create new version; never overwrite history |
| Supplier-specific factor exists | Prefer if validated |
| Factor source inaccessible | Keep source metadata and warning |
| CH₄/N₂O missing | Do not invent values |
| Factor value = 0 | Permit only for valid zero-emission case |
| Negative factor | Reject unless methodology explicitly supports credit/removal accounting |
| Region-specific grid factor missing | Use national factor and indicate lower specificity |

---

# Module F — Carbon Accounting Engine

| Edge Case | Expected Handling |
|---|---|
| Missing emission factor | Calculation status = incomplete |
| Activity value = 0 | Emission = 0 |
| Negative activity | Reject |
| Renewable electricity | Apply approved accounting methodology; do not assume zero automatically |
| On-site solar self-consumption | Separate from grid purchase |
| Electricity exported to grid | Track separately; avoid double-counting credits |
| Fuel used as feedstock, not combustion | Do not apply combustion factor automatically |
| Biogenic emissions | Track according to selected methodology |
| Refrigerant leakage | Use appropriate GWP factor |
| Duplicate activity calculation | Prevent duplicate active calculations |
| Locked reporting period | Prevent recalculation unless versioned/unlocked |
| Rounding difference | Store full precision; round only for display |

---

# Module G — Emission Leak-Point / Hotspot Detector

| Edge Case | Expected Handling |
|---|---|
| Only one process exists | It may be 100% contributor; explain limitation |
| Total emissions = 0 | Do not compute contribution percentage |
| One huge value dominates | Flag as hotspot and potential data anomaly |
| High emissions but no improvement potential | Lower actionability score |
| Low emissions but severe inefficiency | May still rank based on hotspot formula |
| Missing production values | Skip intensity component |
| Tied hotspot scores | Use deterministic tie-breaker |
| Process has incomplete data | Lower confidence |
| Negative/credit emissions included | Separate before percentage ranking |
| Hotspot based on estimated inputs | Display confidence warning |

---

# Module H — Anomaly & Inefficiency Detector

| Edge Case | Expected Handling |
|---|---|
| Too little historical data | Disable ML anomaly claim; use rules only |
| Seasonal production | Use seasonal baseline if available |
| Production shutdown | Avoid treating zero use as anomaly |
| New equipment | Establish new baseline |
| Sensor spike | Flag, do not auto-delete |
| Missing days/months | Avoid naive comparison |
| Model marks known valid event as anomaly | Allow user acknowledgment |
| Model drift | Trigger retraining/recalibration |
| Negative anomaly score semantics vary by model | Standardize score before UI |
| No benchmark available | Use internal historical baseline only |

---

# Module I — Circular Alternative Knowledge Base

| Edge Case | Expected Handling |
|---|---|
| Intervention not applicable to industry | Filter out |
| Intervention applicable only above minimum scale | Check facility scale |
| CAPEX range unavailable | Display "cost estimate unavailable" |
| Technology unavailable regionally | Lower feasibility |
| Intervention conflicts with regulation | Exclude |
| Multiple interventions overlap | Mark dependency/overlap |
| Intervention requires another intervention first | Model prerequisite |
| Claimed savings based on weak evidence | Lower confidence |
| Intervention has no CO₂ benefit but waste benefit | Keep if circularity value is material |
| Intervention can increase another impact | Display trade-off |

---

# Module J — AI Circular Recommendation Engine

| Edge Case | Expected Handling |
|---|---|
| LLM suggests unknown intervention | Reject unless mapped to approved knowledge base |
| User budget = 0 | Prioritize no/low-cost interventions |
| No feasible intervention | Return honest "no suitable recommendation" |
| Recommendation exceeds budget | Deprioritize/filter |
| Very high savings but low feasibility | Rank lower |
| Duplicate recommendations | Deduplicate |
| Conflicting interventions | Mark mutually exclusive |
| Missing CAPEX | Do not fabricate payback |
| Missing CO₂ estimate | Recommendation may remain qualitative but cannot be ranked by savings |
| User changes constraint after generation | Re-rank recommendations |
| Prompt injection in uploaded notes | Ignore untrusted instructions |
| LLM returns malformed JSON | Reject/retry through schema validation |

---

# Module K — Cost & CO₂ Impact Simulator

| Edge Case | Expected Handling |
|---|---|
| Annual saving = 0 | Payback = unavailable/infinite |
| Annual saving < 0 | Report additional annual cost |
| CAPEX = 0 | Payback = immediate if savings positive |
| Adoption = 0% | No change |
| Adoption >100% | Reject |
| Combined interventions double-count savings | Apply interaction logic |
| Two interventions affect same baseline | Recalculate sequentially or with interaction model |
| Currency mismatch | Convert explicitly or keep separate |
| Inflation/energy price assumptions missing | Show static-price assumption |
| Negative projected emissions | Floor at physically valid value unless accounting credits explicitly supported |
| CO₂ saving exceeds source emissions | Cap or flag invalid model |

---

# Module L — Circularity Score

| Edge Case | Expected Handling |
|---|---|
| Missing one score component | Reweight only if methodology explicitly permits |
| Score >100 | Cap/reject calculation defect |
| Score <0 | Reject |
| No baseline data | Mark score incomplete |
| Water reuse irrelevant to sector | Use sector-specific weighting only if documented |
| User interprets score as official certification | Display disclaimer |
| Methodology updated | Version score formula |
| Same waste counted in reuse and recycling | Prevent double counting |

---

# Module M — Recommendation Explainability

| Edge Case | Expected Handling |
|---|---|
| Explanation contradicts calculated values | Reject/regenerate |
| Explanation cites unavailable evidence | Remove unsupported claim |
| LLM invents reason | Validate against stored evidence |
| Very low confidence | Clearly state uncertainty |
| Multiple reasons | Rank top drivers |
| Technical jargon overwhelms SME user | Provide simplified and expert views |
| Recommendation generated from estimated data | Mention this explicitly |
| Missing supporting data | Do not claim causal certainty |

---

# Module N — Dashboard & Visualization

| Edge Case | Expected Handling |
|---|---|
| No data yet | Show empty-state guidance |
| One category only | Avoid misleading pie/donut chart |
| Total emissions = 0 | Handle percentage charts safely |
| Negative credits included | Visualize separately |
| Very large/small values | Use unit scaling |
| Mobile screen | Responsive layout |
| Color-blind users | Do not rely only on red/green |
| Sankey graph too complex | Aggregate minor flows |
| More than 100 processes | Use filtering/search |
| Dashboard data stale | Show last-calculated timestamp |

---

# Module O — What-If / Digital Twin Lite

| Edge Case | Expected Handling |
|---|---|
| Scenario has no interventions | Same as baseline |
| Duplicate intervention in scenario | Prevent duplication |
| Incompatible interventions | Warn/block |
| Scenario exceeds budget | Highlight infeasibility |
| Target reduction impossible | Show maximum achievable estimate |
| Intervention dependence ignored | Enforce prerequisites |
| Sequential effects matter | Apply ordered calculation |
| Baseline changed after scenario created | Mark scenario outdated |
| Factor database updated | Preserve old scenario version unless user recalculates |

---

# Module P — Compliance & Sustainability Report

| Edge Case | Expected Handling |
|---|---|
| Incomplete inventory | Label report "Draft/Incomplete" |
| Missing factor source | Highlight methodology gap |
| Missing Scope 3 | State reporting boundary clearly |
| Report generated before calculations finish | Block |
| Report regenerated after data update | Version report |
| User edits finalized report | Create new version |
| Rounding mismatch with dashboard | Use same calculation source |
| Regulatory template changes | Version template |
| Unsupported regulatory claim | Do not state compliance |
| Confidential information present | Apply access controls/redaction |

---

# Module Q — User Feedback / Recommendation Learning

| Edge Case | Expected Handling |
|---|---|
| User repeatedly changes feedback | Keep latest state + history |
| Recommendation marked implemented with no evidence | Allow but flag as self-reported |
| Actual saving > physically possible | Flag validation issue |
| Negative actual saving | Store as valid outcome if confirmed |
| Feedback from one company biases all users | Segment learning |
| Too few feedback samples | Do not train personalized model |
| Malicious/spam feedback | Rate limit and validate |
| Recommendation rejected for local reason | Capture structured reason |
| Actual CAPEX missing | Keep outcome partially complete |

---

# 22. Cross-Module Edge Cases

## Data Consistency

- Same activity must not be counted under two processes accidentally.
- Scope classification must remain consistent.
- Units must remain consistent between factor and activity data.
- Scenario calculations must use the same baseline period unless explicitly compared.
- Production denominator must correspond to the same reporting period as emissions.

## Carbon Accounting Integrity

- Avoid double counting renewable electricity.
- Avoid double counting recycling benefits.
- Separate avoided emissions from actual inventory emissions.
- Separate estimated savings from measured achieved savings.
- Never mix Scope 1, Scope 2, and Scope 3 without labels.
- Do not treat carbon offsets as operational emission reduction.

## Recommendation Integrity

- Recommendations must be technically applicable.
- Recommendations must be economically constrained.
- Recommendations must expose uncertainty.
- Recommendations must include source/provenance.
- AI-generated narrative must not overwrite deterministic numeric results.

---

# 23. Recommended Validation Severity

Use four validation levels:

```text
ERROR
WARNING
INFO
CONFIRMATION_REQUIRED
```

Examples:

### ERROR
- negative electricity consumption
- invalid date
- unsupported factor/unit conversion

### WARNING
- value 10× industry median
- national factor used instead of regional factor

### INFO
- converted MWh to kWh

### CONFIRMATION_REQUIRED
- duplicate bill suspected
- unusually high fuel usage
- OCR confidence < 85%

---

# 24. Recommended API Security Rules

Every API endpoint should verify:

```text
1. Authentication
2. Authorization
3. Tenant ownership
4. Payload schema
5. Business validation
6. Rate limit
7. Audit requirement
8. Safe error response
```

Example:

```text
PUT /api/facilities/{facility_id}/activity/{activity_id}
```

Must verify:
- user authenticated
- user belongs to organization
- facility belongs to same organization
- activity belongs to facility
- period is editable
- unit/value valid
- change logged

---

# 25. Recommended Hackathon Priorities

## Must Implement

1. Organization/facility tables
2. Process mapping
3. Activity data
4. Emission factors
5. Emission calculations
6. Hotspot detection
7. Circular interventions
8. Recommendations
9. Cost/CO₂ assessment
10. Scenario simulation
11. Audit metadata
12. Basic security checklist

## Strong Differentiators

1. Factor versioning
2. Data quality score
3. Recommendation confidence
4. Carbon Leak Map
5. Multi-criteria ranking
6. Explainable recommendation
7. Scenario interaction validation

## Future / Production

1. PostgreSQL Row-Level Security
2. Sensor integration
3. OCR
4. Supplier-specific emission factors
5. Regulatory workflows
6. Model registry
7. Enterprise identity provider
8. Signed compliance reports
9. Advanced anomaly detection
10. Continuous monitoring

---

# 26. Final Implementation Principle

The system should maintain a strict separation between:

```text
MEASURED DATA
       ↓
NORMALIZED DATA
       ↓
VERIFIED EMISSION FACTORS
       ↓
DETERMINISTIC CARBON CALCULATIONS
       ↓
HOTSPOT / ML ANALYTICS
       ↓
RULE-CONSTRAINED CIRCULAR RECOMMENDATIONS
       ↓
COST + CO₂ SIMULATION
       ↓
LLM-ASSISTED EXPLANATION
```

**Never use the LLM as the authoritative carbon-calculation engine.**

The strongest implementation will be auditable, reproducible, secure, transparent, and able to explain exactly how every emission value and recommendation was produced.
