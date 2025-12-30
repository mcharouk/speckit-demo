# Quickstart: Credit Limit Decision Service (MVP)

**Purpose**: Get developers up and running with local development and deployment  
**Audience**: Python developers new to the project  
**Prerequisites**: Python 3.13, AWS CLI, AWS SAM CLI, pytest

---

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
# Clone repository (if not already cloned)
git clone <repo-url>
cd <repo-name>
git checkout 001-credit-limit-decision

# Install Python dependencies
pip install -r requirements.txt

# Install dev dependencies for testing
pip install pytest pytest-cov
```

### 2. Project Structure Overview

```
src/credit_decision/
├── handler.py           # Lambda entrypoint (API Gateway proxy integration)
├── models.py            # Dataclasses: Request, Response, RiskProfile, AuditRecord
├── decision_engine.py   # Pure function: evaluate_decision()
├── data_sources.py      # Stubbed risk data lookups (in-memory dicts for MVP)
├── audit_repo.py        # DynamoDB writer for audit records
└── errors.py            # Error types + HTTP status mapping

tests/
├── test_decision_engine.py      # Unit tests for all 7 decision rules
├── test_handler_validation.py   # Integration tests for request validation
└── test_integration.py          # End-to-end Lambda handler tests
```

### 3. Run Unit Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/credit_decision --cov-report=html --cov-report=term

# Run specific test file
python -m pytest tests/test_decision_engine.py -v

# Run with detailed output
python -m pytest -vv
```

**Expected Output**: All tests should pass (green). Coverage should be >90% for decision_engine.py.

### 4. Test Locally with SAM CLI

```bash
# Build the SAM application
sam build

# Start local API Gateway
sam local start-api

# In another terminal, test the endpoint
curl -X POST http://127.0.0.1:3000/credit-decisions \
  -H "Content-Type: application/json" \
  -d '{
    "buyerId": "BYR-12345",
    "policyId": "POL-67890",
    "requestedLimit": 750000,
    "currency": "USD"
  }'
```

**Expected Response** (example for Grade A buyer with no past due):
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

**Note**: Local testing uses stubbed data sources (see `data_sources.py` for pre-configured test buyers).

---

## Deployment to AWS

### 1. Configure AWS Credentials

```bash
# Configure AWS CLI (if not already done)
aws configure

# Verify credentials
aws sts get-caller-identity
```

### 2. Deploy with SAM

```bash
# Build for deployment
sam build

# Deploy (first time - guided)
sam deploy --guided

# Follow prompts:
# - Stack name: credit-decision-service
# - Region: us-east-1 (or your preferred region)
# - Confirm changes: Y
# - Allow SAM CLI IAM role creation: Y
# - Disable rollback: N
# - Save arguments to samconfig.toml: Y

# Subsequent deployments (uses saved config)
sam deploy
```

### 3. Get API Endpoint

```bash
# Get API Gateway URL from stack outputs
aws cloudformation describe-stacks \
  --stack-name credit-decision-service \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
```

**Example Output**: `https://abc123.execute-api.us-east-1.amazonaws.com/`

### 4. Test Deployed API

```bash
# Set API URL (replace with your actual URL)
API_URL="https://abc123.execute-api.us-east-1.amazonaws.com"

# Test successful approval
curl -X POST ${API_URL}/credit-decisions \
  -H "Content-Type: application/json" \
  -d '{
    "buyerId": "BYR-12345",
    "policyId": "POL-67890",
    "requestedLimit": 750000,
    "currency": "USD"
  }'

# Test validation error
curl -X POST ${API_URL}/credit-decisions \
  -H "Content-Type: application/json" \
  -d '{
    "policyId": "POL-67890",
    "requestedLimit": 100000,
    "currency": "USD"
  }'
# Expected: {"errorCode": "MISSING_REQUIRED_FIELD", "message": "buyerId is required"}
```

### 5. View Logs

```bash
# Get Lambda function name
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name credit-decision-service \
  --query 'Stacks[0].Outputs[?OutputKey==`FunctionName`].OutputValue' \
  --output text)

# Tail logs in real-time
sam logs -n ${FUNCTION_NAME} --tail

# Query logs with CloudWatch Insights
aws logs start-query \
  --log-group-name /aws/lambda/${FUNCTION_NAME} \
  --start-time $(date -u -d '5 minutes ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, decisionId, level, message | sort @timestamp desc | limit 20'
```

---

## Module-by-Module Development Guide

### models.py - Data Classes

**Responsibility**: Define all request/response/entity dataclasses

**Key Classes**:
- `CreditDecisionRequest`: Input from API Gateway
- `BuyerRiskProfile`: Risk data from data sources
- `CreditDecisionResponse`: Output to API Gateway
- `AuditRecord`: DynamoDB audit record

**Implementation Tips**:
```python
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass(frozen=True)  # Immutable for determinism
class CreditDecisionRequest:
    buyerId: str
    policyId: str
    requestedLimit: int
    currency: str
    requestId: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
```

