# Feature Specification: Credit Limit Decision Service (MVP)

**Feature Branch**: `001-credit-limit-decision`  
**Created**: 2025-12-30  
**Status**: Draft  
**Input**: User description: "Create the full specification for an MVP service: Credit Limit Decision"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Credit Approval for Low-Risk Buyers (Priority: P1)

An underwriter submits a credit limit request for a Grade A or B buyer with no significant past-due balances. The system instantly returns an APPROVE decision with the approved limit (up to the grade's maximum) and clear explanation, enabling the underwriter to proceed immediately without manual review.

**Why this priority**: This is the core value proposition—automating the most common, low-risk decisions to free underwriters from routine approvals. Represents 60-70% of expected volume.

**Independent Test**: Can be fully tested by submitting a credit decision request with `riskGrade: "A"`, `pastDueOver60: false`, and `requestedLimit: 500000`. System returns `decision: "APPROVE"`, `approvedLimit: 500000`, and reason codes explaining approval.

**Acceptance Scenarios**:

1. **Given** a buyer with riskGrade "A" and pastDueOver60 false, **When** underwriter requests 800,000 credit limit in USD, **Then** system returns APPROVE with approvedLimit 800,000, no capping reason code
2. **Given** a buyer with riskGrade "A" and pastDueOver60 false, **When** underwriter requests 1,500,000 credit limit in EUR, **Then** system returns APPROVE with approvedLimit 1,000,000 (capped), includes "LIMIT_CAPPED_BY_GRADE" reason code
3. **Given** a buyer with riskGrade "B" and pastDueOver60 false, **When** underwriter requests 400,000 credit limit in GBP, **Then** system returns APPROVE with approvedLimit 400,000
4. **Given** a buyer with riskGrade "B" and pastDueOver60 false, **When** underwriter requests 700,000 credit limit, **Then** system returns APPROVE with approvedLimit 500,000 (capped), includes "LIMIT_CAPPED_BY_GRADE" reason code

---

### User Story 2 - Automatic Referral for Medium-Risk or Data-Incomplete Cases (Priority: P2)

An underwriter submits a credit limit request for a buyer with moderate risk signals (Grade C, missing data, or past-due issues). The system returns a REFER decision with clear reason codes, prompting the underwriter to manually review the case with additional context.

**Why this priority**: Ensures risky or ambiguous cases get human oversight while still providing instant feedback to the underwriter. Critical for risk management.

**Independent Test**: Can be fully tested by submitting requests with `riskGrade: "C"`, missing riskGrade, or `pastDueOver60: true`. System returns `decision: "REFER"`, `approvedLimit: 0`, and appropriate reason codes.

**Acceptance Scenarios**:

1. **Given** a buyer with riskGrade "C", **When** underwriter requests any credit limit, **Then** system returns REFER with approvedLimit 0 and "RISK_GRADE_MEDIUM" reason code
2. **Given** a buyer with riskGrade "A" and pastDueOver60 true, **When** underwriter requests credit limit, **Then** system returns REFER with approvedLimit 0 and "PAST_DUE_OVER_60" reason code
3. **Given** a buyer with missing riskGrade, **When** underwriter requests credit limit, **Then** system returns REFER with approvedLimit 0 and "RISK_DATA_MISSING" reason code
4. **Given** a buyer with riskGrade "B" and missing pastDueOver60 data, **When** underwriter requests credit limit, **Then** system returns REFER with approvedLimit 0 and "PAST_DUE_DATA_MISSING" reason code

---

### User Story 3 - Automatic Decline for High-Risk Buyers (Priority: P3)

An underwriter submits a credit limit request for a high-risk buyer (Grade D or E). The system instantly returns a DECLINE decision with explanation, saving underwriter time by eliminating the need to review obviously unacceptable risks.

**Why this priority**: While important for workflow efficiency, high-risk declines are less frequent than approvals and referrals. Still provides value by automating clear-cut rejections.

**Independent Test**: Can be fully tested by submitting requests with `riskGrade: "D"` or `riskGrade: "E"`. System returns `decision: "DECLINE"`, `approvedLimit: 0`, and "RISK_GRADE_HIGH" reason code.

**Acceptance Scenarios**:

1. **Given** a buyer with riskGrade "D", **When** underwriter requests any credit limit, **Then** system returns DECLINE with approvedLimit 0 and "RISK_GRADE_HIGH" reason code
2. **Given** a buyer with riskGrade "E", **When** underwriter requests any credit limit, **Then** system returns DECLINE with approvedLimit 0 and "RISK_GRADE_HIGH" reason code

---

### User Story 4 - Complete Audit Trail for Compliance (Priority: P1)

For every credit decision request (successful or failed), the system writes an immutable audit record to the audit table with all inputs, outputs, decision trace, and requestor identity. Compliance team can retrieve full decision history for regulatory review.

**Why this priority**: Non-negotiable for regulatory compliance in trade credit insurance. Without audit, service cannot be used in production.

**Independent Test**: Can be fully tested by submitting a decision request and verifying that the DynamoDB audit table contains a record with decisionId, all request inputs, decision outputs, timestamp, and principalId.

**Acceptance Scenarios**:

1. **Given** any valid credit decision request, **When** system processes request, **Then** audit record created in DynamoDB with decisionId, buyerId, policyId, requestedLimit, currency, riskGrade, pastDueOver60, decision, approvedLimit, reasonCodes, timestamp, principalId, and status "OK"
2. **Given** an invalid request (validation failure), **When** system rejects request, **Then** audit record created with decisionId, partial inputs (if available), status "FAILED", and errorCode
3. **Given** a request with API Gateway authorizer context, **When** system processes request, **Then** principalId extracted from requestContext and stored in audit record
4. **Given** a request without authorizer context, **When** system processes request, **Then** principalId set to "anonymous" in audit record

---

### Edge Cases

- **What happens when requestedLimit has decimal values?** System rejects with validation error `{ "errorCode": "INVALID_REQUEST", "message": "requestedLimit must be a whole number" }` with HTTP 400. No audit record stores the decision outcome, but a FAILED audit record is written.
- **What happens when currency is not a 3-letter ISO 4217 code?** System validates currency is exactly 3 uppercase letters (basic format check), rejects otherwise with validation error. MVP does not validate against full ISO 4217 list.
- **What happens when buyerId or policyId is missing?** System rejects with validation error `{ "errorCode": "MISSING_REQUIRED_FIELD", "message": "buyerId is required" }` with HTTP 400.
- **What happens when requestedLimit is 0 or negative?** System rejects with validation error `{ "errorCode": "INVALID_REQUEST", "message": "requestedLimit must be greater than 0" }` with HTTP 400.
- **What happens when requestId is provided?** System accepts it and stores it in the audit record. MVP does not enforce idempotency (duplicate requestId can create multiple decisions).
- **What happens if DynamoDB write fails?** Decision logic completes successfully and returns response to user, but system logs critical error with decisionId for manual recovery. HTTP 200 returned to user (eventual consistency model for audit).
- **What happens if riskGrade is an unexpected value (not A-E or missing)?** System treats it as "unknown" and applies rule 6 (REFER with "RISK_DATA_MISSING").
- **What happens when multiple reason codes apply?** System returns all applicable reason codes in priority order (following rule evaluation sequence 1-7) with matching explanations in same order.
- **How does system handle currency conversion?** Out of scope for MVP. Currency is validated as 3-letter string and echoed back unchanged. Approved limits are in the same currency as requested.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept POST requests to `/credit-decisions` endpoint with JSON body containing buyerId, policyId, requestedLimit, currency, and optional requestId
- **FR-002**: System MUST validate that buyerId and policyId are non-empty strings, requestedLimit is a positive whole number, and currency is a 3-letter string
- **FR-003**: System MUST return HTTP 400 with JSON error response `{ "errorCode": "...", "message": "..." }` for validation failures
- **FR-004**: System MUST retrieve riskGrade and pastDueOver60 data from internal sources based on buyerId and policyId
- **FR-005**: System MUST evaluate decision rules 1-7 in fixed order (deterministic evaluation) and return decision outcome (APPROVE, REFER, DECLINE) with approvedLimit, reasonCodes, and explanations
- **FR-006**: System MUST generate a unique decisionId (UUID v4 format) for each request
- **FR-007**: System MUST return HTTP 200 with JSON response containing decisionId, decision, approvedLimit, currency, reasonCodes, explanations, and timestamp (ISO 8601 UTC) for successful requests
- **FR-008**: System MUST cap approvedLimit at riskGrade maximum (A: 1,000,000, B: 500,000) and include "LIMIT_CAPPED_BY_GRADE" reason code when requestedLimit exceeds maximum
- **FR-009**: System MUST return approvedLimit as 0 for REFER and DECLINE decisions
- **FR-010**: System MUST provide human-readable explanations for each reason code in the same order as reasonCodes array
- **FR-011**: System MUST write an immutable audit record to DynamoDB table "CreditDecisionAudit" for every request with partition key `DECISION#{decisionId}`
- **FR-012**: Audit record MUST include decisionId, timestamp, principalId, buyerId, policyId, requestedLimit, currency, requestId (if provided), riskGrade and pastDueOver60 (if known), decision, approvedLimit, reasonCodes, status ("OK" or "FAILED"), and errorCode (if failed)
- **FR-013**: System MUST extract principalId from API Gateway authorizer in requestContext; if absent, use "anonymous"
- **FR-014**: System MUST NOT store personally identifiable information (PII) beyond buyerId and policyId identifiers in audit records
- **FR-015**: System MUST emit structured logs (JSON format) with decisionId included in all log entries for correlation
- **FR-016**: System MUST return HTTP 500 with JSON error response for internal errors
- **FR-017**: System MUST ensure decision logic is deterministic (same inputs produce same decision outcome, reasonCodes, and explanations; only decisionId and timestamp may differ)
- **FR-018**: Decision logic MUST be a pure function with no AWS SDK calls or I/O operations inside the rule engine

### Key Entities *(include if feature involves data)*

- **CreditDecisionRequest**: Represents an underwriter's request for a credit limit decision. Attributes: buyerId (identifies the buyer entity), policyId (identifies the insurance policy), requestedLimit (amount requested in whole currency units), currency (ISO 4217 code), requestId (optional idempotency key for request tracking).

- **CreditDecisionResponse**: Represents the system's decision outcome. Attributes: decisionId (unique identifier for this decision), decision (APPROVE/REFER/DECLINE), approvedLimit (amount approved in whole currency units, 0 for REFER/DECLINE), currency (echoed from request), reasonCodes (machine-readable decision rationale), explanations (human-readable decision rationale), timestamp (when decision was made).

- **BuyerRiskProfile**: Represents internal risk assessment data for a buyer. Attributes: riskGrade (A/B/C/D/E or unknown), pastDueOver60 (boolean flag for overdue payments beyond 60 days or unknown). Not persisted by this service; retrieved from internal sources.

- **CreditDecisionAudit**: Immutable audit record for compliance. Attributes: decisionId (partition key), timestamp, principalId (who requested), buyerId, policyId, requestedLimit, currency, requestId, derivedInputs (riskGrade, pastDueOver60), decision, approvedLimit, reasonCodes, status (OK/FAILED), errorCode. Persisted in DynamoDB.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Underwriters can submit a credit decision request and receive a deterministic response (APPROVE/REFER/DECLINE with reasons) in under 200ms (p95, excluding cold start)
- **SC-002**: System correctly evaluates all 7 decision rules in fixed order, producing identical outcomes for identical inputs
- **SC-003**: 100% of credit decision requests (successful and failed) result in an audit record written to DynamoDB
- **SC-004**: System validates 100% of invalid requests (missing fields, negative limits, decimal limits, invalid currency format) and returns appropriate HTTP 400 errors without executing decision logic
- **SC-005**: System handles concurrent requests without data corruption or non-deterministic behavior
- **SC-006**: All decision responses include at least one reason code with matching human-readable explanation
- **SC-007**: Service can be deployed via AWS SAM template with Lambda function, DynamoDB table, API Gateway integration, and minimal IAM permissions in a single `sam deploy` operation
- **SC-008**: Every API response has `Content-Type: application/json` header
- **SC-009**: Every log entry includes decisionId for end-to-end request correlation in CloudWatch

## Assumptions *(optional - include if relevant)*

- **A-001**: Internal risk data source (riskGrade, pastDueOver60) is accessible synchronously during Lambda execution with <50ms latency
- **A-002**: Internal risk data source returns "unknown" or null for missing data, not errors
- **A-003**: API Gateway authorizer is configured externally and provides principalId in requestContext; this service does not implement authentication
- **A-004**: Currency values are provided by upstream systems and are already validated as ISO 4217 codes; MVP performs only basic 3-letter format check
- **A-005**: DynamoDB table has sufficient write capacity for expected request volume (<100 requests/sec)
- **A-006**: Idempotency enforcement is deferred to post-MVP; requestId is stored but not used for deduplication in MVP
- **A-007**: Request payload size is <10KB (well within API Gateway and Lambda limits)

## Out of Scope *(optional - include if relevant)*

- **OS-001**: Currency conversion or multi-currency limit aggregation
- **OS-002**: Idempotency enforcement (requestId deduplication)
- **OS-003**: Real-time integration with external credit bureaus or risk data providers
- **OS-004**: Batch processing or bulk decision requests
- **OS-005**: Decision override or manual adjustment workflows
- **OS-006**: Audit record querying API (read access to DynamoDB)
- **OS-007**: Historical decision analytics or reporting
- **OS-008**: Machine learning or dynamic risk scoring (rules are static in MVP)
- **OS-009**: Versioning of decision logic or A/B testing different rule sets
- **OS-010**: Full ISO 4217 currency code validation (only 3-letter format check)

## Glossary *(optional - include if relevant)*

- **Buyer**: A business entity that is purchasing goods on credit from a policyholder (seller). The subject of the credit risk assessment.
- **Policy**: A trade credit insurance policy held by a seller to protect against buyer default.
- **Risk Grade**: An internal risk classification (A=lowest risk, E=highest risk) assigned to a buyer based on credit analysis.
- **Past Due Over 60**: A boolean flag indicating whether the buyer has outstanding invoices overdue by more than 60 days.
- **Credit Limit**: The maximum amount of trade credit the insurance company will cover for a specific buyer under a policy.
- **Approved Limit**: The credit limit amount the system determines should be granted (may be less than requested if capped by risk grade).
- **Reason Code**: A machine-readable identifier explaining why a decision was made (e.g., "RISK_GRADE_HIGH", "LIMIT_CAPPED_BY_GRADE").
- **Explanation**: A human-readable text description of a reason code, intended for underwriter review.
- **Decision Outcome**: One of three values: APPROVE (grant credit), REFER (manual review required), DECLINE (reject credit request).
- **Underwriter**: A credit insurance professional who reviews and approves/declines credit applications. User of this service.
- **Principal**: The authenticated user or system making the API request (stored as principalId in audit).
- **Idempotency Key**: An optional requestId that can be used to identify duplicate requests (stored but not enforced in MVP).
- **Deterministic**: Property that guarantees the same inputs always produce the same outputs (critical for testing and audit).

## Request/Response Examples *(optional - include if relevant)*

### Example 1: Successful Approval (Grade A, Under Limit)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-12345",
  "policyId": "POL-67890",
  "requestedLimit": 750000,
  "currency": "USD",
  "requestId": "REQ-2025-001"
}
```

**Internal Data Retrieved**:
- riskGrade: "A"
- pastDueOver60: false

**Response** (HTTP 200):
```json
{
  "decisionId": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "APPROVE",
  "approvedLimit": 750000,
  "currency": "USD",
  "reasonCodes": [],
  "explanations": [],
  "timestamp": "2025-12-30T10:30:00.000Z"
}
```

---

### Example 2: Approval with Capping (Grade B, Over Limit)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-54321",
  "policyId": "POL-11111",
  "requestedLimit": 800000,
  "currency": "EUR"
}
```

