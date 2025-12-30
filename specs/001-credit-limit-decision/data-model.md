# Data Model: Credit Limit Decision Service (MVP)

**Date**: 2025-12-30  
**Phase**: 1 - Design & Contracts  
**Purpose**: Define entities, relationships, validation rules, and state transitions

## Core Entities

### CreditDecisionRequest

**Purpose**: Represents an underwriter's request for a credit limit decision

**Attributes**:
- `buyerId`: string (required, non-empty) - Unique identifier for the buyer entity
- `policyId`: string (required, non-empty) - Unique identifier for the insurance policy
- `requestedLimit`: int (required, > 0, no decimals) - Requested credit limit in whole currency units
- `currency`: string (required, exactly 3 uppercase letters) - ISO 4217 currency code (basic format validation only)
- `requestId`: string (optional) - Idempotency key for request tracking (stored but not enforced in MVP)

**Validation Rules**:
1. `buyerId` MUST be non-empty string
2. `policyId` MUST be non-empty string
3. `requestedLimit` MUST be positive integer (reject decimals with validation error)
4. `currency` MUST match regex: `^[A-Z]{3}$`
5. `requestId` is optional (null allowed)

**Source**: Deserialized from API Gateway HTTP event body (JSON)

**Python Dataclass**:
```python
@dataclass
class CreditDecisionRequest:
    buyerId: str
    policyId: str
    requestedLimit: int
    currency: str
    requestId: Optional[str] = None
```

---

### BuyerRiskProfile

**Purpose**: Represents internal risk assessment data for a buyer (retrieved from data sources, not persisted by this service)

**Attributes**:
- `riskGrade`: Optional[str] - Risk classification: "A" (lowest), "B", "C", "D", "E" (highest), or None (unknown)
- `pastDueOver60`: Optional[bool] - Flag for overdue payments >60 days, or None (unknown)

**Validation Rules**:
1. `riskGrade` must be one of: "A", "B", "C", "D", "E", None
2. `pastDueOver60` must be True, False, or None

**Source**: Retrieved from `RiskDataSource` interface (stubbed in-memory for MVP)

**Python Dataclass**:
```python
@dataclass
class BuyerRiskProfile:
    riskGrade: Optional[str]  # "A" | "B" | "C" | "D" | "E" | None
    pastDueOver60: Optional[bool]
```

---

### CreditDecisionResponse

**Purpose**: Represents the system's decision outcome returned to the underwriter

**Attributes**:
- `decisionId`: str (required, UUID v4) - Unique identifier for this decision
- `decision`: str (required) - Decision outcome: "APPROVE", "REFER", or "DECLINE"
- `approvedLimit`: int (required, >= 0) - Approved credit limit (0 for REFER/DECLINE)
- `currency`: str (required) - Currency code echoed from request
- `reasonCodes`: list[str] (required, may be empty) - Machine-readable decision rationale
- `explanations`: list[str] (required, may be empty) - Human-readable explanations (1:1 mapping with reasonCodes)
- `timestamp`: str (required, ISO 8601 UTC) - When decision was made

**Validation Rules**:
1. `decisionId` must be valid UUID v4 string
2. `decision` must be one of: "APPROVE", "REFER", "DECLINE"
3. `approvedLimit` must be non-negative integer
4. `currency` must match request currency
5. `reasonCodes` and `explanations` must have same length
6. `timestamp` must be ISO 8601 UTC format (e.g., "2025-12-30T10:30:00.000Z")

**Serialization**: Converted to JSON for HTTP response body

**Python Dataclass**:
```python
@dataclass
class CreditDecisionResponse:
    decisionId: str
    decision: str  # "APPROVE" | "REFER" | "DECLINE"
    approvedLimit: int
    currency: str
    reasonCodes: list[str]
    explanations: list[str]
    timestamp: str  # ISO 8601 UTC
```

---

### AuditRecord

**Purpose**: Immutable audit record for regulatory compliance (persisted in DynamoDB)