**Tests**: Validate dataclass creation, serialization, validation

---

### errors.py - Error Handling

**Responsibility**: Define custom exceptions and HTTP status mapping

**Key Classes**:
```python
class CreditDecisionError(Exception):
    """Base exception for all credit decision errors"""
    error_code: str
    http_status: int

class ValidationError(CreditDecisionError):
    error_code = "INVALID_REQUEST"
    http_status = 400

class MissingFieldError(ValidationError):
    error_code = "MISSING_REQUIRED_FIELD"
    http_status = 400
    
    def __init__(self, field_name: str):
        self.message = f"{field_name} is required"
        super().__init__(self.message)
```

**Tests**: Verify error codes and messages

---

### decision_engine.py - Core Decision Logic

**Responsibility**: Pure function that evaluates credit decision (NO I/O)

**Signature**:
```python
def evaluate_decision(
    request: CreditDecisionRequest,
    risk_profile: BuyerRiskProfile
) -> CreditDecisionResponse:
    """
    Evaluates credit limit decision based on request and risk profile.
    
    MUST be deterministic: same inputs -> same output (excluding decisionId/timestamp).
    MUST NOT perform I/O operations (no AWS calls, no network, no file access).
    
    Args:
        request: Credit decision request from underwriter
        risk_profile: Buyer risk assessment data
    
    Returns:
        Credit decision response with outcome, limit, reason codes, explanations
    """
    pass
```

**Implementation Steps**:
1. Generate decisionId (UUID v4)
2. Apply decision rules 1-7 in order (see spec)
3. Build reason codes + explanations list
4. Return CreditDecisionResponse

**Tests**: Parameterized tests for all 9 acceptance criteria (see `test_decision_engine.py`)

---

### data_sources.py - Risk Data Retrieval

**Responsibility**: Retrieve buyer risk profile (stubbed for MVP)

**Interface**:
```python
from typing import Protocol

class RiskDataSource(Protocol):
    def get_buyer_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        """Retrieve risk profile for buyer"""
        ...

class InMemoryRiskDataSource:
    """MVP stub implementation with in-memory data"""
    
    def __init__(self):
        self.data = {
            "BYR-12345": {"riskGrade": "A", "pastDueOver60": False},
            "BYR-54321": {"riskGrade": "B", "pastDueOver60": False},
            "BYR-99999": {"riskGrade": "C", "pastDueOver60": False},
            "BYR-88888": {"riskGrade": "D", "pastDueOver60": True},
            # Add more test data as needed
        }
    
    def get_buyer_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        data = self.data.get(buyer_id, {"riskGrade": None, "pastDueOver60": None})
        return BuyerRiskProfile(
            riskGrade=data.get("riskGrade"),
            pastDueOver60=data.get("pastDueOver60")
        )
```

**Future Enhancement**: Replace with DynamoDB lookup or external API call

---

### audit_repo.py - DynamoDB Writer

**Responsibility**: Write audit records to DynamoDB

**Implementation**:
```python
import boto3
import os
from datetime import datetime, timezone

class AuditRepository:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.environ['AUDIT_TABLE_NAME']
        self.table = self.dynamodb.Table(self.table_name)
    
    def write_audit_record(self, audit_record: AuditRecord) -> None:
        """Write immutable audit record to DynamoDB"""
        item = {
            'pk': audit_record.pk,
            'decisionId': audit_record.decisionId,
            'timestamp': audit_record.timestamp,
            # ... all other fields
        }
        self.table.put_item(Item=item)
```

**Error Handling**: Log DynamoDB errors but don't block response (eventual consistency)

---

### handler.py - Lambda Entrypoint

**Responsibility**: Orchestrate request validation → data retrieval → decision → audit → response

**Lambda Handler Signature**:
```python
def lambda_handler(event, context):
    """
    AWS Lambda handler for API Gateway HTTP API proxy integration.
    
    Args:
        event: API Gateway event (contains body, headers, requestContext)
        context: Lambda context (requestId, etc.)
    
    Returns:
        API Gateway proxy response (statusCode, headers, body)
    """
    pass
```

**Implementation Flow**:
1. Parse `event['body']` JSON → `CreditDecisionRequest`
2. Validate request (raise errors if invalid)
3. Extract principalId from `event['requestContext']['authorizer']` (or "anonymous")
4. Retrieve risk profile from data source
5. Call `evaluate_decision()` (pure function)
6. Create audit record
7. Write audit to DynamoDB (fire-and-forget with error logging)
8. Return HTTP 200 with JSON response

**Error Handling**:
```python
try:
    # Main logic
except MissingFieldError as e:
    return {
        'statusCode': e.http_status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'errorCode': e.error_code, 'message': e.message})
    }
except Exception as e:
    # Log unexpected error with decisionId
    return {
        'statusCode': 500,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'errorCode': 'INTERNAL_ERROR', 'message': 'An unexpected error occurred'})
    }
```

