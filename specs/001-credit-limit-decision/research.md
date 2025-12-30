# Research: Credit Limit Decision Service (MVP)

**Date**: 2025-12-30  
**Phase**: 0 - Outline & Research  
**Purpose**: Resolve technical unknowns and document technology choices

## Research Findings

### 1. AWS Lambda Python 3.13 Runtime Compatibility

**Question**: Is Python 3.13 available as Lambda runtime? What are implications for dataclasses?

**Decision**: Use Python 3.13 runtime (specified in constitution and user requirements)

**Rationale**:
- Python 3.13 includes enhanced dataclass features with improved type hinting support
- Stdlib dataclasses sufficient for this use case (no Pydantic needed)
- Native JSON serialization with `dataclasses.asdict()` for responses
- AWS Lambda supports custom runtimes if Python 3.13 not yet in managed runtimes

**Alternatives Considered**:
- Python 3.11/3.12: More mature Lambda support, but requirement specifies 3.13
- Pydantic for validation: Rejected due to constitution principle IV (minimal dependencies)

**Implementation Notes**:
- Use `@dataclass` decorator from stdlib
- Manual JSON serialization in handler (no auto-serialization framework)
- Type hints: `str`, `int`, `list[str]`, `Optional[T]` for nullable fields

---

### 2. API Gateway HTTP API vs REST API

**Question**: Should we use HTTP API or REST API for API Gateway?

**Decision**: HTTP API (Lambda proxy integration)

**Rationale**:
- Simpler, lower cost (70% cheaper than REST API)
- Native Lambda proxy integration (event structure well-documented)
- Sufficient for MVP (no need for REST API features like request/response transformations)
- Better latency characteristics (important for <200ms p95 goal)

**Alternatives Considered**:
- REST API: More features (caching, WAF, usage plans) but overkill for MVP
- Lambda Function URL: Even simpler but lacks authorization integration

**Implementation Notes**:
- Event structure: `event['body']` contains JSON string
- Response format: `{"statusCode": 200, "headers": {...}, "body": "..."}`
- Authorization: requestContext.authorizer.principalId extraction

---

### 3. DynamoDB Table Design for Audit

**Question**: What's the optimal partition key and attributes for audit table?

**Decision**: Partition key = `DECISION#{decisionId}`, no sort key (single-item-per-decision pattern)

**Rationale**:
- Each decision is immutable and independent (no need for sort key)
- DecisionId is unique UUID, provides good partition distribution
- No query access patterns in MVP (write-only audit)
- Simplifies IAM permissions (PutItem only)

**Alternatives Considered**:
- Partition key = buyerId, Sort key = timestamp: Would enable buyer history queries, but out of scope for MVP
- Composite key with policyId: Similar issue, adds complexity for no MVP value
- Global Secondary Index on principalId: Deferred to post-MVP

**Implementation Notes**:
- Partition key attribute name: `pk` (string)
- Attributes: all from spec FR-012 (decisionId, timestamp, principalId, buyerId, policyId, requestedLimit, currency, requestId, riskGrade, pastDueOver60, decision, approvedLimit, reasonCodes, status, errorCode)
- TTL attribute: Add `ttl` (number, epoch seconds) for future retention policy
- Capacity: On-demand billing mode (no provisioned capacity planning needed)

---

### 4. Stubbed Data Sources Design Pattern

**Question**: How to stub internal risk data sources while maintaining clean interface for future swap?

**Decision**: Abstract protocol with in-memory implementation

**Rationale**:
- Python `Protocol` (typing.Protocol) defines interface without inheritance
- In-memory dict implementation for MVP: `{"BYR-12345": {"riskGrade": "A", "pastDueOver60": False}}`
- Future: swap to real implementation (e.g., DynamoDB lookup, external API call) by injecting different instance
- Enables unit testing decision engine with fake data sources

**Alternatives Considered**:
- Abstract Base Class (ABC): More heavyweight, requires inheritance
- Direct dict access in decision logic: Violates constitution (pure function principle)
- Environment variable configuration: Too inflexible for testing

**Implementation Notes**:
```python
# data_sources.py
class RiskDataSource(Protocol):
    def get_buyer_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        ...

class InMemoryRiskDataSource:
    def __init__(self):
        self.data = {"BYR-12345": {"riskGrade": "A", "pastDueOver60": False}}
    
    def get_buyer_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        # Return BuyerRiskProfile dataclass
        pass
```

---

### 5. Error Handling Strategy

**Question**: How to map Python exceptions to HTTP status codes + JSON errors?

**Decision**: Custom exception hierarchy with error code mapping

**Rationale**:
- Define custom exceptions: `ValidationError`, `InternalError`, `DataRetrievalError`
- Handler catches exceptions and maps to `{"errorCode": "...", "message": "..."}` + HTTP status
- Centralizes error handling logic (DRY principle)
- Maintains type safety (typed exception classes)

