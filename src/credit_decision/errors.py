"""Error types and HTTP status mapping for Credit Limit Decision Service"""

import json
from typing import Optional


class ValidationError(Exception):
    """Raised when request validation fails (maps to HTTP 400)"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class InternalError(Exception):
    """Raised when internal processing fails (maps to HTTP 500)"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# Error codes
ERROR_INVALID_REQUEST = "INVALID_REQUEST"
ERROR_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
ERROR_INTERNAL_ERROR = "INTERNAL_ERROR"


def to_http_response(
    status_code: int,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    body: Optional[dict] = None,
) -> dict:
    """
    Convert error or success to Lambda proxy response format.

    Args:
        status_code: HTTP status code
        error_code: Error code for error responses
        message: Error message for error responses
        body: Response body for success responses

    Returns:
        Lambda proxy response dict
    """
    headers = {"Content-Type": "application/json"}

    if body is not None:
        # Success response
        response_body = body
    else:
        # Error response
        response_body = {"errorCode": error_code, "message": message}

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(response_body),
    }
