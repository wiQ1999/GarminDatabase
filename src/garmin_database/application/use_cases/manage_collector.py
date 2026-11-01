"""Manage collector installation, offline status and authentication through ports."""

from dataclasses import asdict
from datetime import datetime, timezone

from garmin_database.application.ports import (
    CollectorRecords,
    CollectorRegistration,
    CollectorScheduler,
)


class CollectorManager:
    def __init__(
        self,
        files: CollectorRecords,
        scheduler: CollectorScheduler,
        *,
        registration: CollectorRegistration,
        runtime_factory,
        source_factory,
    ):
        self.files, self.scheduler = files, scheduler
        self.registration = registration
        self.runtime_factory = runtime_factory
        self.source_factory = source_factory

    def runtime(self, config, synchronize):
        return self.runtime_factory(config, synchronize)

    def apply(self, config):
        if not self.registration.apply(config):
            self._record_applied(config)

    def install(self, config):
        if not self.registration.install(config):
            self._record_applied(config)

    def prepare_key(self, config):
        self.registration.prepare_key(config)

    def _record_applied(self, config):
        with self.files.lock(config):
            state = self.files.load_state(config)
            state.applied_revision = config.revision
            self.files.save_state(config, state)
        self.registration.after_applied(config)

    def status(self, config=None):
        config = config or self.files.load_config()
        state = self.files.load_state(config)
        task = self.scheduler.status(config)
        # Derive next time instead of displaying a stale value saved by an old run.
        next_run = (
            config.schedule.next_after(datetime.now(timezone.utc)).isoformat()
            if config.enabled and task["enabled"]
            else None
        )
        session_present = self.files.session_present(config)
        return {
            "schedule": task,
            "config_revision": config.revision,
            "state": asdict(state),
            "next_run": next_run,
            "session_present": session_present,
        }

    def login(
        self, config, session_factory, email, password, mfa, stop, *, progress=None
    ):
        store = session_factory(config)
        with self.files.lock(config), store.lock():
            self.source_factory(store).login(
                email, password, mfa, stop=stop, progress=progress
            )
            state = self.files.load_state(config)
            state.auth_required = False
            state.auth_generation = None
            self.files.save_state(config, state)
