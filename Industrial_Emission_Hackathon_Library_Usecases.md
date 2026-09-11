# Industrial Emission Leak-Point Detector & Circular Alternative Recommender
## Recommended Libraries, Security Use Cases, and Edge-Case Handling

**Target stack:** React + FastAPI + PostgreSQL + Python ML services

---

# 1. Recommended Library Stack

| Area | Library | Priority | Primary Use |
|---|---|---:|---|
| API validation | **Pydantic v2** | Must | Request validation, ranges, enums, cross-field rules |
| Database ORM | **SQLAlchemy 2.x** | Must | Models, relationships, constraints, transactions |
| Database migrations | **Alembic** | Must | Safe schema versioning |
| PostgreSQL driver | **psycopg** | Must | PostgreSQL connectivity |
| Password hashing | **pwdlib[argon2]** | Must if login exists | Secure password hashing |
| JWT authentication | **PyJWT** | Must if login exists | Access-token generation and validation |
| App configuration | **pydantic-settings** | Must | Environment variables and secrets |
| Unit conversion | **Pint** | Must | kg↔tonne, kWh↔MWh, litre↔m³ |
| CSV/Excel validation | **Pandera** | Must | Schema/range/data-quality validation |
| Excel processing | **openpyxl** | Must | `.xlsx` import |
| Tabular processing | **pandas** | Must | CSV/Excel preprocessing and aggregation |
| Machine learning | **scikit-learn** | Must | Anomaly detection and recommendation scoring |
| Retry handling | **Tenacity** | Strong | External API/LLM retries |
| Testing | **pytest** | Must | Unit and integration tests |
| Async testing | **pytest-asyncio** | Strong | FastAPI async test coverage |
| Edge-case generation | **Hypothesis** | Strong | Property-based testing |
| API tests | **httpx** | Must | FastAPI endpoint testing |
| Structured logging | **structlog** | Useful | Audit/security/application logs |
| Frontend validation | **Zod** | Must | Browser-side schema validation |
| React form handling | **React Hook Form** | Strong | Form state and validation UX |
| Resolver integration | **@hookform/resolvers** | Strong | Connect Zod with React Hook Form |
| HTML sanitization | **DOMPurify** | Conditional | Sanitizing rendered HTML/LLM output |
| Rate limiting | **Redis + fastapi-redis-sdk** | Production | API/login/LLM throttling |
| MIME checking | **python-magic** | Production | Uploaded-file type validation |
| Malware scanning | **ClamAV** | Production | Uploaded-file malware scanning |
| Error monitoring | **Sentry SDK** | Production | Runtime exception monitoring |

---

# 2. Core Validation Library — Pydantic v2

## Use Cases

Use **Pydantic** for all backend request and response models.

Recommended validations:

- Non-negative electricity consumption
- Non-negative fuel/material/waste quantities
- Production must be greater than zero where intensity is calculated
- Working hours must be between 0 and 24
- Adoption percentage must be between 0 and 100
- Confidence scores must be between 0 and 100
- Reporting end date must not precede start date
- Enum validation for:
  - Scope 1/2/3
  - activity type
  - severity
  - recommendation status
  - reporting-period status
- Validate currency codes
- Validate supported units
- Validate scenario constraints

## Best Fit

```text
Frontend request
      ↓
FastAPI
      ↓
Pydantic validation
      ↓
Business logic
      ↓
Database
```

## Example

```python
from pydantic import BaseModel, Field, model_validator
from datetime import date

class ActivityInput(BaseModel):
    value: float = Field(ge=0)
    unit: str
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self
```

---

# 3. Database Integrity — SQLAlchemy 2.x

## Use Cases

Use SQLAlchemy for:

- ORM entities
- foreign keys
- uniqueness
- check constraints
- indexes
- database transactions
- soft-deletion workflows
- tenant filtering
- relationship management

## Critical Constraints

Examples:

```python
CheckConstraint(
    "annual_production >= 0",
    name="ck_facility_production_nonnegative"
)
```

```python
CheckConstraint(
    "working_hours_per_day >= 0 AND working_hours_per_day <= 24"
)
```

