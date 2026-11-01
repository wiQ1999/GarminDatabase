import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from garmin_database.application.errors import (
    LoginFailed,
    SessionRequired,
    SessionStorageError,
)


def login_causes(error):
    """Bound traversal, including libraries that wrap local I/O as auth errors."""
    for _ in range(8):
        if error is None:
            break
        yield error
        error = getattr(error, "__cause__", None) or getattr(error, "__context__", None)


def login_http_status(error):
    """Read only structured status codes; never include upstream error text."""
    for error in login_causes(error):
        status = getattr(getattr(error, "response", None), "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            return status
    return None


def login_failure(stage, error):
    reasons = {
        "GarminConnectAuthenticationError": "ACCESS_DENIED",
        "GarminConnectTooManyRequestsError": "RATE_LIMIT",
        "GarminConnectConnectionError": "CONNECTION",
    }
    reason = reasons.get(type(error).__name__, "CLIENT_ERROR")
    if any(isinstance(cause, FileNotFoundError) for cause in login_causes(error)):
        reason = "LOCAL_RUNTIME"
    if stage == "session_save":
        reason = "LOCAL_SESSION"
    status = login_http_status(error)
    if status is None:
        status = {"ACCESS_DENIED": 401, "RATE_LIMIT": 429}.get(reason)
    return LoginFailed(stage, reason, status)


def error_status(error):
    if isinstance(error, (SessionRequired, SessionStorageError)):
        return None
    if isinstance(error, LoginFailed) and error.code.endswith("/LOCAL_SESSION"):
        return None
    for cause in login_causes(error):
        status = cause_status(cause)
        if status is not None:
            return status
    return None


def cause_status(error):
    status = getattr(getattr(error, "response", None), "status_code", None)
    if type(status) is int and 100 <= status <= 599:
        return status
    match = re.search(r"(?:API Error|HTTP|status[=: ]+)\s*(\d{3})", str(error), re.I)
    if match:
        return int(match.group(1))
    for fragment, status in (("Authentication", 401), ("TooManyRequests", 429)):
        if fragment in type(error).__name__:
            return status
    return None


def retry_after(error, fallback, now=None):
    """Respect the server delay without persisting response headers or bodies."""
    for error in login_causes(error):
        headers = getattr(getattr(error, "response", None), "headers", {}) or {}
        value = headers.get("Retry-After")
        if value is not None:
            try:
                delay = (
                    int(value)
                    if str(value).isdigit()
                    else (
                        parsedate_to_datetime(str(value))
                        - (now or datetime.now(timezone.utc))
                    ).total_seconds()
                )
                return max(fallback, delay)
            except (TypeError, ValueError, OverflowError):
                pass
    return fallback
