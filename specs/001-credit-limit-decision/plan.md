# Implementation Plan: Credit Limit Decision Service (MVP)

**Branch**: `001-credit-limit-decision` | **Date**: 2025-12-30 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/001-credit-limit-decision/spec.md`

## Summary

Build a deterministic credit limit decision service for trade credit insurance underwriters. The service provides instant APPROVE/REFER/DECLINE decisions based on buyer risk grade and payment history, with full explainability (reason codes + human explanations) and regulatory audit trail. Implemented as AWS Lambda (Python 3.13) with API Gateway frontend and DynamoDB audit storage.

**Technical Approach**: Pure function decision engine (no I/O) wrapped by Lambda handler that orchestrates: request validation → data retrieval (stubbed for MVP) → decision logic → audit persistence → response formatting. Strict module boundaries ensure decision logic can be tested independently and remains deterministic.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: boto3 (AWS SDK), dataclasses (stdlib), json (stdlib), uuid (stdlib), datetime (stdlib)  
**Storage**: AWS DynamoDB (audit records only; table name: CreditDecisionAudit)  
**Testing**: pytest (unit tests for decision matrix, integration tests for handler validation)  
**Target Platform**: AWS Lambda with Python 3.13 runtime, deployed via AWS SAM  
**Project Type**: Single serverless project (Lambda function + SAM IaC)  
**Performance Goals**: <200ms p95 latency (excluding cold start), <100 requests/sec expected load  
**Constraints**: No external frameworks (Flask/FastAPI), minimal dependencies (stdlib + boto3), pure function decision logic  
**Scale/Scope**: MVP with 7 decision rules, 4 user stories, ~10 modules, ~1500 LOC estimated

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Principle I: Deterministic Decision Logic (NON-NEGOTIABLE)

**Check**: Decision engine implemented as pure function?  
**Status**: ✅ **PASS** - `decision_engine.py` will contain pure function `evaluate_decision()` with no I/O, no random, no timestamps. Returns deterministic output for given inputs.

**Check**: No AWS SDK calls inside decision logic?  
**Status**: ✅ **PASS** - DynamoDB writes isolated to `audit_repo.py`, data retrieval isolated to `data_sources.py`. Decision engine only receives plain dataclass inputs.

### ✅ Principle II: Explainability & Auditability (NON-NEGOTIABLE)

**Check**: Every decision returns reason codes + explanations?  
**Status**: ✅ **PASS** - `CreditDecisionResponse` dataclass includes `reasonCodes: list[str]` and `explanations: list[str]` fields. Spec defines all 7 reason codes with explanations.

**Check**: All decisions stored in DynamoDB audit table?  
**Status**: ✅ **PASS** - `audit_repo.py` writes audit record for every request (including validation failures) with full payload.

**Check**: No PII beyond identifiers?  
**Status**: ✅ **PASS** - Audit schema only stores buyerId, policyId (identifiers), no names or addresses per spec FR-014.

### ✅ Principle III: Type Safety & Data Contracts

**Check**: Python type hints throughout?  
**Status**: ✅ **PASS** - All modules will use type hints. `models.py` defines dataclasses with full type annotations.

**Check**: Dataclasses for request/response models?  
**Status**: ✅ **PASS** - `models.py` contains: `CreditDecisionRequest`, `CreditDecisionResponse`, `BuyerRiskProfile`, `AuditRecord` as dataclasses.

**Check**: No untyped dictionaries passed between modules?  
**Status**: ✅ **PASS** - Handler deserializes JSON → dataclass, passes typed objects to decision engine, returns typed dataclass.

### ✅ Principle IV: Minimal Dependencies & Simplicity

**Check**: Dependencies limited to stdlib + boto3?  
**Status**: ✅ **PASS** - No FastAPI, Flask, or heavy frameworks. Only boto3 for DynamoDB, rest is stdlib.

### ✅ Principle V: Observability & Correlation

**Check**: Structured JSON logs with decisionId?  
**Status**: ✅ **PASS** - Handler will use `json.dumps()` for structured logging, include decisionId in all log entries.

### ✅ Principle VI: Error Handling & API Contracts

**Check**: JSON error responses with errorCode + message?  
**Status**: ✅ **PASS** - `errors.py` defines error types mapped to HTTP status + JSON schema `{"errorCode": "...", "message": "..."}`.

### ✅ Principle VII: Code Quality & Maintainability

**Check**: Black-compatible formatting, clear modules, readable names?  
**Status**: ✅ **PASS** - Module structure (models, decision_engine, data_sources, audit_repo, errors, handler) provides clear boundaries. Will use `black` for formatting.

### ✅ Technology Stack Constraints

**Check**: Python 3.13, Lambda, API Gateway, DynamoDB, SAM, pytest?  
**Status**: ✅ **PASS** - `template.yaml` defines Lambda with Python 3.13 runtime, API Gateway HTTP API integration, DynamoDB table. Tests use pytest.

### 🟢 **GATE VERDICT: PASS - Proceed to Phase 0 Research**

**No constitution violations detected.** Design fully compliant with all 7 core principles and technology constraints.

## Project Structure

### Documentation (this feature)

```text
specs/001-credit-limit-decision/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── api-contract.yaml
├── checklists/          
│   └── requirements.md  # Spec quality checklist (already exists)
└── spec.md              # Feature specification (already exists)
```

### Source Code (repository root)

```text
src/credit_decision/
├── handler.py           # Lambda entrypoint (API Gateway proxy integration)
├── models.py            # Dataclasses: Request, Response, RiskProfile, AuditRecord
├── decision_engine.py   # Pure function: evaluate_decision()
├── data_sources.py      # Stubbed risk data lookups (in-memory dicts for MVP)
├── audit_repo.py        # DynamoDB writer for audit records
└── errors.py            # Error types + HTTP status mapping