```python
UniqueConstraint(
    "organization_id",
    "facility_code"
)
```

## Why Both Pydantic and SQLAlchemy/PostgreSQL?

```text
Pydantic
    ↓
Application validation

SQLAlchemy/PostgreSQL
    ↓
Final data-integrity protection
```

Never depend only on frontend or API validation.

---

# 4. Database Migration — Alembic

## Use Cases

Use **Alembic** whenever database structure changes.

Examples:

- adding a new emission-factor column
- adding recommendation confidence
- adding scenario tables
- changing indexes
- adding constraints
- introducing audit fields

Avoid manual production database modifications.

---

# 5. Unit Conversion — Pint

## Important for This Hackathon

Incorrect units can completely distort carbon calculations.

Use **Pint** for safe compatible-unit conversions.

Examples:

```text
tonne ↔ kilogram
MWh ↔ kWh
GJ ↔ MJ
m³ ↔ litre
km ↔ metre
```

## Example

```python
from pint import UnitRegistry

ureg = UnitRegistry()

value = 1.5 * ureg.tonne
kg = value.to("kilogram")
```

Result:

```text
1500 kilogram
```

## Important Limitation

Do not automatically convert:

```text
litre diesel → kg diesel
m³ natural gas → kWh
```

unless a verified density/calorific conversion factor is available.

Store:

- conversion factor
- source
- year/version
- assumption
- confidence

---

# 6. CSV / Excel Validation — Pandera

## Use Cases

Use **Pandera** after loading external tabular files.

Validate:

- mandatory columns
- numeric fields
- non-negative values
- null values
- valid categories
- duplicate rows
- supported units
- date formats
- facility/process IDs
- row-level business rules

## Example

```python
import pandera.pandas as pa

schema = pa.DataFrameSchema({
    "Process": pa.Column(str, nullable=False),
    "Electricity_kWh": pa.Column(
        float,
        pa.Check.ge(0)
    ),
    "Fuel_Litre": pa.Column(
        float,
        pa.Check.ge(0)
    ),
})
```

## Recommended Separation

```text
Pydantic
→ API payload validation

Pandera
→ CSV / Excel dataframe validation
```

---

# 7. Excel Handling — openpyxl

## Use Cases

Use **openpyxl** for:

- reading `.xlsx`
- sheet inspection
- cell extraction
- controlled Excel import
- validation before dataframe conversion

## Edge Cases to Handle

- multiple sheets
- empty workbook
- formulas
- corrupt file
- hidden sheets
- password-protected workbook
- mixed data types
- merged cells
- invalid column headers

---

# 8. Tabular Processing — pandas

## Use Cases

Use **pandas** for:

- CSV import
- Excel-to-dataframe conversion
- grouping emissions by process
- aggregation by Scope 1/2/3
- carbon intensity
- waste intensity
- production-normalized values
- recommendation analytics
- report tables

Example operations:

```text
groupby
merge
pivot_table
fillna
astype
drop_duplicates
```

Do not rely on pandas alone for validation. Use Pandera afterward.

---

# 9. Machine Learning — scikit-learn

## Recommended Use

Use ML only where ML adds value.

### Anomaly Detection

Recommended starting model:

```text
IsolationForest
```

Potential features:

- kWh/unit production
- fuel/unit production
- waste/unit production
- machine operating hours
- water/unit production
- CO₂ intensity

### Recommendation Ranking

Possible models later:

- Logistic Regression
- Random Forest
- Gradient Boosting
- LightGBM/CatBoost if sufficient historical labels become available

For hackathon MVP, a **weighted multi-criteria ranker** is safer and more explainable than an unnecessary complex ML model.

---

# 10. Retry Handling — Tenacity

## Use Cases

Use **Tenacity** for temporary failures from:

- LLM APIs
- external emission-factor APIs
- regulatory APIs
- remote data sources
- cloud storage

## Retry

Recommended:

```text
429 Too Many Requests
502 Bad Gateway
503 Service Unavailable
504 Gateway Timeout
TimeoutError
ConnectionError
```

## Do Not Retry

```text
400 Bad Request
401 Unauthorized
403 Forbidden
Pydantic validation error
Invalid business-rule request
```

