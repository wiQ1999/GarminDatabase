"""Execute one scheduled synchronization; waiting belongs to the OS scheduler."""

from dataclasses import asdict, replace

from garmin_database.application.errors import BusyError
from garmin_database.application.ports import CollectorRuntime
from garmin_database.domain.cancellation import Cancelled
from garmin_database.domain.schedule import instant


class RunCollector:
    def __init__(self, runtime: CollectorRuntime):
        self.runtime = runtime

    def run(self, config, stop, *, scheduled=True):
        config.validate()
        now = self.runtime.now()
        if scheduled:
            if not config.enabled:
                return "disabled"
            slot = config.schedule.due(now, self.runtime.boot_at())
            if slot is None:
                return "not_due"
        else:
            slot = None
        try:
            with self.runtime.lock():
                return self._execute(config, stop, now, slot)
        except BusyError:
            self.runtime.log("skipped_busy")
            return "skipped_busy"

    def _execute(self, config, stop, now, slot):
        state = self.runtime.load()
        if slot is not None:
            if state.applied_revision != config.revision:
                self.runtime.log("config_error")
                return "config_error"
            if (
                state.claimed_revision == config.revision
                and state.claimed_slot
                and instant(state.claimed_slot) >= slot
            ):
                return "already_claimed"
            state.claimed_slot = slot.isoformat()
            state.claimed_revision = config.revision
        state.next_run = (
            config.schedule.next_after(now).isoformat() if config.enabled else None
        )
        self.runtime.save(state)
        try:
            generation = self.runtime.session_generation()
        except OSError:
            state.outcome = "session_error"
            state.summary = None
            return self._finish(config, state)
        paused = self.pause_outcome(state, generation, now)
        if paused is not None:
            return paused
        if state.outcome == "running":
            state.outcome = "interrupted"
        return self._synchronize(config, stop, state, now)

    @staticmethod
    def pause_outcome(state, generation, now):
        if state.auth_required and generation == state.auth_generation:
            return "auth_required"
        if state.not_before and now < instant(state.not_before):
            return "rate_limited"
        return None

    def _synchronize(self, config, stop, state, now):
        previous = replace(state)
        state.auth_required = False
        state.not_before = None
        state.started_at = now.isoformat()
        state.finished_at = None
        state.outcome = "running"
        state.summary = None
        self.runtime.save(state)
        try:
            result = self.runtime.synchronize(config, stop)
            state.summary = asdict(result)
            state.outcome = result.halt_reason or (
                "issues" if result.issue_count else "success"
            )
            state.not_before = result.retry_not_before
            state.auth_required = state.outcome == "auth_required"
            state.auth_generation = None
            if state.outcome == "success":
                state.last_success = self.runtime.now().isoformat()
        except BusyError:
            # Keep the slot claim, but do not replace the last real outcome.
            self.runtime.save(previous)
            self.runtime.log("skipped_busy")
            return "skipped_busy"
        except Cancelled:
            state.outcome = "cancelled"
        except Exception as error:
            state.outcome = self.runtime.classify(error)
        if state.outcome == "auth_required":
            try:
                state.auth_generation = self.runtime.session_generation()
                state.auth_required = True
            except OSError:
                state.outcome = "session_error"
                state.auth_required = False
        return self._finish(config, state)

    def _finish(self, config, state):
        state.finished_at = self.runtime.now().isoformat()
        if config.enabled:
            state.next_run = config.schedule.next_after(self.runtime.now()).isoformat()
        self.runtime.save(state)
        self.runtime.log(
            state.outcome, summary=state.summary, not_before=state.not_before
        )
        return state.outcome