**Attributes**:
- `pk`: str (partition key) - Format: "DECISION#{decisionId}"
- `decisionId`: str (required, UUID v4) - Unique decision identifier
- `timestamp`: str (required, ISO 8601 UTC) - When record was created
- `principalId`: str (required) - Who requested (from API Gateway authorizer or "anonymous")
- `buyerId`: str (required) - From request
- `policyId`: str (required) - From request
- `requestedLimit`: int (required) - From request
- `currency`: str (required) - From request
- `requestId`: Optional[str] - From request (if provided)
- `riskGrade`: Optional[str] - Derived input from data source
- `pastDueOver60`: Optional[bool] - Derived input from data source
- `decision`: Optional[str] - Decision outcome (null if validation failed)
- `approvedLimit`: Optional[int] - Approved limit (null if validation failed)
- `reasonCodes`: Optional[list[str]] - Reason codes (null if validation failed)
- `status`: str (required) - "OK" or "FAILED"
- `errorCode`: Optional[str] - Error code if status == "FAILED"
- `ttl`: Optional[int] - TTL for future retention policy (epoch seconds)

**Validation Rules**:
1. `pk` must match format: "DECISION#{decisionId}"
2. `status` must be "OK" or "FAILED"
3. If `status` == "OK", `decision`, `approvedLimit`, `reasonCodes` must be non-null
4. If `status` == "FAILED", `errorCode` must be non-null
5. No PII beyond buyerId and policyId (no names, addresses, financial details)

**Storage**: DynamoDB table "CreditDecisionAudit"

**Python Dataclass**:
```python
@dataclass
class AuditRecord:
    pk: str  # DECISION#{decisionId}
    decisionId: str
    timestamp: str
    principalId: str
    buyerId: str
    policyId: str
    requestedLimit: int
    currency: str
    requestId: Optional[str]
    riskGrade: Optional[str]
    pastDueOver60: Optional[bool]
    decision: Optional[str]
    approvedLimit: Optional[int]
    reasonCodes: Optional[list[str]]
    status: str  # "OK" | "FAILED"
    errorCode: Optional[str]
    ttl: Optional[int] = None
```

---

## Relationships

```
┌─────────────────────────┐
│ Underwriter (External)  │
└───────────┬─────────────┘
            │ POST /credit-decisions
            ▼
┌─────────────────────────────────────────┐
│       CreditDecisionRequest            │
│  - buyerId, policyId, requestedLimit   │
│  - currency, requestId (optional)      │
└──────────┬──────────────────────────────┘
           │
           │ Retrieve risk data
           ▼
┌─────────────────────────────────────────┐
│       BuyerRiskProfile                 │
│  - riskGrade (A-E or unknown)          │
│  - pastDueOver60 (true/false/unknown)  │
└──────────┬──────────────────────────────┘
           │
           │ Decision logic (pure function)
           ▼
┌─────────────────────────────────────────┐
│      CreditDecisionResponse            │
│  - decision (APPROVE/REFER/DECLINE)    │
│  - approvedLimit, reasonCodes, etc.    │
└──────────┬──────────────────────────────┘
           │
           │ Audit persistence
           ▼
┌─────────────────────────────────────────┐
│         AuditRecord                    │
│  - Full request + response + metadata  │
│  - Stored in DynamoDB                  │
└─────────────────────────────────────────┘
```

**Relationships**:
1. **1 Request → 1 Risk Profile**: Each request triggers lookup of exactly one buyer's risk profile
2. **1 Risk Profile → 1 Decision**: Pure function maps risk profile to decision outcome
3. **1 Request → 1 Response**: Each valid request produces exactly one response
4. **1 Request → 1 Audit Record**: Each request (including failed) produces exactly one audit record
5. **No entity persistence**: Only AuditRecord is stored; Request/Response/RiskProfile are ephemeral

---

## Decision State Transitions

**State Machine**: Decision logic is stateless (pure function), but decision outcomes follow fixed rules

```
                          ┌─────────────────┐
                          │  Request Input  │
                          │  + Risk Profile │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │ Validate Input  │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            ┌───────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
            │ VALIDATION   │  │  REFER   │  │ APPROVE  │
            │   ERROR      │  │          │  │          │
            └──────────────┘  └──────────┘  └──────────┘
                    │              │              │
                    │         ┌────▼────┐         │
                    │         │ DECLINE │         │
                    │         └─────────┘         │
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                          ┌────────▼────────┐
                          │  Audit Record   │
                          └─────────────────┘
```

