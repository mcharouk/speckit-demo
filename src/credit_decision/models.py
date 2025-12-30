"""Data models for Credit Limit Decision Service"""

from dataclasses import dataclass
from typing import Optional

# Decision outcome constants
DECISION_APPROVE = "APPROVE"
DECISION_REFER = "REFER"
DECISION_DECLINE = "DECLINE"

# Reason codes
REASON_RISK_GRADE_HIGH = "RISK_GRADE_HIGH"
REASON_RISK_GRADE_MEDIUM = "RISK_GRADE_MEDIUM"
REASON_PAST_DUE_OVER_60 = "PAST_DUE_OVER_60"
REASON_LIMIT_CAPPED_BY_GRADE = "LIMIT_CAPPED_BY_GRADE"
REASON_RISK_DATA_MISSING = "RISK_DATA_MISSING"
REASON_PAST_DUE_DATA_MISSING = "PAST_DUE_DATA_MISSING"

# Reason code explanations
REASON_EXPLANATIONS = {
    REASON_RISK_GRADE_HIGH: "Buyer risk grade is too high (D or E) for credit approval",
    REASON_RISK_GRADE_MEDIUM: "Buyer risk grade (C) requires manual underwriter review",
    REASON_PAST_DUE_OVER_60: "Buyer has past-due payments exceeding 60 days",
    REASON_LIMIT_CAPPED_BY_GRADE: "Requested limit exceeds maximum allowed for buyer's risk grade",
    REASON_RISK_DATA_MISSING: "Buyer risk grade data is not available",
    REASON_PAST_DUE_DATA_MISSING: "Buyer past-due payment data is not available",
}

# Risk grade maximum limits
RISK_GRADE_MAX_LIMITS = {
    "A": 1_000_000,
    "B": 500_000,
}


@dataclass
class CreditDecisionRequest:
    """Represents an underwriter's request for a credit limit decision"""

    buyerId: str
    policyId: str
    requestedLimit: int
    currency: str
    requestId: Optional[str] = None


@dataclass
class BuyerRiskProfile:
    """Represents internal risk assessment data for a buyer"""

    riskGrade: Optional[str]  # "A" | "B" | "C" | "D" | "E" | None
    pastDueOver60: Optional[bool]


@dataclass
class CreditDecisionResponse:
    """Represents the system's decision outcome returned to the underwriter"""

    decisionId: str
    decision: str  # "APPROVE" | "REFER" | "DECLINE"
    approvedLimit: int
    currency: str
    reasonCodes: list[str]
    explanations: list[str]
    timestamp: str  # ISO 8601 UTC


@dataclass
class AuditRecord:
    """Immutable audit record for compliance"""

    decisionId: str
    timestamp: str
    principalId: str
    buyerId: str
    policyId: str
    requestedLimit: int
    currency: str
    requestId: Optional[str]
    riskGrade: Optional[str]
    pastDueOver60: Optional[bool]
    decision: Optional[str]
    approvedLimit: Optional[int]
    reasonCodes: Optional[list[str]]
    status: str  # "OK" | "FAILED"
    errorCode: Optional[str]