## Example

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(
        multiplier=1,
        min=1,
        max=8
    )
)
def load_external_factor():
    ...
```

---

# 11. Password Security — pwdlib[argon2]

## Use Cases

Use for password hashing.

Architecture:

```text
Plain password
     ↓
Argon2id hash
     ↓
Database
```

Never store:

```text
password = "student123"
```

Store only the password hash.

## Security Rules

- never log passwords
- never return password hashes through APIs
- enforce minimum password requirements
- reset tokens must expire
- invalidate sessions after password change where applicable

---

# 12. Authentication — PyJWT

## Use Cases

Use **PyJWT** for:

- access-token generation
- access-token verification
- expiration checking
- role/identity claims

Suggested token claims:

```text
sub
organization_id
role
iat
exp
jti
```

Do not store secrets inside JWT payloads.

---

# 13. Configuration & Secrets — pydantic-settings

## Use Cases

Use for:

- DATABASE_URL
- JWT_SECRET
- JWT_ALGORITHM
- external API keys
- LLM API keys
- environment configuration
- allowed frontend origins

Example:

```text
.env
```

must never be committed to Git.

Add:

```text
.env
.env.*
```

to `.gitignore`.

---

# 14. Testing — pytest

## Use Cases

Write tests for:

### Carbon engine
- activity × factor
- zero consumption
- missing factor
- rounding

### Unit converter
- tonne→kg
- MWh→kWh
- incompatible-unit rejection

### Scenario engine
- 0% adoption
- 100% adoption
- incompatible interventions
- budget limit

### Recommendation engine
- rank consistency
- duplicate filtering
- feasibility filtering

### API
- invalid payload
- unauthorized request
- wrong tenant
- duplicate activity
- invalid unit

---

# 15. Async Testing — pytest-asyncio

Use **pytest-asyncio** for asynchronous FastAPI code.

Best for:

- async database calls
- async endpoints
- async external APIs
- async recommendation generation

---

# 16. Property-Based Testing — Hypothesis

## Strong Recommendation

Hypothesis is one of the best libraries for finding edge cases automatically.

Instead of manually choosing:

```text
0
1
-1
999999999
NaN
Infinity
```

Hypothesis generates many combinations automatically.

## Example

```python
from hypothesis import given
from hypothesis import strategies as st

@given(
    st.floats(
        min_value=0,
        max_value=10_000_000,
        allow_nan=False,
        allow_infinity=False
    )
)
def test_emission_never_negative(activity):
    result = calculate_emission(
        activity,
        emission_factor=0.8
    )

    assert result >= 0
```

## Important Invariants to Test

```text
Emission >= 0
0 <= CircularityScore <= 100
0 <= AdoptionPercentage <= 100
ProjectedEmissions >= 0
HotspotContribution <= 100
Payback cannot divide by zero
```

---

# 17. API Testing — httpx

Use **httpx** with FastAPI tests.

Test:

```text
POST /activities
POST /calculations
POST /recommendations
POST /scenarios
GET /dashboard
```

Validate:

- status codes
- JSON schema
- authentication
- validation errors
- tenant isolation
- safe server errors

---

# 18. Structured Logging — structlog

## Use Cases

Recommended for:

- login failures
- activity import
- emission calculation
- factor change
- recommendation generation
- scenario creation
- report generation
- unexpected errors

Useful fields:

```text
timestamp
request_id
organization_id
facility_id
actor_id
event
severity
```

Never log:

- passwords
- JWTs
- API keys
- complete confidential uploaded datasets

---

# 19. Frontend Validation — Zod

## Use Cases

Use Zod for:

- required fields
- numeric ranges
- unit validation
- percentages
- date validation
- enums

Example:

```typescript
const ActivitySchema = z.object({
  electricity: z.number().nonnegative(),
  production: z.number().positive(),
  unit: z.string().min(1),
  adoptionPercentage: z.number().min(0).max(100)
});
```

## Important Principle

```text
Zod
↓
User experience

