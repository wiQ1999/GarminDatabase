"""Exercise the installed Garmin SDK through MFA, mocking only HTTP transport."""

import json
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import requests
from garminconnect import Garmin, GarminConnectTooManyRequestsError, client

from garmin_database.auth import GarminSource, LoginFailed, SessionStore

pytestmark = pytest.mark.unit


class GarminTransport:
    def __init__(self):
        self.calls = []
        self.login_session = None
        self.fail = None

    def request(self, session, method, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((method, path))
        status = 200
        if path.endswith("/sign-in"):
            self.login_session = session
            session.cookies.set("synthetic-cookie", "synthetic-value")
            body = {}
        elif path.endswith("/api/login"):
            assert session is self.login_session
            assert session.cookies.get("synthetic-cookie") == "synthetic-value"
            assert kwargs["json"]["username"] == "synthetic@example.invalid"
            body = {
                "responseStatus": {"type": "MFA_REQUIRED"},
                "customerMfaInfo": {"mfaLastMethodUsed": "email"},
            }
        elif path.endswith("/mfa/verifyCode"):
            assert session is self.login_session
            assert kwargs["json"]["mfaVerificationCode"] == "123456"
            body = {
                "responseStatus": {
                    "type": "INVALID_MFA_CODE" if self.fail == "mfa" else "SUCCESSFUL"
                },
                "serviceTicketId": "ST-synthetic",
            }
        elif urlsplit(url).hostname == "diauth.garmin.com":
            body = {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
            }
        elif path.endswith("/socialProfile"):
            status = 403 if self.fail == "profile" else 200
            body = {
                "displayName": "synthetic-profile",
                "fullName": "Synthetic",
                "profileId": 1,
            }
        elif path.endswith("/user-settings"):
            body = {"userData": {"measurementSystem": "metric"}}
        else:
            raise AssertionError(f"Unexpected test HTTP endpoint: {method} {path}")
        response = requests.Response()
        response.status_code = status
        response.url = url
        response._content = json.dumps(body).encode()
        return response


@pytest.fixture(params=["requests", "cffi"])
def sdk_login(tmp_path, monkeypatch, request):
    transport = GarminTransport()
    monkeypatch.setattr(
        requests.Session,
        "request",
        lambda session, method, url, **kw: transport.request(
            session, method, url, **kw
        ),
    )
    monkeypatch.setattr(
        client.cffi_requests.Session,
        "request",
        lambda session, method, url, **kw: transport.request(
            session, method, url, **kw
        ),
    )
    use_cffi = request.param == "cffi"
    monkeypatch.setattr(client, "HAS_CFFI", use_cffi)
    monkeypatch.setattr("garminconnect.client.sso.time.sleep", lambda seconds: None)
    token_dir = tmp_path / "forbidden-plaintext-tokens"
    monkeypatch.setenv("GARMINTOKENS", str(token_dir))
    apis = []

    def factory(**kwargs):
        api = Garmin(**kwargs)
        # Exercise each complete mobile strategy without real network access.
        api.client.skip_strategies.update(
            {"widget+cffi", "portal+cffi", "portal+requests"}
            | ({"mobile+requests"} if use_cffi else {"mobile+cffi"})
        )
        apis.append(api)
        return api

    store = SessionStore(
        tmp_path / "session.bin", lambda data, decrypt=False: data[::-1]
    )
    source = GarminSource(store, factory)
    return SimpleNamespace(
        source=source, store=store, transport=transport, apis=apis, token_dir=token_dir
    )


def login(source, stages=None):
    source.login(
        "synthetic@example.invalid",
        "synthetic-password",
        lambda: " 123456\n",
        progress=stages.append if stages is not None else None,
    )


def test_sdk_mfa_uses_warmed_session_and_saves_only_after_api_accepts(sdk_login):
    flow = sdk_login
    stages = []
    login(flow.source, stages)
    assert stages == ["connect", "mfa_wait", "mfa_verify", "session_save", "ready"]
    assert flow.transport.calls[0][0] == "GET"
    assert flow.transport.calls[0][1].endswith("/sign-in")
    assert flow.source.api is flow.apis[0]
    assert flow.source.api.password is None and flow.source.api.prompt_mfa is None
    saved = json.loads(flow.store.load())
    assert saved["di_token"] == "synthetic-access"
    assert "synthetic-access" not in flow.store.path.read_text()
    assert (
        "123456" not in flow.store.load()
        and "synthetic-password" not in flow.store.load()
    )
    assert not flow.token_dir.exists()


@pytest.mark.parametrize("failure", ["mfa", "profile"])
def test_sdk_post_mfa_failure_preserves_session_and_allows_fresh_retry(
    sdk_login, failure
):
    flow = sdk_login
    flow.store.save("old-encrypted-session")
    before = flow.store.path.read_bytes()
    flow.transport.fail = failure
    with pytest.raises(LoginFailed) as result:
        login(flow.source)
    assert result.value.stage == "mfa_verify"
    assert "MFA_VERIFY/" in str(result.value)
    assert "Sprawdź e-mail" not in str(result.value)
    assert flow.source.api is None and flow.store.path.read_bytes() == before
    assert flow.apis[0].password is None and flow.apis[0].prompt_mfa is None
    assert not flow.token_dir.exists()
    flow.transport.fail = None
    login(flow.source)
    assert flow.source.api is flow.apis[1] and flow.apis[0] is not flow.apis[1]


def test_sdk_success_with_local_store_failure_has_distinct_diagnostic(
    sdk_login, monkeypatch
):
    flow = sdk_login

    def fail_save(token):
        raise OSError("synthetic-private-path")

    monkeypatch.setattr(flow.store, "save", fail_save)
    with pytest.raises(LoginFailed) as result:
        login(flow.source)
    assert result.value.code == "SESSION_SAVE/LOCAL_SESSION"
    assert "synthetic-private-path" not in str(result.value)
    assert flow.source.api is None and not flow.store.path.exists()
    assert flow.apis[0].password is None and flow.apis[0].prompt_mfa is None


def test_login_diagnostic_uses_structured_status_without_upstream_message():
    error = requests.HTTPError("synthetic-password token=synthetic-secret")
    error.response = SimpleNamespace(status_code=403)
    wrapped = RuntimeError("synthetic-private-response")
    wrapped.__cause__ = error
    diagnostic = LoginFailed("mfa_verify", wrapped)
    assert diagnostic.http_status == 403
    assert "HTTP 403" in str(diagnostic)
    assert "synthetic" not in str(diagnostic)
    limited = LoginFailed("connect", GarminConnectTooManyRequestsError("private"))
    assert limited.code == "CONNECT/RATE_LIMIT" and "Odczekaj" in str(limited)


def test_missing_runtime_file_is_not_reported_as_garmin_access_denied():
    from garminconnect import GarminConnectAuthenticationError

    missing = FileNotFoundError("synthetic-private-path")
    transport = requests.ConnectionError("synthetic-private-response")
    transport.__cause__ = missing
    auth = GarminConnectAuthenticationError("synthetic-private-profile-error")
    auth.__cause__ = transport
    diagnostic = LoginFailed("mfa_verify", auth)
    assert diagnostic.code == "MFA_VERIFY/LOCAL_RUNTIME"
    assert "składnika lokalnej paczki" in str(diagnostic)
    assert "synthetic" not in str(diagnostic)
    local_save = LoginFailed("session_save", missing)
    assert local_save.code == "SESSION_SAVE/LOCAL_SESSION"