**Internal Data Retrieved**:
- riskGrade: "B"
- pastDueOver60: false

**Response** (HTTP 200):
```json
{
  "decisionId": "660e8400-e29b-41d4-a716-446655440001",
  "decision": "APPROVE",
  "approvedLimit": 500000,
  "currency": "EUR",
  "reasonCodes": ["LIMIT_CAPPED_BY_GRADE"],
  "explanations": ["Requested limit exceeds maximum allowed for risk grade B (500,000)"],
  "timestamp": "2025-12-30T10:31:00.000Z"
}
```

---

### Example 3: Referral (Grade C)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-99999",
  "policyId": "POL-22222",
  "requestedLimit": 300000,
  "currency": "GBP"
}
```

**Internal Data Retrieved**:
- riskGrade: "C"
- pastDueOver60: false

**Response** (HTTP 200):
```json
{
  "decisionId": "770e8400-e29b-41d4-a716-446655440002",
  "decision": "REFER",
  "approvedLimit": 0,
  "currency": "GBP",
  "reasonCodes": ["RISK_GRADE_MEDIUM"],
  "explanations": ["Buyer risk grade is C (medium risk); manual underwriter review required"],
  "timestamp": "2025-12-30T10:32:00.000Z"
}
```

---

### Example 4: Referral (Missing Risk Data)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-00000",
  "policyId": "POL-33333",
  "requestedLimit": 100000,
  "currency": "USD"
}
```