Pydantic
↓
Security / server validation
```

Never trust frontend validation alone.

---

# 20. React Form Handling — React Hook Form

## Use Cases

Use for:

- factory-profile forms
- process forms
- activity entry
- scenario sliders
- recommendation feedback
- validation error display

Benefits:

- efficient form state
- validation integration
- less manual state-management code

---

# 21. Zod Integration — @hookform/resolvers

Use this to connect:

```text
React Hook Form
      +
     Zod
```

so that frontend validation rules remain declarative and reusable.

---

# 22. XSS Protection — DOMPurify

## Use Only When Necessary

React escapes normal strings automatically.

Use DOMPurify if rendering raw HTML such as:

```typescript
dangerouslySetInnerHTML={{
  __html: htmlContent
}}
```

Recommended approach for LLM output:

```text
LLM
 ↓
Structured JSON
 ↓
Pydantic validation
 ↓
React components
```

This is safer than raw HTML generation.

---

# 23. Rate Limiting — Redis + fastapi-redis-sdk

## Production Use Cases

Apply rate limiting to:

```text
POST /login
POST /upload
POST /recommendations/generate
POST /llm/explain
POST /reports/generate
```

Example policies:

```text
/login
5 requests/minute

/upload
10 requests/minute

/llm/explain
20 requests/hour
```

Redis is not necessary for the first local hackathon prototype.

---

# 24. MIME Validation — python-magic

## Production Use Cases

Validate real uploaded file type instead of trusting filename extension.

Example:

```text
report.xlsx
```

should actually be detected as an Excel MIME type.

Helps prevent:

```text
malware.exe renamed as report.xlsx
```

---

# 25. Malware Scanning — ClamAV

## Production Use Case

Recommended when users upload:

- spreadsheets
- PDFs
- documents
- ZIP archives

Pipeline:

```text
Upload
  ↓
MIME validation
  ↓
ClamAV scan
  ↓
File parsing
```

Not necessary for the first hackathon demo.

---

# 26. Runtime Monitoring — Sentry SDK

## Production Use Cases

Useful for:

- unhandled backend exceptions
- frontend runtime errors
- API failure tracing
- performance monitoring

Do not send confidential business data to monitoring tools unnecessarily.

---

# 27. Money Calculations — Python Decimal

No external package required.

Use:

```python
from decimal import Decimal
```

for:

- CAPEX
- OPEX
- annual saving
- payback
- ₹/tCO₂ avoided
- currency values

Example:

```python
capex = Decimal("420000.00")
saving = Decimal("160000.00")

payback = capex / saving
```

Avoid binary floating-point arithmetic for financial calculations.

---

# 28. Custom Exception Architecture

Create domain-specific exceptions.

```python
class CarbonPlatformError(Exception):
    pass

class InvalidUnitError(CarbonPlatformError):
    pass

class EmissionFactorNotFoundError(CarbonPlatformError):
    pass

class DuplicateActivityError(CarbonPlatformError):
    pass

class InvalidScenarioError(CarbonPlatformError):
    pass

class InterventionNotApplicableError(CarbonPlatformError):
    pass

class InsufficientDataError(CarbonPlatformError):
    pass
