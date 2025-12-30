"""DynamoDB audit record writer for compliance"""

import os
from dataclasses import asdict

import boto3

from src.credit_decision.models import AuditRecord


class AuditRepository:
    """Writes audit records to DynamoDB for regulatory compliance"""

    def __init__(self, table_name: str = None):
        """
        Initialize audit repository.

        Args:
            table_name: DynamoDB table name (defaults to AUDIT_TABLE_NAME env var)
        """
        self.table_name = table_name or os.environ.get(
            "AUDIT_TABLE_NAME", "CreditDecisionAudit"
        )
        self.dynamodb = boto3.client("dynamodb")

    def write_audit_record(self, record: AuditRecord) -> None:
        """
        Write an immutable audit record to DynamoDB.

        Uses partition key pattern: DECISION#{decisionId}
        No error handling for DynamoDB failures per spec (eventual consistency model).

        Args:
            record: AuditRecord to persist
        """
        # Convert dataclass to dict
        record_dict = asdict(record)

        # Build DynamoDB item with proper type annotations
        item = {
            "pk": {"S": f"DECISION#{record.decisionId}"},
            "decisionId": {"S": record.decisionId},
            "timestamp": {"S": record.timestamp},
            "principalId": {"S": record.principalId},
            "buyerId": {"S": record.buyerId},
            "policyId": {"S": record.policyId},
            "requestedLimit": {"N": str(record.requestedLimit)},
            "currency": {"S": record.currency},
            "status": {"S": record.status},
        }

        # Add optional fields if present
        if record.requestId is not None:
            item["requestId"] = {"S": record.requestId}

        if record.riskGrade is not None:
            item["riskGrade"] = {"S": record.riskGrade}

        if record.pastDueOver60 is not None:
            item["pastDueOver60"] = {"BOOL": record.pastDueOver60}

        if record.decision is not None:
            item["decision"] = {"S": record.decision}

        if record.approvedLimit is not None:
            item["approvedLimit"] = {"N": str(record.approvedLimit)}

        if record.reasonCodes is not None:
            item["reasonCodes"] = {"L": [{"S": code} for code in record.reasonCodes]}

        if record.errorCode is not None:
            item["errorCode"] = {"S": record.errorCode}

        # Write to DynamoDB (no error handling per spec edge case)
        self.dynamodb.put_item(TableName=self.table_name, Item=item)
