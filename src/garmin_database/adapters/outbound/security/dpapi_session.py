"""Windows-only encrypted session storage; never stores a password or MFA code."""

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.files import atomic_write, file_lock
from garmin_database.adapters.outbound.filesystem.settings_json import application_dir


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

    def lock(self):
        return file_lock(self.path.with_suffix(self.path.suffix + ".lock"))

    def save(self, token):
        atomic_write(self.path, self.protector(token.encode("utf-8")))

    def load(self):
        return self.protector(self.path.read_bytes(), decrypt=True).decode("utf-8")

    def clear(self):
        self.path.unlink(missing_ok=True)