```

Then use FastAPI global exception handlers.

Example API response:

```json
{
  "error_code": "EMISSION_FACTOR_NOT_FOUND",
  "message": "No compatible emission factor is available.",
  "severity": "WARNING",
  "details": {
    "activity": "Grid Electricity",
    "region": "Gujarat"
  }
}
```

---

# 29. Recommended Library Mapping by Module

| Module | Recommended Libraries |
|---|---|
| A — Factory Profile | Pydantic, SQLAlchemy |
| B — Process Mapper | Pydantic, SQLAlchemy, NetworkX optional |
| C — Data Import | pandas, openpyxl, Pandera |
| D — Unit Normalization | Pint, Pandera |
| E — Emission Factor KB | SQLAlchemy, Alembic |
| F — Carbon Accounting | Pydantic, Decimal, pytest, Hypothesis |
| G — Hotspot Detection | pandas, NumPy, Hypothesis |
| H — Anomaly Detection | scikit-learn |
| I — Circular Alternative KB | SQLAlchemy, Pydantic |
| J — Recommendation Engine | scikit-learn, Pydantic |
| K — Cost & CO₂ Simulator | Decimal, Hypothesis |
| L — Circularity Score | Pydantic, Hypothesis |
| M — Explainability | Pydantic structured outputs |
| N — Dashboard | Zod, React Hook Form |
| O — Scenario Simulator | Pydantic, Hypothesis |
| P — Reports | Jinja2; WeasyPrint/ReportLab later |
| Q — User Feedback | Pydantic, SQLAlchemy |
| Authentication | pwdlib[argon2], PyJWT |
| API protection | Redis + rate limiting |
| XSS protection | DOMPurify when required |
| External API retry | Tenacity |
| Logging | structlog |
| Monitoring | Sentry production |

---

# 30. Recommended Backend Installation

```bash
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy alembic psycopg "pwdlib[argon2]" PyJWT python-multipart pint pandas pandera openpyxl scikit-learn tenacity pytest pytest-asyncio hypothesis httpx structlog
```

---

# 31. Recommended Frontend Installation

```bash
npm install zod react-hook-form @hookform/resolvers dompurify
```

---

# 32. Libraries to Add Later for Production

Backend:

```bash
pip install sentry-sdk python-magic
```

Infrastructure:

```text
Redis
ClamAV
WAF/API Gateway
centralized logging
secret manager
container scanning
```

---

# 33. Recommended Minimal Hackathon Stack

If implementation time is limited, prioritize these libraries:

```text
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
Pint
pandas
Pandera
openpyxl
scikit-learn
pytest
Hypothesis
Zod
React Hook Form
```

For login:

```text
pwdlib[argon2]
PyJWT
```

For external API/LLM reliability:

```text
Tenacity
```

---

# 34. Most Important Combination for Edge Cases

The strongest combination for this hackathon is:

```text
Pydantic
   +
Pandera
   +
Pint
   +
SQLAlchemy/PostgreSQL constraints
   +
pytest
   +
Hypothesis
```

Each layer solves a different class of problem:

| Layer | Responsibility |
|---|---|
| Pydantic | API validation |
| Pandera | CSV/Excel validation |
| Pint | Unit safety |
| PostgreSQL constraints | Final data integrity |
| pytest | Deterministic test coverage |
| Hypothesis | Automatic edge-case discovery |

---

# 35. Recommended Validation Pipeline

```text
User Input / Uploaded File
          ↓
Frontend Zod Validation
          ↓
FastAPI Request Boundary
          ↓
Pydantic Validation
          ↓
CSV/Excel → Pandera Validation
          ↓
Pint Unit Normalization
          ↓
Business-Rule Validation
          ↓
SQLAlchemy Transaction
          ↓
PostgreSQL Constraints
          ↓
Carbon Calculation Engine
          ↓
Recommendation / Scenario Engine
```

---

# 36. Security Principle for AI/LLM Components

The LLM should never be the authoritative calculation engine.

Recommended architecture:

```text
Measured Data
    ↓
Validated Data
    ↓
Verified Emission Factor
    ↓
Deterministic Carbon Calculation
    ↓
Hotspot Detection
    ↓
Rule-Constrained Recommendation
    ↓
Cost / CO₂ Simulation
    ↓
LLM Explanation
```

The LLM may explain, summarize, or rephrase results.

It should not invent:

- emission factors
- CO₂ totals
- CAPEX values
- savings
- payback periods
- regulatory compliance claims

without validated data and deterministic checks.

---

# 37. Final Recommendation

For the hackathon MVP, do **not** over-engineer security tooling.

Focus first on:

1. **Pydantic** — API validation
2. **Pandera** — imported data validation
3. **Pint** — unit safety
4. **SQLAlchemy + PostgreSQL constraints** — final integrity
5. **pwdlib + PyJWT** — authentication, if required
6. **pytest + Hypothesis** — systematic edge-case testing
7. **Zod + React Hook Form** — frontend validation
8. **Tenacity** — external API resilience
9. **scikit-learn** — anomaly detection
10. **structlog** — auditable application logs

This gives the team a strong balance of **security, correctness, explainability, implementation speed, and hackathon feasibility**.
