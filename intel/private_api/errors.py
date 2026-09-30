# STAGE 7 PHASE L — stable JSON error contract (Te spec: no raw stack traces in HTTP
# responses; a fixed vocabulary of error codes, not ad-hoc strings per endpoint).
ERROR_CODES = (
    "NOT_FOUND", "INVALID_QUERY", "UNAUTHORIZED", "DATA_UNAVAILABLE",
    "PROVENANCE_UNKNOWN", "INSUFFICIENT_EVIDENCE",
)

_HTTP_STATUS_BY_CODE = {
    "NOT_FOUND": 404,
    "INVALID_QUERY": 400,
    "UNAUTHORIZED": 401,
    "DATA_UNAVAILABLE": 503,
    "PROVENANCE_UNKNOWN": 404,
    "INSUFFICIENT_EVIDENCE": 404,
}


class ApiError(Exception):
    """Raised by service functions for an error condition; the HTTP layer catches this and
    only this (plus a final catch-all INTERNAL_ERROR with no stack trace) to build the JSON
    error body - a service function never lets a raw exception reach the HTTP response."""

    def __init__(self, code, message):
        assert code in ERROR_CODES, f"unknown API error code: {code}"
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def http_status(self):
        return _HTTP_STATUS_BY_CODE[self.code]

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message}}