**Internal Data Retrieved**:
- riskGrade: unknown
- pastDueOver60: false

**Response** (HTTP 200):
```json
{
  "decisionId": "880e8400-e29b-41d4-a716-446655440003",
  "decision": "REFER",
  "approvedLimit": 0,
  "currency": "USD",
  "reasonCodes": ["RISK_DATA_MISSING"],
  "explanations": ["Buyer risk grade data is unavailable; cannot make automated decision"],
  "timestamp": "2025-12-30T10:33:00.000Z"
}
```

---

### Example 5: Referral (Past Due Over 60)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-77777",
  "policyId": "POL-44444",
  "requestedLimit": 200000,
  "currency": "CAD"
}
```

**Internal Data Retrieved**:
- riskGrade: "A"
- pastDueOver60: true

**Response** (HTTP 200):
```json
{
  "decisionId": "990e8400-e29b-41d4-a716-446655440004",
  "decision": "REFER",
  "approvedLimit": 0,
  "currency": "CAD",
  "reasonCodes": ["PAST_DUE_OVER_60"],
  "explanations": ["Buyer has outstanding invoices overdue by more than 60 days; manual review required"],
  "timestamp": "2025-12-30T10:34:00.000Z"
}
```

---

### Example 6: Decline (Grade D)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-88888",
  "policyId": "POL-55555",
  "requestedLimit": 50000,
  "currency": "AUD"
}
```