**Decision Rules (from spec)**:

| Rule | Risk Grade | Past Due >60 | Decision | Approved Limit | Reason Code |
|------|-----------|--------------|----------|----------------|-------------|
| 1    | D or E    | any          | DECLINE  | 0              | RISK_GRADE_HIGH |
| 2    | C         | any          | REFER    | 0              | RISK_GRADE_MEDIUM |
| 3    | A or B    | true         | REFER    | 0              | PAST_DUE_OVER_60 |
| 4    | A         | false        | APPROVE  | min(requested, 1M) | LIMIT_CAPPED_BY_GRADE (if capped) |
| 5    | B         | false        | APPROVE  | min(requested, 500K) | LIMIT_CAPPED_BY_GRADE (if capped) |
| 6    | unknown   | any          | REFER    | 0              | RISK_DATA_MISSING |
| 7    | any       | unknown      | REFER    | 0              | PAST_DUE_DATA_MISSING |

**Rule Priority**: Rules evaluated in order 1-7 (first match wins)

---

## Reason Codes & Explanations

**Mapping Table**:

| Reason Code | Explanation |
|-------------|-------------|
| RISK_GRADE_HIGH | Buyer risk grade is D or E (high risk); credit cannot be approved |
| RISK_GRADE_MEDIUM | Buyer risk grade is C (medium risk); manual underwriter review required |
| PAST_DUE_OVER_60 | Buyer has outstanding invoices overdue by more than 60 days; manual review required |
| LIMIT_CAPPED_BY_GRADE | Requested limit exceeds maximum allowed for risk grade {A/B} ({1,000,000/500,000}) |
| RISK_DATA_MISSING | Buyer risk grade data is unavailable; cannot make automated decision |
| PAST_DUE_DATA_MISSING | Buyer past-due payment data is unavailable; cannot make automated decision |

**Implementation Note**: Explanations stored as constants in `decision_engine.py` module

---

## Validation Summary

**Request Validation** (performed before decision logic):
1. ✅ buyerId non-empty → `MissingFieldError` if fails
2. ✅ policyId non-empty → `MissingFieldError` if fails
3. ✅ requestedLimit > 0 → `InvalidRequestError` if fails
4. ✅ requestedLimit is integer (no decimals) → `InvalidRequestError` if fails
5. ✅ currency matches `^[A-Z]{3}$` → `InvalidRequestError` if fails

**Response Validation** (enforced by dataclass type hints):
1. ✅ reasonCodes and explanations have same length
2. ✅ approvedLimit is 0 for REFER/DECLINE decisions
3. ✅ decision is one of APPROVE/REFER/DECLINE

**Audit Validation** (enforced before DynamoDB write):
1. ✅ pk format is "DECISION#{decisionId}"
2. ✅ status is "OK" or "FAILED"
3. ✅ No PII beyond identifiers

---

## Data Flow Diagram

```
API Gateway → Lambda Handler
                │
                ├─→ Validate Request → ValidationError?
                │                          │
                │                          ├─→ Write Audit (FAILED)
                │                          └─→ Return 400 Error
                │
                ├─→ Retrieve Risk Data → BuyerRiskProfile
                │
                ├─→ Decision Engine (pure) → CreditDecisionResponse
                │
                ├─→ Write Audit (OK)
                │
                └─→ Return 200 Response
```

**Data Persistence**: Only AuditRecord is persisted to DynamoDB. All other entities are request-scoped.

**Immutability**: All dataclasses should be frozen (`@dataclass(frozen=True)`) to prevent mutation and enforce determinism.

---

## Summary

**4 Core Entities Defined**:
1. ✅ CreditDecisionRequest - Input from underwriter
2. ✅ BuyerRiskProfile - Risk data from internal sources
3. ✅ CreditDecisionResponse - Decision outcome to underwriter
4. ✅ AuditRecord - Compliance audit trail

**7 Decision Rules Mapped** to reason codes and explanations

**Validation Rules Specified** for all attributes

**Ready for API Contract Generation** (Phase 1 next step)
