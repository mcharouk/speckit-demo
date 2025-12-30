"""Unit tests for decision engine - all 7 decision rules"""

import pytest

from src.credit_decision.decision_engine import evaluate_decision
from src.credit_decision.models import (
    DECISION_APPROVE,
    DECISION_DECLINE,
    DECISION_REFER,
    REASON_LIMIT_CAPPED_BY_GRADE,
    REASON_PAST_DUE_DATA_MISSING,
    REASON_PAST_DUE_OVER_60,
    REASON_RISK_DATA_MISSING,
    REASON_RISK_GRADE_HIGH,
    REASON_RISK_GRADE_MEDIUM,
    BuyerRiskProfile,
    CreditDecisionRequest,
)

# Test fixtures
DECISION_ID = "test-decision-id"
TIMESTAMP = "2025-12-30T10:00:00.000Z"


def create_request(
    requested_limit: int = 500_000, currency: str = "USD"
) -> CreditDecisionRequest:
    """Helper to create test request"""
    return CreditDecisionRequest(
        buyerId="BYR-TEST",
        policyId="POL-TEST",
        requestedLimit=requested_limit,
        currency=currency,
    )


class TestDeclineRules:
    """Test Rule 1: Risk grade D or E → DECLINE"""

    @pytest.mark.parametrize("risk_grade", ["D", "E"])
    def test_decline_high_risk(self, risk_grade):
        """AC-1: Risk grade D/E → DECLINE with RISK_GRADE_HIGH reason"""
        request = create_request(500_000)
        risk_profile = BuyerRiskProfile(riskGrade=risk_grade, pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_DECLINE
        assert response.approvedLimit == 0
        assert REASON_RISK_GRADE_HIGH in response.reasonCodes
        assert len(response.explanations) == len(response.reasonCodes)


class TestReferralRules:
    """Test Rules 2, 3, 6, 7: Various REFER scenarios"""

    def test_refer_medium_risk(self):
        """AC-2: Risk grade C → REFER with RISK_GRADE_MEDIUM reason"""
        request = create_request(500_000)
        risk_profile = BuyerRiskProfile(riskGrade="C", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_REFER
        assert response.approvedLimit == 0
        assert REASON_RISK_GRADE_MEDIUM in response.reasonCodes

    @pytest.mark.parametrize("risk_grade", ["A", "B"])
    def test_refer_past_due(self, risk_grade):
        """AC-3: Grade A/B + past due over 60 → REFER with PAST_DUE_OVER_60 reason"""
        request = create_request(500_000)
        risk_profile = BuyerRiskProfile(riskGrade=risk_grade, pastDueOver60=True)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_REFER
        assert response.approvedLimit == 0
        assert REASON_PAST_DUE_OVER_60 in response.reasonCodes

    def test_refer_missing_risk_grade(self):
        """AC-8: Missing risk grade → REFER with RISK_DATA_MISSING reason"""
        request = create_request(500_000)
        risk_profile = BuyerRiskProfile(riskGrade=None, pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_REFER
        assert response.approvedLimit == 0
        assert REASON_RISK_DATA_MISSING in response.reasonCodes

    def test_refer_missing_past_due(self):
        """AC-9: Missing past due data → REFER with PAST_DUE_DATA_MISSING reason"""
        request = create_request(500_000)
        risk_profile = BuyerRiskProfile(riskGrade="A", pastDueOver60=None)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_REFER
        assert response.approvedLimit == 0
        assert REASON_PAST_DUE_DATA_MISSING in response.reasonCodes


class TestApprovalRules:
    """Test Rules 4 & 5: Grade A and B approvals with capping"""

    def test_approve_grade_a_under_limit(self):
        """AC-4: Grade A + no past due, limit ≤1M → APPROVE with full amount"""
        request = create_request(800_000)
        risk_profile = BuyerRiskProfile(riskGrade="A", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_APPROVE
        assert response.approvedLimit == 800_000
        assert REASON_LIMIT_CAPPED_BY_GRADE not in response.reasonCodes
        assert response.currency == "USD"

    def test_approve_grade_a_capped(self):
        """AC-5: Grade A + no past due, limit >1M → APPROVE capped at 1M with reason"""
        request = create_request(1_500_000)
        risk_profile = BuyerRiskProfile(riskGrade="A", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_APPROVE
        assert response.approvedLimit == 1_000_000
        assert REASON_LIMIT_CAPPED_BY_GRADE in response.reasonCodes

    def test_approve_grade_b_under_limit(self):
        """AC-6: Grade B + no past due, limit ≤500K → APPROVE with full amount"""
        request = create_request(400_000)
        risk_profile = BuyerRiskProfile(riskGrade="B", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_APPROVE
        assert response.approvedLimit == 400_000
        assert REASON_LIMIT_CAPPED_BY_GRADE not in response.reasonCodes

    def test_approve_grade_b_capped(self):
        """AC-7: Grade B + no past due, limit >500K → APPROVE capped at 500K with reason"""
        request = create_request(700_000)
        risk_profile = BuyerRiskProfile(riskGrade="B", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.decision == DECISION_APPROVE
        assert response.approvedLimit == 500_000
        assert REASON_LIMIT_CAPPED_BY_GRADE in response.reasonCodes


class TestDeterminism:
    """Test deterministic behavior"""

    def test_determinism(self):
        """AC-23: Identical inputs → identical outputs (except decisionId/timestamp)"""
        request = create_request(600_000)
        risk_profile = BuyerRiskProfile(riskGrade="A", pastDueOver60=False)

        # Call twice with same inputs (but different IDs/timestamps)
        response1 = evaluate_decision(
            request, risk_profile, "id-1", "2025-12-30T10:00:00Z"
        )
        response2 = evaluate_decision(
            request, risk_profile, "id-2", "2025-12-30T11:00:00Z"
        )

        # Decision, approvedLimit, reasonCodes, explanations should be identical
        assert response1.decision == response2.decision
        assert response1.approvedLimit == response2.approvedLimit
        assert response1.reasonCodes == response2.reasonCodes
        assert response1.explanations == response2.explanations
        assert response1.currency == response2.currency

        # Only decisionId and timestamp should differ
        assert response1.decisionId != response2.decisionId
        assert response1.timestamp != response2.timestamp


class TestCurrencyHandling:
    """Test currency is echoed correctly"""

    @pytest.mark.parametrize("currency", ["USD", "EUR", "GBP"])
    def test_currency_echo(self, currency):
        """Verify currency is echoed back unchanged"""
        request = create_request(500_000, currency)
        risk_profile = BuyerRiskProfile(riskGrade="A", pastDueOver60=False)

        response = evaluate_decision(request, risk_profile, DECISION_ID, TIMESTAMP)

        assert response.currency == currency
