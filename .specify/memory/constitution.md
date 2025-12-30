<!--
SYNC IMPACT REPORT
==================
Version Change: [initial template] → 1.0.0
Modified Principles: N/A (initial constitution)
Added Sections:
  - Core Principles: 7 principles established
  - Technology Stack Constraints (fixed stack)
  - Compliance & Auditability Requirements
  - Governance rules
Templates Requiring Updates:
  ✅ plan-template.md - constitution check section compatible
  ✅ spec-template.md - acceptance criteria align with explainability principle
  ✅ tasks-template.md - test-driven approach consistent with principle III
Follow-up TODOs: None
==================
-->

# Credit Limit Decision Service Constitution

## Core Principles

### I. Deterministic Decision Logic (NON-NEGOTIABLE)

**MUST**: Decision logic is a pure function with zero side effects. Same inputs MUST produce the same decision output every time (timestamp and decisionId may differ, but decision outcome, reason codes, and explanations MUST be identical).

**MUST NOT**: Make AWS SDK calls (boto3) or any I/O operations inside the rule engine.

**Rationale**: Determinism enables testing, debugging, and regulatory audit. Non-deterministic underwriting decisions create legal and compliance risk.

### II. Explainability & Auditability (NON-NEGOTIABLE)

**MUST**: Every credit limit decision returns:
- Decision outcome (approved/declined/referred)
- Reason codes (machine-readable identifiers)
- Human-readable explanations for underwriters

**MUST**: All decisions stored in DynamoDB audit table with full request payload and decision trace.

**MUST NOT**: Store PII beyond identifiers (buyerId, policyId). No names, addresses, or financial details beyond aggregate risk indicators.

**Rationale**: Trade credit insurance is a regulated space. Decisions must be explainable to regulators, underwriters, and clients. Privacy regulations prohibit unnecessary PII storage.

### III. Type Safety & Data Contracts

**MUST**: Use Python type hints throughout all modules.

**MUST**: Use dataclasses (or Pydantic if dependencies expanded) for all request/response models and domain entities.

**MUST NOT**: Pass untyped dictionaries between functions or modules.

**Rationale**: Type hints catch errors at development time, improve IDE support, enable better refactoring, and serve as inline documentation for credit risk analysts reviewing logic.

### IV. Minimal Dependencies & Simplicity

**MUST**: Keep dependencies minimal. Approved: stdlib, boto3 (AWS SDK), pytest (dev).

**MUST NOT**: Add heavy frameworks (Django, Flask, FastAPI) or unnecessary libraries without explicit constitution amendment.

**Rationale**: Lambda cold start performance, security surface reduction, and long-term maintainability for a small underwriting team.

### V. Observability & Correlation

**MUST**: Emit structured logs (JSON-compatible format) for all decision requests.

**MUST**: Include `decisionId` in every log entry to enable correlation across Lambda invocations, DynamoDB writes, and downstream systems.

**MUST**: Log decision inputs, outputs, and any rule branch taken (for audit trail).

**Rationale**: When an underwriter questions a decision, engineering must trace the full decision path in CloudWatch. DecisionId is the correlation key.

### VI. Error Handling & API Contracts

**MUST**: API Gateway responses are JSON with `Content-Type: application/json`.

**MUST**: Success responses follow schema: `{ "decisionId": "...", "decision": "...", "reasonCodes": [...], "explanation": "..." }`

**MUST**: Error responses follow schema: `{ "errorCode": "...", "message": "..." }` with appropriate HTTP status (400 client error, 500 server error, 422 validation failure).

**MUST NOT**: Return HTML error pages or stack traces to clients.

**Rationale**: Downstream systems (underwriter UI, batch processors) depend on stable JSON contracts. Error codes enable systematic error handling.

### VII. Code Quality & Maintainability

**MUST**: Format code with `black` (or black-compatible formatter).

**MUST**: Organize code into clear module boundaries: `decision_engine/`, `models/`, `api_gateway_handler/`, `audit/`.

**MUST**: Use readable, domain-specific names: prefer `CreditLimitRequest` over `CLR`, `assess_buyer_risk()` over `abr()`.

**Rationale**: Credit risk logic is complex enough. Code must be readable by underwriters (who may review business rules) and junior engineers (small team, knowledge transfer critical).

## Technology Stack Constraints

**FIXED STACK** (changes require constitution amendment):

- **Runtime**: AWS Lambda, Python 3.13
- **API Gateway**: HTTP API with Lambda proxy integration
- **Persistence**: DynamoDB (audit records only; decision logic remains stateless)
- **Infrastructure as Code**: AWS SAM (`template.yaml`)
- **Testing**: pytest (unit + integration tests)
- **Deployment**: AWS SAM CLI (`sam build`, `sam deploy`)

**Rationale**: Stack selected for regulatory compliance (AWS GovCloud compatible), serverless cost model (sporadic usage), and team expertise (Python).

## Compliance & Auditability Requirements

**MUST**: Audit table schema includes:
- decisionId (partition key)
- timestamp (ISO 8601 UTC)
- buyerId, policyId (identifiers only)
- requestPayload (full input for replay)
- decisionOutcome, reasonCodes, explanation
- lambdaRequestId (for CloudWatch correlation)

**MUST**: Implement DynamoDB TTL for audit records (retention TBD, but support TTL attribute).

**MUST NOT**: Log or store sensitive PII (customer names, contact details, financial statements) in audit table.

## Governance

**Authority**: This constitution supersedes all coding preferences, team conventions, and prior practices. Non-negotiable principles (marked NON-NEGOTIABLE above) cannot be bypassed.

**Amendment Process**:
1. Proposal documented with business justification
2. Team review (engineering + risk management stakeholders)
3. Version bump per semantic versioning: MAJOR (principle removal/breaking change), MINOR (new principle added), PATCH (clarification/wording fix)
4. Migration plan for affected code (if applicable)

**Compliance Verification**:
- All PRs must pass constitution compliance check
- Tests must validate determinism (same input → same output)
- Code reviews verify type hints, pure function boundaries, structured logging

**Versioning**: Use semantic versioning for constitution itself. Breaking changes to governance require MAJOR version bump.

**Version**: 1.0.0 | **Ratified**: 2025-12-30 | **Last Amended**: 2025-12-30
