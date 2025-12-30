"""Integration tests for Lambda handler validation and error handling"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.credit_decision.handler import lambda_handler


def create_event(body: dict, authorizer_principal: str = None) -> dict:
    """Helper to create Lambda proxy integration event"""
    event = {"body": json.dumps(body)}

    if authorizer_principal is not None:
        event["requestContext"] = {"authorizer": {"principalId": authorizer_principal}}

    return event


class TestRequestValidation:
    """Test AC-10 through AC-14: Request validation errors"""

    @patch("src.credit_decision.handler.audit_repo")
    def test_missing_buyer_id(self, mock_audit):
        """AC-10: Missing buyerId → HTTP 400 with MISSING_REQUIRED_FIELD"""
        event = create_event(
            {"policyId": "POL-123", "requestedLimit": 500000, "currency": "USD"}
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "MISSING_REQUIRED_FIELD"
        assert "buyerId" in body["message"]

    @patch("src.credit_decision.handler.audit_repo")
    def test_missing_policy_id(self, mock_audit):
        """AC-11: Missing policyId → HTTP 400 with MISSING_REQUIRED_FIELD"""
        event = create_event(
            {"buyerId": "BYR-123", "requestedLimit": 500000, "currency": "USD"}
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "MISSING_REQUIRED_FIELD"
        assert "policyId" in body["message"]

    @patch("src.credit_decision.handler.audit_repo")
    def test_negative_limit(self, mock_audit):
        """AC-12: requestedLimit ≤ 0 → HTTP 400 with INVALID_REQUEST"""
        event = create_event(
            {
                "buyerId": "BYR-123",
                "policyId": "POL-123",
                "requestedLimit": -1000,
                "currency": "USD",
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "INVALID_REQUEST"
        assert "greater than 0" in body["message"]

    @patch("src.credit_decision.handler.audit_repo")
    def test_zero_limit(self, mock_audit):
        """requestedLimit = 0 → HTTP 400 with INVALID_REQUEST"""
        event = create_event(
            {
                "buyerId": "BYR-123",
                "policyId": "POL-123",
                "requestedLimit": 0,
                "currency": "USD",
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "INVALID_REQUEST"

    @patch("src.credit_decision.handler.audit_repo")
    def test_decimal_limit(self, mock_audit):
        """AC-13: Decimal requestedLimit → HTTP 400 with INVALID_REQUEST"""
        event = create_event(
            {
                "buyerId": "BYR-123",
                "policyId": "POL-123",
                "requestedLimit": 500000.50,
                "currency": "USD",
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "INVALID_REQUEST"
        assert "whole number" in body["message"]

    @patch("src.credit_decision.handler.audit_repo")
    @pytest.mark.parametrize("invalid_currency", ["US", "USDD", "us", "12", ""])
    def test_invalid_currency(self, mock_audit, invalid_currency):
        """AC-14: Invalid currency format → HTTP 400 with INVALID_REQUEST"""
        event = create_event(
            {
                "buyerId": "BYR-123",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": invalid_currency,
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["errorCode"] == "INVALID_REQUEST"
        assert "currency" in body["message"].lower()


class TestErrorResponseFormat:
    """Test AC-20: Error response format"""

    @patch("src.credit_decision.handler.audit_repo")
    def test_error_response_format(self, mock_audit):
        """AC-20: Validation error → HTTP 400 with errorCode and message fields"""
        event = create_event(
            {"buyerId": "BYR-123", "policyId": "POL-123", "requestedLimit": 500000}
        )
        # Missing currency

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        assert response["headers"]["Content-Type"] == "application/json"
        body = json.loads(response["body"])
        assert "errorCode" in body
        assert "message" in body
        assert isinstance(body["errorCode"], str)
        assert isinstance(body["message"], str)


class TestSuccessResponse:
    """Test AC-19: Success response format"""

    @patch("src.credit_decision.handler.audit_repo")
    def test_success_response_format(self, mock_audit):
        """AC-19: Success → HTTP 200 with all required fields"""
        event = create_event(
            {
                "buyerId": "BYR-A-CLEAN",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": "USD",
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
        body = json.loads(response["body"])

        # Verify all required response fields
        assert "decisionId" in body
        assert "decision" in body
        assert "approvedLimit" in body
        assert "currency" in body
        assert "reasonCodes" in body
        assert "explanations" in body
        assert "timestamp" in body

        # Verify types
        assert isinstance(body["decisionId"], str)
        assert body["decision"] in ["APPROVE", "REFER", "DECLINE"]
        assert isinstance(body["approvedLimit"], int)
        assert isinstance(body["reasonCodes"], list)
        assert isinstance(body["explanations"], list)
        assert len(body["reasonCodes"]) == len(body["explanations"])


class TestPrincipalIdExtraction:
    """Test AC-17 and AC-18: Principal ID extraction"""

    @patch("src.credit_decision.handler.audit_repo")
    def test_principal_from_authorizer(self, mock_audit):
        """AC-17: principalId extracted from requestContext.authorizer"""
        event = create_event(
            {
                "buyerId": "BYR-A-CLEAN",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": "USD",
            },
            authorizer_principal="user-12345",
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        # Verify audit was called with correct principalId
        mock_audit.write_audit_record.assert_called_once()
        audit_call = mock_audit.write_audit_record.call_args[0][0]
        assert audit_call.principalId == "user-12345"

    @patch("src.credit_decision.handler.audit_repo")
    def test_principal_anonymous(self, mock_audit):
        """AC-18: principalId = 'anonymous' when authorizer absent"""
        event = create_event(
            {
                "buyerId": "BYR-A-CLEAN",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": "USD",
            }
        )
        # No authorizer context

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        # Verify audit was called with anonymous
        mock_audit.write_audit_record.assert_called_once()
        audit_call = mock_audit.write_audit_record.call_args[0][0]
        assert audit_call.principalId == "anonymous"


class TestAuditRecordCreation:
    """Test AC-15 and AC-16: Audit record creation"""

    @patch("src.credit_decision.handler.audit_repo")
    def test_audit_success(self, mock_audit):
        """AC-15: Successful decision → audit record with status 'OK'"""
        event = create_event(
            {
                "buyerId": "BYR-A-CLEAN",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": "USD",
            }
        )

        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        mock_audit.write_audit_record.assert_called_once()
        audit_call = mock_audit.write_audit_record.call_args[0][0]
        assert audit_call.status == "OK"
        assert audit_call.errorCode is None
        assert audit_call.decision is not None

    @patch("src.credit_decision.handler.audit_repo")
    def test_audit_validation_error(self, mock_audit):
        """AC-16: Validation error → audit record with status 'FAILED'"""
        event = create_event(
            {"buyerId": "BYR-123", "policyId": "POL-123", "requestedLimit": 500000}
        )
        # Missing currency

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        mock_audit.write_audit_record.assert_called_once()
        audit_call = mock_audit.write_audit_record.call_args[0][0]
        assert audit_call.status == "FAILED"
        assert audit_call.errorCode == "MISSING_REQUIRED_FIELD"
        assert audit_call.decision is None


class TestContentTypeHeader:
    """Test AC-22: Content-Type header"""

    @patch("src.credit_decision.handler.audit_repo")
    @pytest.mark.parametrize(
        "body",
        [
            {
                "buyerId": "BYR-A-CLEAN",
                "policyId": "POL-123",
                "requestedLimit": 500000,
                "currency": "USD",
            },  # Success
            {
                "buyerId": "BYR-123",
                "policyId": "POL-123",
                "requestedLimit": 500000,
            },  # Error (missing currency)
        ],
    )
    def test_content_type_header(self, mock_audit, body):
        """AC-22: All responses → Content-Type: application/json"""
        event = create_event(body)

        response = lambda_handler(event, None)

        assert "headers" in response
        assert response["headers"]["Content-Type"] == "application/json"
