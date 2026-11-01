"""Signed page positions tied to a query and the current data snapshot."""

import base64
import hmac
import json
import secrets

from garmin_database.application.errors import AccessError
from garmin_database.domain.values import dumps


class PageCursor:
    def __init__(self):
        self.secret = secrets.token_bytes(32)

    def encode(self, value):
        raw = dumps(value).encode()
        digest = hmac.digest(self.secret, raw, "sha256")
        return base64.urlsafe_b64encode(digest + raw).decode()

    def decode(self, cursor, expected):
        try:
            if not isinstance(cursor, str) or len(cursor) > 4096:
                raise ValueError()
            raw = base64.b64decode(cursor, altchars=b"-_", validate=True)
            if not hmac.compare_digest(
                raw[:32], hmac.digest(self.secret, raw[32:], "sha256")
            ):
                raise ValueError()
            value = json.loads(raw[32:])
            if value["query"] != expected:
                raise ValueError()
            return value["next"]
        except (ValueError, TypeError, KeyError):
            raise AccessError(
                "Kursor nieprawidłowy lub nieaktualny. Rozpocznij zapytanie ponownie."
            ) from None