---

## Testing Strategy

### Unit Tests (test_decision_engine.py)

**Purpose**: Test all 7 decision rules in isolation

```python
import pytest
from credit_decision.decision_engine import evaluate_decision
from credit_decision.models import CreditDecisionRequest, BuyerRiskProfile

@pytest.mark.parametrize("risk_grade,past_due,requested,expected_decision,expected_limit,expected_reasons", [
    ("D", False, 100000, "DECLINE", 0, ["RISK_GRADE_HIGH"]),
    ("E", True, 500000, "DECLINE", 0, ["RISK_GRADE_HIGH"]),
    ("C", False, 100000, "REFER", 0, ["RISK_GRADE_MEDIUM"]),
    ("A", True, 200000, "REFER", 0, ["PAST_DUE_OVER_60"]),
    ("A", False, 800000, "APPROVE", 800000, []),
    ("A", False, 1500000, "APPROVE", 1000000, ["LIMIT_CAPPED_BY_GRADE"]),
    ("B", False, 400000, "APPROVE", 400000, []),
    ("B", False, 700000, "APPROVE", 500000, ["LIMIT_CAPPED_BY_GRADE"]),
    (None, False, 100000, "REFER", 0, ["RISK_DATA_MISSING"]),
    ("A", None, 100000, "REFER", 0, ["PAST_DUE_DATA_MISSING"]),
])
def test_decision_rules(risk_grade, past_due, requested, expected_decision, expected_limit, expected_reasons):
    request = CreditDecisionRequest(
        buyerId="TEST-001",
        policyId="POL-001",
        requestedLimit=requested,
        currency="USD"
    )
    risk_profile = BuyerRiskProfile(riskGrade=risk_grade, pastDueOver60=past_due)
    
    response = evaluate_decision(request, risk_profile)
    
    assert response.decision == expected_decision
    assert response.approvedLimit == expected_limit
    assert response.reasonCodes == expected_reasons
    assert response.currency == "USD"
```

### Integration Tests (test_handler_validation.py)

**Purpose**: Test request validation and error handling

```python
def test_missing_buyer_id():
    event = {
        'body': json.dumps({
            'policyId': 'POL-001',
            'requestedLimit': 100000,
            'currency': 'USD'
        })
    }
    response = lambda_handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['errorCode'] == 'MISSING_REQUIRED_FIELD'
    assert 'buyerId' in body['message']

def test_decimal_requested_limit():
    event = {
        'body': json.dumps({
            'buyerId': 'BYR-001',
            'policyId': 'POL-001',
            'requestedLimit': 100000.50,
            'currency': 'USD'
        })
    }
    response = lambda_handler(event, {})
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['errorCode'] == 'INVALID_REQUEST'
```

---

## Performance Considerations

**Target**: p95 latency < 200ms (excluding cold start)

**Optimization Tips**:
1. **Minimize Lambda package size**: Keep dependencies minimal (no heavy frameworks)
2. **Reuse DynamoDB connections**: Initialize `boto3.resource('dynamodb')` outside handler
3. **Parallel data retrieval**: If multiple data sources needed (future), use concurrent.futures
4. **Efficient JSON parsing**: Use stdlib `json` module (avoid heavy serialization libraries)
5. **Cold start mitigation**: Consider provisioned concurrency for production (not in MVP)

**Monitoring**:
- CloudWatch metric: `Duration` (should be <200ms p95)
- CloudWatch metric: `Errors` (should be near zero for internal errors)
- CloudWatch Insights: Query by decisionId for end-to-end request tracing

---

## Troubleshooting

### Issue: "Module not found" error in Lambda

**Solution**: Ensure handler path in `template.yaml` matches directory structure:
```yaml
Handler: credit_decision.handler.lambda_handler  # Not src.credit_decision.handler
```

### Issue: DynamoDB write fails with "AccessDeniedException"

**Solution**: Verify IAM policy grants `dynamodb:PutItem` on correct table ARN

### Issue: Request validation passes but decision logic fails

**Solution**: Check CloudWatch logs for exceptions. Ensure risk data source returns valid `BuyerRiskProfile`

### Issue: Tests pass locally but fail in Lambda

**Solution**: Check Python version (must be 3.13 locally and in template.yaml). Verify all dependencies in requirements.txt

---

## Next Steps

1. **Run tests**: `pytest` (should all pass)
2. **Deploy to AWS**: `sam build && sam deploy --guided`
3. **Test API**: Use curl or Postman with examples from this guide
4. **Review logs**: Check CloudWatch for structured JSON logs with decisionId
5. **Verify audit**: Query DynamoDB table to confirm audit records are written

**Ready to implement?** See [data-model.md](data-model.md) for entity details and [api-contract.yaml](contracts/api-contract.yaml) for full API specification.

**Questions?** Check [spec.md](spec.md) for requirements and [research.md](research.md) for technology decisions.
