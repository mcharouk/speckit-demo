"""Lambda handler for Credit Limit Decision API Gateway integration"""

import json
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from src.credit_decision.audit_repo import AuditRepository
from src.credit_decision.data_sources import InMemoryRiskDataSource
from src.credit_decision.decision_engine import evaluate_decision
from src.credit_decision.errors import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_REQUEST,
    ERROR_MISSING_REQUIRED_FIELD,
    InternalError,
    ValidationError,
    to_http_response,
)
from src.credit_decision.models import AuditRecord, CreditDecisionRequest

# Initialize dependencies (reused across Lambda invocations)
risk_data_source = InMemoryRiskDataSource()
audit_repo = AuditRepository()


def log_structured(decision_id: str, level: str, message: str, **kwargs) -> None:
    """
    Emit structured JSON log with decisionId for correlation.

    Args:
        decision_id: Unique decision identifier
        level: Log level (INFO, ERROR, etc.)
        message: Log message
        **kwargs: Additional fields to include in log
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "decisionId": decision_id,
        "message": message,
        **kwargs,
    }
    print(json.dumps(log_entry))


def validate_request(data: dict) -> CreditDecisionRequest:
    """
    Validate and parse request data into CreditDecisionRequest.

    Validation rules:
    - buyerId: required, non-empty string
    - policyId: required, non-empty string
    - requestedLimit: required, positive integer (no decimals)
    - currency: required, exactly 3 uppercase letters
    - requestId: optional string

    Args:
        data: Parsed JSON request body

    Returns:
        Validated CreditDecisionRequest dataclass

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if not data.get("buyerId"):
        raise ValidationError(ERROR_MISSING_REQUIRED_FIELD, "buyerId is required")

    if not data.get("policyId"):
        raise ValidationError(ERROR_MISSING_REQUIRED_FIELD, "policyId is required")

    if "requestedLimit" not in data:
        raise ValidationError(
            ERROR_MISSING_REQUIRED_FIELD, "requestedLimit is required"
        )

    if "currency" not in data:
        raise ValidationError(ERROR_MISSING_REQUIRED_FIELD, "currency is required")

    # Validate requestedLimit: must be positive integer (no decimals)
    requested_limit = data.get("requestedLimit")
    if not isinstance(requested_limit, int) or isinstance(requested_limit, bool):
        raise ValidationError(
            ERROR_INVALID_REQUEST, "requestedLimit must be a whole number (integer)"
        )

    if requested_limit <= 0:
        raise ValidationError(
            ERROR_INVALID_REQUEST, "requestedLimit must be greater than 0"
        )

    # Validate currency: exactly 3 uppercase letters
    currency = data.get("currency")
    if not isinstance(currency, str) or not re.match(r"^[A-Z]{3}$", currency):
        raise ValidationError(
            ERROR_INVALID_REQUEST,
            "currency must be exactly 3 uppercase letters (e.g., USD, EUR)",
        )

    # Create validated request object
    return CreditDecisionRequest(
        buyerId=data["buyerId"],
        policyId=data["policyId"],
        requestedLimit=requested_limit,
        currency=currency,
        requestId=data.get("requestId"),
    )


def extract_principal_id(event: dict) -> str:
    """
    Extract principalId from API Gateway authorizer context.

    Args:
        event: Lambda proxy integration event

    Returns:
        principalId from authorizer context, or "anonymous" if not present
    """
    try:
        return (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("principalId", "anonymous")
        )
    except (AttributeError, TypeError):
        return "anonymous"


