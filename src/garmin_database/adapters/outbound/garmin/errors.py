from garmin_database.application.errors import LoginFailed


def login_causes(error):
    """Bound traversal, including libraries that wrap local I/O as auth errors."""
    for _ in range(8):
        if error is None:
            break
        yield error
        error = error.__cause__ or error.__context__


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
    return LoginFailed(stage, reason, login_http_status(error))