**Internal Data Retrieved**:
- riskGrade: "D"
- pastDueOver60: true

**Response** (HTTP 200):
```json
{
  "decisionId": "aa0e8400-e29b-41d4-a716-446655440005",
  "decision": "DECLINE",
  "approvedLimit": 0,
  "currency": "AUD",
  "reasonCodes": ["RISK_GRADE_HIGH"],
  "explanations": ["Buyer risk grade is D or E (high risk); credit cannot be approved"],
  "timestamp": "2025-12-30T10:35:00.000Z"
}
```

---

### Example 7: Validation Error (Missing Required Field)

**Request**:
```json
POST /credit-decisions
{
  "policyId": "POL-66666",
  "requestedLimit": 100000,
  "currency": "USD"
}
```

**Response** (HTTP 400):
```json
{
  "errorCode": "MISSING_REQUIRED_FIELD",
  "message": "buyerId is required"
}
```

---

### Example 8: Validation Error (Invalid Requested Limit)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-11111",
  "policyId": "POL-77777",
  "requestedLimit": 100000.50,
  "currency": "USD"
}
```

**Response** (HTTP 400):
```json
{
  "errorCode": "INVALID_REQUEST",
  "message": "requestedLimit must be a whole number"
}
```

---

### Example 9: Validation Error (Negative Requested Limit)

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-22222",
  "policyId": "POL-88888",
  "requestedLimit": -50000,
  "currency": "EUR"
}
```