def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda handler for Credit Limit Decision API.

    Orchestrates:
    1. Request validation
    2. Data retrieval (risk profile)
    3. Decision logic evaluation
    4. Audit record persistence
    5. Response formatting

    Args:
        event: API Gateway Lambda proxy integration event
        context: Lambda context object

    Returns:
        Lambda proxy response with statusCode, headers, and body
    """
    decision_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    log_structured(decision_id, "INFO", "Processing credit decision request")

    try:
        # Parse request body
        body = json.loads(event.get("body", "{}"))
        log_structured(
            decision_id, "INFO", "Request body parsed", buyerId=body.get("buyerId")
        )

        # Validate request
        request = validate_request(body)
        log_structured(
            decision_id,
            "INFO",
            "Request validated",
            buyerId=request.buyerId,
            policyId=request.policyId,
            requestedLimit=request.requestedLimit,
        )

        # Retrieve risk profile
        risk_profile = risk_data_source.get_risk_profile(
            request.buyerId, request.policyId
        )
        log_structured(
            decision_id,
            "INFO",
            "Risk profile retrieved",
            riskGrade=risk_profile.riskGrade,
            pastDueOver60=risk_profile.pastDueOver60,
        )

        # Evaluate decision
        response = evaluate_decision(request, risk_profile, decision_id, timestamp)
        log_structured(
            decision_id,
            "INFO",
            "Decision evaluated",
            decision=response.decision,
            approvedLimit=response.approvedLimit,
            reasonCodes=response.reasonCodes,
        )

        # Write audit record for success
        principal_id = extract_principal_id(event)
        audit_record = AuditRecord(
            decisionId=decision_id,
            timestamp=timestamp,
            principalId=principal_id,
            buyerId=request.buyerId,
            policyId=request.policyId,
            requestedLimit=request.requestedLimit,
            currency=request.currency,
            requestId=request.requestId,
            riskGrade=risk_profile.riskGrade,
            pastDueOver60=risk_profile.pastDueOver60,
            decision=response.decision,
            approvedLimit=response.approvedLimit,
            reasonCodes=response.reasonCodes,
            status="OK",
            errorCode=None,
        )
        audit_repo.write_audit_record(audit_record)
        log_structured(decision_id, "INFO", "Audit record written")

        # Return success response
        response_body = {
            "decisionId": response.decisionId,
            "decision": response.decision,
            "approvedLimit": response.approvedLimit,
            "currency": response.currency,
            "reasonCodes": response.reasonCodes,
            "explanations": response.explanations,
            "timestamp": response.timestamp,
        }

        return to_http_response(200, body=response_body)

    except ValidationError as e:
        # Validation error - write audit with FAILED status
        log_structured(
            decision_id,
            "ERROR",
            "Validation error",
            errorCode=e.error_code,
            errorMessage=e.message,
        )

        try:
            principal_id = extract_principal_id(event)
            audit_record = AuditRecord(
                decisionId=decision_id,
                timestamp=timestamp,
                principalId=principal_id,
                buyerId=body.get("buyerId", ""),
                policyId=body.get("policyId", ""),
                requestedLimit=(
                    body.get("requestedLimit", 0)
                    if isinstance(body.get("requestedLimit"), int)
                    else 0
                ),
                currency=body.get("currency", ""),
                requestId=body.get("requestId"),
                riskGrade=None,
                pastDueOver60=None,
                decision=None,
                approvedLimit=None,
                reasonCodes=None,
                status="FAILED",
                errorCode=e.error_code,
            )
            audit_repo.write_audit_record(audit_record)
        except Exception as audit_error:
            log_structured(
                decision_id,
                "ERROR",
                "Failed to write audit for validation error",
                error=str(audit_error),
            )

        return to_http_response(400, error_code=e.error_code, message=e.message)

    except Exception as e:
        # Internal error
        log_structured(
            decision_id,
            "ERROR",
            "Internal error",
            error=str(e),
            traceback=traceback.format_exc(),
        )

        try:
            principal_id = extract_principal_id(event)
            audit_record = AuditRecord(
                decisionId=decision_id,
                timestamp=timestamp,
                principalId=principal_id,
                buyerId=body.get("buyerId", "") if "body" in locals() else "",
                policyId=body.get("policyId", "") if "body" in locals() else "",
                requestedLimit=(
                    body.get("requestedLimit", 0)
                    if "body" in locals()
                    and isinstance(body.get("requestedLimit"), int)
                    else 0
                ),
                currency=body.get("currency", "") if "body" in locals() else "",
                requestId=body.get("requestId") if "body" in locals() else None,
                riskGrade=None,
                pastDueOver60=None,
                decision=None,
                approvedLimit=None,
                reasonCodes=None,
                status="FAILED",
                errorCode=ERROR_INTERNAL_ERROR,
            )
            audit_repo.write_audit_record(audit_record)
        except Exception as audit_error:
            log_structured(
                decision_id,
                "ERROR",
                "Failed to write audit for internal error",
                error=str(audit_error),
            )

        return to_http_response(
            500, error_code=ERROR_INTERNAL_ERROR, message="Internal server error"
        )
