"""Authenticated encrypted token storage; the key is supplied by systemd."""

import os
import secrets
import stat
import subprocess
from pathlib import Path

from garmin_database.adapters.outbound.filesystem.files import atomic_write, file_lock

MAGIC = b"GDBS1"
CREDENTIAL = "garmin-session-key"


class SessionStore:
    def __init__(self, path, *, key_path=None):
        self.path = Path(path)
        self.key_path = Path(key_path) if key_path else None

    def lock(self):
        return file_lock(self.path.with_suffix(self.path.suffix + ".lock"))

    def _cipher(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        directory = os.environ.get("CREDENTIALS_DIRECTORY")
        path = self.key_path or (Path(directory) / CREDENTIAL if directory else None)
        if path is None:
            raise RuntimeError(
                "Uruchom polecenie z poświadczeniem systemd garmin-session-key"
            )
        if path.stat().st_mode & (
            stat.S_IRGRP | stat.S_IWGRP | stat.S_IWOTH | stat.S_IROTH
        ):
            raise PermissionError("Nieprawidłowa ochrona poświadczenia sesji")
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("Nieprawidłowy klucz sesji")
        return AESGCM(key)

    def save(self, token):
        nonce = secrets.token_bytes(12)
        payload = MAGIC + nonce + self._cipher().encrypt(nonce, token.encode(), MAGIC)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write(self.path, payload)
        self.path.chmod(0o600)

    def load(self):
        payload = self.path.read_bytes()
        if not payload.startswith(MAGIC) or len(payload) < len(MAGIC) + 28:
            raise ValueError("Nieprawidłowy format zaszyfrowanej sesji")
        offset = len(MAGIC)
        return (
            self._cipher()
            .decrypt(payload[offset : offset + 12], payload[offset + 12 :], MAGIC)
            .decode()
        )

    def clear(self):
        self.path.unlink(missing_ok=True)


def prepare_key(path):
    """Create once; cleartext key exists only in memory and the subprocess pipe."""
    path = Path(path)
    if path.exists():
        raise FileExistsError("Poświadczenie już istnieje; zachowano istniejącą sesję")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "systemd-creds",
            "encrypt",
            "--with-key=host",
            f"--name={CREDENTIAL}",
            "-",
            str(path),
        ],
        input=secrets.token_bytes(32),
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Nie udało się zabezpieczyć klucza przez systemd-creds")
    path.chmod(0o600)
