# Overview



# Constitution

## Explanations

* This is the always true part
* This is where you put things like:
  * “Don’t break existing behavior” / backwards compatibility expectations
  * security constraints (no logging secrets, approved crypto libs only, etc.)
  * testing requirements (unit tests required; integration tests for critical paths)
  * coding standards (formatting, lint rules, typing)
  * repo conventions (folder layout, naming, branching strategy)
  * “No new dependencies without approval”
  * “Prefer minimal diffs; refactor only when necessary to implement the task”
  * Create a stable home for spec-kit artifacts, so they live with the code and evolve via PRs

* You can also define some .md files like
  * architecture.md
  * stack.md
  * testing.md
* refer to it in the constitution in each feature like that


```
All specs/plans/tasks/implementation MUST conform to docs/architecture.md and docs/stack.md
```

or 

```
Plans must start by restating relevant constraints from docs/architecture.md (only the relevant ones), not redefining the architecture
```

## Prompt

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

* if folder is connected to git, it will create a new branch
* creates a specs/001-credit-limit-decision folder
* creates a spec.md where the spec are written down
* creates a requirements.md that indicates 
  * if there are something missing in the spec.md or unclear
    * some tags with [NEEDS CLARIFICATION] could be added to the spec.md  

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

# Clarify

* identifies unclear parts in the spec.md
* Optional to run

# Speckit Plan

* generates a 
  * research.md
    * capture the targeted research and technical decisions the agent (and your team) needs in order to turn the spec into reliable tasks and code
  * data-model.md
    * define all the data model (dynamoDB)
    * mappings class in Python
    * relationship between entities 
  * plan.md
    * how we apply each constitution principle technically
    * map each acceptance criteria to a specific unit test
    * takes research.md and summarize technical choices
  * quickstart.md
    * audience are developers that emboard the project. It contains basic commands to setup, execute the tests, describe project structure, etc... 
  * api-contract.yaml : OpenAPI specification

```
/speckit.plan
```

Generate an implementation plan from the spec for a small but real AWS Lambda application.

ARCHITECTURE
- API Gateway HTTP API -> Lambda (Python 3.13)
- DynamoDB audit table: CreditDecisionAudit
- Internal data sources are stubs for demo (in-memory dicts) with clear interfaces so they can be swapped later.

REPO STRUCTURE (required)
- src/credit_decision/
  - handler.py (lambda entrypoint)
  - models.py (dataclasses for request/response)
  - decision_engine.py (pure function rules)
  - data_sources.py (stubbed risk + past-due lookups)
  - audit_repo.py (DynamoDB writer)
  - errors.py (error types + mapping)
- tests/
  - test_decision_engine.py (rule matrix)
  - test_handler_validation.py
- template.yaml (SAM)
- README.md (local + deploy instructions)
- pyproject.toml (pytest config minimal)

PLAN OUTPUT
- Provide a step-by-step plan with sequence, rationale, and dependencies.
- Include a mapping from each acceptance criterion to tests and modules.
- Include the minimal IAM permissions needed for DynamoDB PutItem.


# Tasks

* Each task
  * goal
  * files to edit
  * Success critieria

```
/speckit.tasks
```

Create an engineering task list from the plan.

TASK STYLE
- Granularity: each task should be 1–4 hours.
- Each task must include:
  - Goal
  - Implementation notes
  - Files to create/modify
  - Acceptance criteria / Definition of Done
  - Test expectations

REQUIRED TASKS (must appear)
1) Define models + enums (decision, reason codes) and shared constants
2) Implement decision_engine pure function + full rule matrix unit tests
3) Implement Lambda handler: request parsing, validation, error responses + handler tests
4) Implement stub data_sources interfaces and demo data
5) Implement DynamoDB audit_repo + write audit for success + failures
6) Add SAM template: Lambda, DynamoDB table, env vars, IAM permissions
7) Add README with local run (sam local) + curl examples + deployment steps

OUTPUT FORMAT
- Numbered list of tasks
- Each task includes “Done when …” checkboxes


# Spec-kit core logic

```
spec.md
   ↓
research.md
   ↓
plan.md
   ↓
tasks.md
```

* try to fix the issue in the most top level file or it will create inconsistencies

# Analyze

* Cross-artifact consistency & coverage analysis
* basically it checks that the tasks don't violate any rule that was given before. It's a quality check gate.
* It can make recommendations for improvements
* If you want to accept recommendations, tell him to integrate them in the spec, plan and tasks to use a recursive loop.
* Optional to run


# Spec-kit implement

* if something is not right in the result of implement step, you can iterate to ask him to refine
* at the very least be sure, once it's done, ask him to reintegrate all the learning and experience pieces to the spec.md

```
/speckit.implement
```

Implement the application exactly as specified and planned.

IMPLEMENTATION CONSTRAINTS
- Python 3.13
- Minimal dependencies: stdlib + boto3 only
- Use dataclasses for models; keep code simple and readable.
- Decision logic must remain pure and fully unit-tested.
- requestedLimit validation:
  - required, numeric, > 0
  - must be whole units (reject decimals) -> return 400 VALIDATION_ERROR
- Return JSON responses with appropriate HTTP codes:
  - 200 for success
  - 400 for validation errors
  - 500 for unexpected errors
- Always attempt to write an audit record (success and failures).
- Include decisionId and timestamp generation in handler.
- principalId extraction from requestContext.authorizer.principalId (fallback to "anonymous").

FILES TO GENERATE (required)
- src/credit_decision/handler.py
- src/credit_decision/models.py
- src/credit_decision/decision_engine.py
- src/credit_decision/data_sources.py
- src/credit_decision/audit_repo.py
- src/credit_decision/errors.py
- tests/test_decision_engine.py
- tests/test_handler_validation.py
- template.yaml (SAM)
- pyproject.toml (pytest config)
- README.md

QUALITY BAR
- Tests must pass locally.
- README must show:
  - sam build / sam local start-api
  - example curl requests for APPROVE, CAP, REFER, DECLINE, VALIDATION_ERROR
  - notes on how to replace stubs with real services later