tests/
├── test_decision_engine.py      # Unit tests for all 7 decision rules (decision matrix)
├── test_handler_validation.py   # Integration tests for request validation
└── test_integration.py          # End-to-end Lambda handler tests

template.yaml            # AWS SAM Infrastructure as Code
README.md                # Local development + deployment instructions
pyproject.toml           # pytest configuration (minimal)
requirements.txt         # Python dependencies: boto3
```

**Structure Decision**: Single project structure selected. No frontend (API-only service), no mobile (server-side only). Lambda function is self-contained with clear module boundaries per constitution principle VII.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**Status**: N/A - No violations detected. All constitution principles satisfied by design.

---

## Acceptance Criteria to Implementation Mapping

**Purpose**: Map each acceptance criterion from spec to specific tests and modules

### Decision Logic (9 criteria)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-1 | Risk grade D/E → DECLINE | `test_decision_engine.py::test_decline_high_risk` | `decision_engine.py` |
| AC-2 | Risk grade C → REFER | `test_decision_engine.py::test_refer_medium_risk` | `decision_engine.py` |
| AC-3 | Grade A/B + past due → REFER | `test_decision_engine.py::test_refer_past_due` | `decision_engine.py` |
| AC-4 | Grade A + no past due, limit ≤ 1M → APPROVE | `test_decision_engine.py::test_approve_grade_a_under_limit` | `decision_engine.py` |
| AC-5 | Grade A + no past due, limit > 1M → APPROVE (capped) | `test_decision_engine.py::test_approve_grade_a_capped` | `decision_engine.py` |
| AC-6 | Grade B + no past due, limit ≤ 500K → APPROVE | `test_decision_engine.py::test_approve_grade_b_under_limit` | `decision_engine.py` |
| AC-7 | Grade B + no past due, limit > 500K → APPROVE (capped) | `test_decision_engine.py::test_approve_grade_b_capped` | `decision_engine.py` |
| AC-8 | Missing risk grade → REFER | `test_decision_engine.py::test_refer_missing_risk_grade` | `decision_engine.py` |
| AC-9 | Missing past due data → REFER | `test_decision_engine.py::test_refer_missing_past_due` | `decision_engine.py` |

### Validation (5 criteria)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-10 | Missing buyerId → HTTP 400 | `test_handler_validation.py::test_missing_buyer_id` | `handler.py`, `errors.py` |
| AC-11 | Missing policyId → HTTP 400 | `test_handler_validation.py::test_missing_policy_id` | `handler.py`, `errors.py` |
| AC-12 | requestedLimit ≤ 0 → HTTP 400 | `test_handler_validation.py::test_negative_limit` | `handler.py`, `errors.py` |
| AC-13 | Decimal requestedLimit → HTTP 400 | `test_handler_validation.py::test_decimal_limit` | `handler.py`, `errors.py` |
| AC-14 | Invalid currency format → HTTP 400 | `test_handler_validation.py::test_invalid_currency` | `handler.py`, `errors.py` |

### Audit (4 criteria)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-15 | Successful decision → audit record with status "OK" | `test_integration.py::test_audit_success` | `audit_repo.py`, `handler.py` |
| AC-16 | Validation error → audit record with status "FAILED" | `test_integration.py::test_audit_validation_error` | `audit_repo.py`, `handler.py` |
| AC-17 | Authorizer present → principalId from requestContext | `test_integration.py::test_principal_from_authorizer` | `handler.py` |
| AC-18 | No authorizer → principalId = "anonymous" | `test_integration.py::test_principal_anonymous` | `handler.py` |

### Response Format (4 criteria)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-19 | Success → HTTP 200 with JSON (all fields) | `test_integration.py::test_response_format_success` | `handler.py`, `models.py` |
| AC-20 | Validation error → HTTP 400 with errorCode/message | `test_handler_validation.py::test_error_response_format` | `handler.py`, `errors.py` |
| AC-21 | Internal error → HTTP 500 with errorCode/message | `test_integration.py::test_internal_error_response` | `handler.py`, `errors.py` |
| AC-22 | All responses → Content-Type: application/json | `test_integration.py::test_content_type_header` | `handler.py` |

### Determinism (1 criterion)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-23 | Identical inputs → identical outputs (except ID/timestamp) | `test_decision_engine.py::test_determinism` | `decision_engine.py` |

### Observability (2 criteria)

| AC# | Acceptance Criterion | Test File | Module |
|-----|---------------------|-----------|--------|
| AC-24 | All logs include decisionId | `test_integration.py::test_logs_include_decision_id` | `handler.py` |
| AC-25 | Logs are structured JSON | `test_integration.py::test_structured_logging` | `handler.py` |

**Total**: 25 acceptance criteria mapped to specific tests and modules

---

## Implementation Sequence

### Phase 0: Research ✅ COMPLETE

**Output**: [research.md](research.md)

**Findings**:
- Python 3.13 dataclass approach validated
- API Gateway HTTP API selected (Lambda proxy integration)
- DynamoDB partition key design: `DECISION#{decisionId}`
- Protocol-based data source abstraction for MVP stubbing
- Custom exception hierarchy for error mapping
- Parameterized pytest for decision matrix testing
- Minimal IAM: DynamoDB PutItem only
- Flat JSON structured logging format