**Response** (HTTP 400):
```json
{
  "errorCode": "INVALID_REQUEST",
  "message": "requestedLimit must be greater than 0"
}
```

---

### Example 10: Internal Server Error

**Request**:
```json
POST /credit-decisions
{
  "buyerId": "BYR-33333",
  "policyId": "POL-99999",
  "requestedLimit": 500000,
  "currency": "JPY"
}
```

**Response** (HTTP 500):
```json
{
  "errorCode": "INTERNAL_ERROR",
  "message": "An unexpected error occurred while processing your request"
}
```

## Acceptance Criteria Summary *(mandatory)*

**Decision Logic**:

1. **Given** a buyer with riskGrade "D" or "E", **When** any credit limit requested, **Then** system returns DECLINE with approvedLimit 0 and "RISK_GRADE_HIGH" reason code
2. **Given** a buyer with riskGrade "C", **When** any credit limit requested, **Then** system returns REFER with approvedLimit 0 and "RISK_GRADE_MEDIUM" reason code
3. **Given** a buyer with riskGrade "A" or "B" and pastDueOver60 true, **When** any credit limit requested, **Then** system returns REFER with approvedLimit 0 and "PAST_DUE_OVER_60" reason code
4. **Given** a buyer with riskGrade "A" and pastDueOver60 false, **When** requestedLimit ≤ 1,000,000, **Then** system returns APPROVE with approvedLimit = requestedLimit
5. **Given** a buyer with riskGrade "A" and pastDueOver60 false, **When** requestedLimit > 1,000,000, **Then** system returns APPROVE with approvedLimit = 1,000,000 and "LIMIT_CAPPED_BY_GRADE" reason code
6. **Given** a buyer with riskGrade "B" and pastDueOver60 false, **When** requestedLimit ≤ 500,000, **Then** system returns APPROVE with approvedLimit = requestedLimit
7. **Given** a buyer with riskGrade "B" and pastDueOver60 false, **When** requestedLimit > 500,000, **Then** system returns APPROVE with approvedLimit = 500,000 and "LIMIT_CAPPED_BY_GRADE" reason code
8. **Given** a buyer with missing/unknown riskGrade, **When** any credit limit requested, **Then** system returns REFER with approvedLimit 0 and "RISK_DATA_MISSING" reason code
9. **Given** a buyer with missing/unknown pastDueOver60, **When** any credit limit requested, **Then** system returns REFER with approvedLimit 0 and "PAST_DUE_DATA_MISSING" reason code