**Alternatives Considered**:
- Result type (Ok/Err): More functional, but not idiomatic Python
- HTTP library exceptions: Would require importing framework (violates minimal dependencies)
- Plain dict returns: Loses type safety, harder to test

**Implementation Notes**:
```python
# errors.py
class CreditDecisionError(Exception):
    error_code: str
    http_status: int

class ValidationError(CreditDecisionError):
    error_code = "INVALID_REQUEST"
    http_status = 400

class MissingFieldError(ValidationError):
    error_code = "MISSING_REQUIRED_FIELD"
    http_status = 400
```

---

### 6. Testing Strategy for Decision Matrix

**Question**: How to test all 7 decision rules comprehensively?

**Decision**: Parameterized pytest tests with decision matrix table

**Rationale**:
- Use `@pytest.mark.parametrize` to define table of inputs → expected outputs
- Covers all rule branches (9 acceptance criteria from spec)
- Makes test cases readable and easy to extend
- Enables property-based testing (same input → same output)

**Alternatives Considered**:
- Individual test functions per rule: Too much duplication
- Hypothesis property-based testing: Overkill for deterministic rules with finite input space
- Manual test scripts: Not automated, can't run in CI/CD

**Implementation Notes**:
```python
# test_decision_engine.py
@pytest.mark.parametrize("risk_grade,past_due,requested,expected_decision,expected_limit,expected_reasons", [
    ("D", False, 100000, "DECLINE", 0, ["RISK_GRADE_HIGH"]),
    ("C", False, 100000, "REFER", 0, ["RISK_GRADE_MEDIUM"]),
    # ... all 9+ test cases
])
def test_decision_rules(risk_grade, past_due, requested, expected_decision, expected_limit, expected_reasons):
    # Test implementation
    pass
```

---

### 7. SAM Template Best Practices

**Question**: What IAM permissions and SAM configurations are needed?

**Decision**: Minimal IAM (DynamoDB PutItem only), explicit function configuration

**Rationale**:
- Principle of least privilege: only grant PutItem on specific table
- Explicit timeout (10 seconds), memory (256 MB) for cost/performance predictability
- Environment variable for table name (no hardcoding)
- CloudWatch Logs permissions auto-added by SAM

**Alternatives Considered**:
- Administrator access: Security violation
- Wildcard DynamoDB permissions: Violates least privilege
- Inline table name in code: Violates 12-factor app configuration principle

**Implementation Notes**:
```yaml
# template.yaml
Resources:
  CreditDecisionFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.13
      Handler: credit_decision.handler.lambda_handler
      Timeout: 10
      MemorySize: 256
      Environment:
        Variables:
          AUDIT_TABLE_NAME: !Ref CreditDecisionAuditTable
      Policies:
        - DynamoDBWritePolicy:
            TableName: !Ref CreditDecisionAuditTable
```

**Minimal IAM Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:*:*:table/CreditDecisionAudit"
    },
    {
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

---

### 8. Structured Logging Format

**Question**: What JSON log format ensures CloudWatch queryability?

**Decision**: Flat JSON with standard fields + decisionId

**Rationale**:
- CloudWatch Insights can query JSON logs efficiently
- Standard fields: timestamp, level, message, decisionId
- Avoid nested objects (harder to query)
- Use Python `json.dumps()` with consistent key names

**Alternatives Considered**:
- Python `logging` module JSON formatter: Adds dependency or custom formatter
- Print statements with string formatting: Not structured, not queryable
- AWS Lambda Powertools: Great library but violates minimal dependencies principle

**Implementation Notes**:
```python
import json
from datetime import datetime, timezone

def log(level: str, message: str, decision_id: str, **extra):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "decisionId": decision_id,
        **extra
    }
    print(json.dumps(log_entry))  # Lambda captures stdout to CloudWatch
```

---

## Research Summary

**All NEEDS CLARIFICATION items resolved:**

1. ✅ Python 3.13 runtime compatibility → Use stdlib dataclasses, manual JSON serialization
2. ✅ API Gateway choice → HTTP API with Lambda proxy integration
3. ✅ DynamoDB schema → Single-item pattern with `DECISION#{id}` partition key
4. ✅ Data source stubbing → Protocol-based interface with in-memory MVP implementation
5. ✅ Error handling → Custom exception hierarchy mapped to HTTP status + JSON
6. ✅ Testing approach → Parameterized pytest tests for decision matrix
7. ✅ SAM configuration → Minimal IAM (PutItem only), explicit resource limits
8. ✅ Structured logging → Flat JSON with decisionId for CloudWatch Insights

**Ready for Phase 1: Design & Contracts**