---

### Phase 1: Design & Contracts ✅ COMPLETE

**Output**: [data-model.md](data-model.md), [contracts/api-contract.yaml](contracts/api-contract.yaml), [quickstart.md](quickstart.md)

**Artifacts Generated**:
1. **Data Model**: 4 core entities defined with validation rules, relationships, state transitions
2. **API Contract**: OpenAPI 3.0 specification with request/response schemas, examples, error cases
3. **Quickstart Guide**: Local development setup, testing strategy, deployment instructions, troubleshooting

**Re-check Constitution**:
- ✅ Principle I: Data model enforces pure function pattern (decision_engine takes dataclasses, no I/O)
- ✅ Principle II: Response model includes reasonCodes + explanations fields
- ✅ Principle III: All entities defined as dataclasses with type hints
- ✅ All principles remain compliant post-design

---

### Phase 2: Task Breakdown (NOT in scope for /speckit.plan)

**Note**: Task breakdown is created by `/speckit.tasks` command, not by `/speckit.plan`.

**Next Command**: Run `/speckit.tasks` to generate [tasks.md](tasks.md) with implementation tasks organized by user story priority.

---

## IAM Permissions (Minimal)

**Principle**: Least privilege - grant only what's necessary for MVP

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBWriteOnly",
      "Effect": "Allow",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:*:*:table/CreditDecisionAudit"
    },
    {
      "Sid": "CloudWatchLogging",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

**SAM Template Implementation**:
```yaml
Policies:
  - DynamoDBWritePolicy:
      TableName: !Ref CreditDecisionAuditTable
  - CloudWatchLogsFullAccess  # Auto-added by SAM for logging
```

**No Additional Permissions Needed**:
- ❌ No S3 access (no file storage)
- ❌ No SQS/SNS (no async messaging)
- ❌ No external API calls (data sources stubbed)
- ❌ No DynamoDB read/query (audit is write-only in MVP)

---

## Summary & Next Steps

### What's Been Completed

✅ **Phase 0: Research** - All technical unknowns resolved, technology decisions documented  
✅ **Phase 1: Design & Contracts** - Data model, API contract, and quickstart guide created  
✅ **Constitution Check** - All 7 principles validated, no violations

### Artifacts Created

- [research.md](research.md) - Technology decisions and rationale
- [data-model.md](data-model.md) - Entity definitions, validation rules, relationships
- [contracts/api-contract.yaml](contracts/api-contract.yaml) - OpenAPI 3.0 specification
- [quickstart.md](quickstart.md) - Developer onboarding and implementation guide

### Ready For Implementation

**Branch**: `001-credit-limit-decision`  
**Next Command**: `/speckit.tasks` to generate task breakdown  
**Test Coverage Target**: >90% for decision_engine.py, >80% overall  
**Deployment Target**: AWS Lambda + API Gateway + DynamoDB via SAM

### Key Implementation Reminders

1. **Pure Function**: `decision_engine.evaluate_decision()` must have zero I/O
2. **Type Hints**: Use dataclasses with full type annotations throughout
3. **Error Handling**: Custom exceptions mapped to HTTP status + JSON errors
4. **Audit**: Write audit record for every request (including validation failures)
5. **Logging**: Structured JSON with decisionId in all log entries
6. **Testing**: Parameterized tests for all 25 acceptance criteria

**Command Complete**: `/speckit.plan` execution finished. Implementation plan ready.
