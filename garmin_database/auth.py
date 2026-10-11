"""Session persistence uses DPAPI, never a plaintext temporary token store."""

import ctypes
import logging
import os
from ctypes import wintypes
from pathlib import Path

from .settings import application_dir
from .util import atomic_write


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
        # The upstream client may log response bodies; app reports only error codes.
        for name in ("garminconnect", "requests", "urllib3", "curl_cffi"):
            logging.getLogger(name).setLevel(logging.CRITICAL)

    def login(self, email=None, password=None, mfa=None):
        api = self.factory(
            email=email, password=password, prompt_mfa=mfa, retry_attempts=1
        )
        try:
            # Inline JSON explicitly overrides upstream GARMINTOKENS environment
            # paths, so the library cannot persist an unencrypted token store.
            try:
                token = self.store.load() if email is None else "{}"
            except FileNotFoundError:
                raise SessionRequired() from None
            api.login(token)
            self.store.save(api.client.dumps())
            self.api = api
        finally:
            api.password = None

    def download_health_snapshot(self, day):
        if self.api is None:
            self.login()
        payload = self.api.download_health_snapshot(day)
        self.store.save(self.api.client.dumps())  # retain refreshed tokens
        return payload
