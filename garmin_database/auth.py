"""Session persistence uses DPAPI, never a plaintext temporary token store."""

import ctypes
import logging
import os
from ctypes import wintypes
from pathlib import Path

from .settings import application_dir
from .util import Cancelled, atomic_write, check_stop

LOGIN_STAGES = {
    "connect": "łączenie z Garmin Connect",
    "mfa_wait": "oczekiwanie na kod MFA",
    "mfa_verify": "potwierdzanie kodu MFA i dostępu aplikacji do Garmin",
    "session_save": "zabezpieczanie i zapis sesji Windows",
    "ready": "sesja gotowa",
}


def login_http_status(error):
    """Read only structured status codes; never include upstream error text."""
    for _ in range(8):
        if error is None:
            return None
        status = getattr(getattr(error, "response", None), "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            return status
        error = error.__cause__ or error.__context__
    return None


class LoginFailed(RuntimeError):
    """A safe diagnostic for UI/CLI; never contains a response or credentials."""

    def __init__(self, stage, error):
        self.stage = stage if stage in LOGIN_STAGES else "connect"
        self.http_status = login_http_status(error)
        reasons = {
            "GarminConnectAuthenticationError": "ACCESS_DENIED",
            "GarminConnectTooManyRequestsError": "RATE_LIMIT",
            "GarminConnectConnectionError": "CONNECTION",
        }
        reason = reasons.get(type(error).__name__, "CLIENT_ERROR")
        if self.stage == "session_save":
            reason = "LOCAL_SESSION"
        self.code = f"{self.stage.upper()}/{reason}"
        message = f"Etap: {LOGIN_STAGES[self.stage]}.\nKod diagnostyczny: {self.code}"
        if self.http_status is not None:
            message += f"; HTTP {self.http_status}"
        if reason == "RATE_LIMIT":
            message += ". Odczekaj przed ponowieniem logowania."
        super().__init__(message)


class SessionRequired(RuntimeError):
    def __init__(self):
        super().__init__(
            "Brak zapisanej sesji Garmin. Otwórz Ustawienia i zaloguj się do Garmin."
        )


def dpapi(payload, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("Magazyn sesji tej wersji wymaga Windows")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(payload)
    source = Blob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError(
            ctypes.get_last_error(), "Nie można odczytać lub zabezpieczyć sesji Windows"
        )
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class SessionStore:
    def __init__(self, path=None, protector=dpapi):
        self.path = Path(path or application_dir() / "auth/session.bin")
        self.protector = protector

    def save(self, token):
        atomic_write(self.path, self.protector(token.encode("utf-8")))

    def load(self):
        return self.protector(self.path.read_bytes(), decrypt=True).decode("utf-8")

    def clear(self):
        self.path.unlink(missing_ok=True)


class GarminSource:
    def __init__(self, store=None, factory=None):
        if factory is None:
            from garminconnect import Garmin

            factory = Garmin
        self.factory = factory
        self.store = store or SessionStore()
        self.api = None
        self.login_stage = "connect"
        # The upstream client may log response bodies; app reports only error codes.
        for name in ("garminconnect", "requests", "urllib3", "curl_cffi"):
            logging.getLogger(name).setLevel(logging.CRITICAL)

    def login(self, email=None, password=None, mfa=None, stop=None, progress=None):
        check_stop(stop)
        self.api = None
        self.set_login_stage("connect", progress)
        api = None
        try:
            api = self.factory(
                email=email,
                password=password,
                prompt_mfa=self.mfa_prompt(mfa, stop, progress),
                retry_attempts=1,
            )
            # Inline JSON explicitly overrides upstream GARMINTOKENS environment
            # paths, so the library cannot persist an unencrypted token store.
            api.login(self.login_token(email))
            check_stop(stop)
            self.set_login_stage("session_save", progress)
            self.store.save(api.client.dumps())
            self.api = api
            self.set_login_stage("ready", progress)
        except (Cancelled, SessionRequired):
            raise
        except Exception as error:
            raise LoginFailed(self.login_stage, error) from error
        finally:
            if api is not None:
                api.password = None
                api.prompt_mfa = None

    def login_token(self, email):
        if email is not None:
            return "{}"
        try:
            return self.store.load()
        except FileNotFoundError:
            raise SessionRequired() from None

    def set_login_stage(self, stage, progress):
        self.login_stage = stage
        if progress is not None:
            progress(stage)

    def mfa_prompt(self, callback, stop, progress):
        if callback is None:
            return None

        def prompt():
            self.set_login_stage("mfa_wait", progress)
            code = callback().strip()
            check_stop(stop)
            self.set_login_stage("mfa_verify", progress)
            return code

        return prompt

    def download_health_snapshot(self, day):
        if self.api is None:
            self.login()
        payload = self.api.download_health_snapshot(day)
        self.store.save(self.api.client.dumps())  # retain refreshed tokens
        return payload