**Validation**:

10. **Given** a request with missing buyerId, **When** request submitted, **Then** system returns HTTP 400 with "MISSING_REQUIRED_FIELD" error code
11. **Given** a request with missing policyId, **When** request submitted, **Then** system returns HTTP 400 with "MISSING_REQUIRED_FIELD" error code
12. **Given** a request with requestedLimit ≤ 0, **When** request submitted, **Then** system returns HTTP 400 with "INVALID_REQUEST" error code
13. **Given** a request with decimal requestedLimit, **When** request submitted, **Then** system returns HTTP 400 with "INVALID_REQUEST" error code
14. **Given** a request with currency not matching 3-letter format, **When** request submitted, **Then** system returns HTTP 400 with validation error

**Audit**:

15. **Given** any successful credit decision, **When** response returned, **Then** audit record exists in DynamoDB with all required attributes and status "OK"
16. **Given** any validation error, **When** error response returned, **Then** audit record exists in DynamoDB with status "FAILED" and errorCode
17. **Given** a request with API Gateway authorizer context, **When** audit record created, **Then** principalId extracted from requestContext
18. **Given** a request without API Gateway authorizer context, **When** audit record created, **Then** principalId set to "anonymous"

**Response Format**:

19. **Given** any successful decision, **When** response returned, **Then** HTTP 200 with JSON containing decisionId (UUID), decision, approvedLimit, currency, reasonCodes (array), explanations (array), timestamp (ISO 8601)
20. **Given** any validation error, **When** error response returned, **Then** HTTP 400 with JSON containing errorCode and message
21. **Given** any internal error, **When** error response returned, **Then** HTTP 500 with JSON containing errorCode and message
22. **Given** any response, **When** returned to client, **Then** Content-Type header is application/json

**Determinism**:

23. **Given** two identical requests with same buyerId, policyId, requestedLimit, currency, **When** processed at different times, **Then** decision, approvedLimit, reasonCodes, and explanations are identical (only decisionId and timestamp differ)

**Observability**:

24. **Given** any request processed, **When** logs emitted, **Then** all log entries include decisionId for correlation
25. **Given** any request processed, **When** logs emitted, **Then** logs are structured (JSON-compatible format)
