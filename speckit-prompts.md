# Constitution

```
/speckit.constitution
```

You are Spec Kit for a credit risk / trade credit insurance team. Establish the project constitution (non-negotiable rules) for this repo.

GOALS
- Build a deterministic “Credit Limit Decision” service for underwriting support.
- Every decision must be explainable (reason codes + human explanations) and auditable.

TECH STACK (fixed)
- AWS Lambda runtime: Python 3.13
- Front door: API Gateway HTTP API (Lambda proxy integration)
- Persistence: DynamoDB table for audit records
- IaC: AWS SAM (template.yaml)
- Tests: pytest

ENGINEERING RULES
- Decision logic must be a pure function (no AWS calls inside the rule engine).
- Use Python type hints throughout; prefer dataclasses for request/response models.
- No heavy frameworks; keep dependencies minimal (stdlib + boto3 only).
- API responses must be JSON with content-type application/json.
- Errors must return JSON: { "errorCode": "...", "message": "..." } with appropriate HTTP status.
- Observability: structured logs (JSON-ish) and include decisionId in logs for correlation.
- Security/Privacy: audit must not store any PII beyond identifiers (buyerId, policyId) and request payload.
- Determinism: same inputs => same decision (decisionId and timestamp can differ).
- Code style: black-compatible formatting, clear module boundaries, readable names.

DELIVERABLES
- A runnable SAM application with Lambda + DynamoDB + tests + README.
Output the constitution as a concise, structured document.

# Specify 

```
/speckit.specify
```

Create the full specification for an MVP service: “Credit Limit Decision”.

DOMAIN CONTEXT
We are building a feature for a credit risk / trade credit insurance application. Underwriters need a fast, consistent decision suggestion for requested credit limits, with explainability and auditability.

API CONTRACT
Endpoint: POST /credit-decisions

Request JSON (all required unless noted):
- buyerId: string
- policyId: string
- requestedLimit: number (must be > 0)
- currency: string (ISO 4217)
- requestId: string (optional idempotency key; MVP stores it but does not dedupe)

Response JSON (200):
- decisionId: string (uuid)
- decision: "APPROVE" | "REFER" | "DECLINE"
- approvedLimit: number (0 for REFER/DECLINE)
- currency: string
- reasonCodes: string[]
- explanations: string[]
- timestamp: string (ISO-8601 UTC)

Error response JSON (4xx/5xx):
- errorCode: string
- message: string

MVP BUSINESS INPUTS (from internal sources)
- riskGrade: "A" | "B" | "C" | "D" | "E" | unknown
- pastDueOver60: boolean | unknown

RULES (MVP)
Max limits by grade:
- A: 1,000,000
- B: 500,000

Decision rules:
1) If riskGrade in {D, E} -> DECLINE, approvedLimit=0, reasonCodes includes "RISK_GRADE_HIGH"
2) If riskGrade == C -> REFER, approvedLimit=0, reasonCodes includes "RISK_GRADE_MEDIUM"
3) If riskGrade in {A, B} AND pastDueOver60 == true -> REFER, approvedLimit=0, reasonCodes includes "PAST_DUE_OVER_60"
4) If riskGrade == A AND pastDueOver60 == false -> APPROVE up to 1,000,000 (cap if needed). If capped add reason "LIMIT_CAPPED_BY_GRADE"
5) If riskGrade == B AND pastDueOver60 == false -> APPROVE up to 500,000 (cap if needed). If capped add reason "LIMIT_CAPPED_BY_GRADE"
6) If riskGrade is missing/unknown -> REFER, approvedLimit=0, reasonCodes includes "RISK_DATA_MISSING"
7) If pastDueOver60 is missing/unknown -> REFER, approvedLimit=0, reasonCodes includes "PAST_DUE_DATA_MISSING"

EXPLANATIONS
- Provide a short human-readable explanation for each reason code returned.
- If multiple reason codes, provide explanations in the same order.

EDGE DECISIONS (explicit)
- Currency conversion is OUT OF SCOPE for MVP. We validate that currency is a 3-letter string and echo it back.
- approvedLimit is numeric and returned as 0 for REFER/DECLINE.
- Rounding: keep requestedLimit/approvedLimit as whole currency units in responses (no decimals). Reject decimals in requestedLimit (validation error).
- Deterministic results: rule ordering is fixed as above.

AUDIT REQUIREMENTS
For every request (including validation errors), write one immutable audit record to DynamoDB table "CreditDecisionAudit".
- Partition key (string): pk = "DECISION#{decisionId}"
- Required attributes:
  - decisionId, timestamp, principalId
  - buyerId, policyId, requestedLimit, currency, requestId (if provided)
  - derivedInputs: riskGrade, pastDueOver60 (if known)
  - decision, approvedLimit, reasonCodes (if produced)
  - status: "OK" | "FAILED"
  - errorCode (if failed)
- principalId comes from API Gateway authorizer in requestContext; if absent use "anonymous".
- Do not store invoice details or personal data beyond ids.

NON-FUNCTIONAL REQUIREMENTS
- p95 < 200ms excluding cold start (best effort; mention in README)
- Structured logging with decisionId in all logs
- Unit tests for decision matrix + handler validation tests
- SAM template to deploy Lambda + DynamoDB + minimal IAM permissions

Include: glossary, request/response examples, and acceptance criteria (Given/When/Then style).

