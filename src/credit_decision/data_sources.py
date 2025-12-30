"""Stubbed data sources for buyer risk profile lookups (MVP in-memory implementation)"""

from typing import Protocol

from src.credit_decision.models import BuyerRiskProfile


class RiskDataSource(Protocol):
    """
    Protocol defining interface for risk data retrieval.

    This allows the implementation to be swapped later (e.g., DynamoDB, external API)
    without changing the decision engine or handler code.
    """

    def get_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        """
        Retrieve risk profile for a buyer.

        Args:
            buyer_id: Unique identifier for the buyer
            policy_id: Unique identifier for the insurance policy

        Returns:
            BuyerRiskProfile with riskGrade and pastDueOver60 data
        """
        ...


class InMemoryRiskDataSource:
    """
    In-memory stub implementation of RiskDataSource for MVP.

    Pre-configured with test buyers covering all decision scenarios.
    Replace this with real data source integration post-MVP.
    """

    def __init__(self):
        # Pre-configured test buyers for all scenarios
        self._test_data = {
            # Grade A buyers
            "BYR-A-CLEAN": BuyerRiskProfile(riskGrade="A", pastDueOver60=False),
            "BYR-A-PASTDUE": BuyerRiskProfile(riskGrade="A", pastDueOver60=True),
            # Grade B buyers
            "BYR-B-CLEAN": BuyerRiskProfile(riskGrade="B", pastDueOver60=False),
            "BYR-B-PASTDUE": BuyerRiskProfile(riskGrade="B", pastDueOver60=True),
            # Grade C buyer (medium risk)
            "BYR-C-MEDIUM": BuyerRiskProfile(riskGrade="C", pastDueOver60=False),
            # Grade D and E buyers (high risk)
            "BYR-D-HIGH": BuyerRiskProfile(riskGrade="D", pastDueOver60=False),
            "BYR-E-HIGH": BuyerRiskProfile(riskGrade="E", pastDueOver60=False),
            # Missing data scenarios
            "BYR-NO-GRADE": BuyerRiskProfile(riskGrade=None, pastDueOver60=False),
            "BYR-NO-PASTDUE": BuyerRiskProfile(riskGrade="A", pastDueOver60=None),
            "BYR-NO-DATA": BuyerRiskProfile(riskGrade=None, pastDueOver60=None),
            # Additional test buyers with IDs matching spec examples
            "BYR-12345": BuyerRiskProfile(riskGrade="A", pastDueOver60=False),
            "BYR-67890": BuyerRiskProfile(riskGrade="B", pastDueOver60=False),
        }

    def get_risk_profile(self, buyer_id: str, policy_id: str) -> BuyerRiskProfile:
        """
        Retrieve risk profile from in-memory test data.

        Args:
            buyer_id: Unique identifier for the buyer
            policy_id: Unique identifier for the insurance policy (not used in MVP stub)

        Returns:
            BuyerRiskProfile with riskGrade and pastDueOver60 data.
            Returns profile with None values if buyer not found.
        """
        # Return test data if buyer exists, otherwise return unknown profile
        return self._test_data.get(
            buyer_id, BuyerRiskProfile(riskGrade=None, pastDueOver60=None)
        )
