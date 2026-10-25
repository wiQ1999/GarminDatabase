"""Session persistence uses DPAPI, never a plaintext temporary token store."""

import logging

from garmin_database.application.errors import (
    SessionRequired,
)
from garmin_database.domain.cancellation import Cancelled, check_stop

from .errors import login_failure


class GarminSource:
    def __init__(self, store, factory=None):
        if factory is None:
            from garminconnect import Garmin

            factory = Garmin
        self.factory = factory
        self.store = store
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
                retry_attempts=0,
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
            raise login_failure(self.login_stage, error) from error
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
