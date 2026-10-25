"""Paced overview reads, one worker and no change-driven SQL polling."""

import copy
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from garmin_database.adapters.inbound.desktop.workers import Worker
from garmin_database.domain.cancellation import check_stop


class OverviewPoller(QObject):
    ready = Signal(object)
    failed = Signal(str)
    catalog_failed = Signal(str)
    busy_changed = Signal(bool)
    idle = Signal()
    interval_ms = 15_000
    catalog_interval = 60.0

    def __init__(self, services, settings, path, visible, parent):
        super().__init__(parent)
        self.services, self.settings, self.path = services, settings, path
        self.visible = visible
        self.worker = None
        self.initialized = False
        self.generation = self.job_generation = 0
        self.catalog_revision = None
        self.catalog_checked = float("-inf")
        self.pending = self.stopped = False
        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    @property
    def busy(self):
        return self.worker is not None

    def poll(self):
        if self.visible():
            self.request(force_catalog=False)

    def configure(self, services, settings):
        self.services, self.settings = services, settings
        self.generation += 1
        self.catalog_revision = None
        self.catalog_checked = float("-inf")
        if self.worker is not None:
            self.worker.stop.set()
            self.pending = True
        else:
            self.request()

    def request(self, force_catalog=True):
        if self.stopped or self.worker is not None:
            return
        services, settings, path = (
            self.services,
            copy.deepcopy(self.settings),
            self.path,
        )
        include_catalog = (
            force_catalog
            or time.monotonic() - self.catalog_checked >= self.catalog_interval
        )
        revision = self.catalog_revision

        def read(worker):
            result = services.overview(worker.stop, revision, False)
            check_stop(worker.stop)
            if not include_catalog:
                return result
            worker.preview.emit(dict(result))
            result = {**result, **services.catalog(worker.stop, revision)}
            if result["parameters"] is not None and settings.migrate(
                result["parameters"]
            ):
                check_stop(worker.stop)
                services.settings_store.save(settings, path)
                result["settings"] = settings
            return result

        self.job_generation = self.generation
        self.job_catalog = include_catalog
        self.job_status_ready = False
        worker = Worker(read, self)
        self.worker = worker
        worker.success.connect(self.accept)
        worker.preview.connect(self.accept_status)
        worker.failure.connect(self.reject)
        worker.finished.connect(self.release)
        self.busy_changed.emit(True)
        worker.start()

    @Slot(object)
    def accept_status(self, result):
        if self.stopped or self.job_generation != self.generation:
            return
        self.job_status_ready = True
        self.catalog_checked = time.monotonic()
        self.initialized = True
        self.ready.emit(result)

    @Slot(object)
    def accept(self, result):
        if self.stopped or self.job_generation != self.generation:
            return
        self.initialized = True
        if self.job_catalog:
            self.catalog_revision = result["catalog_revision"]
            self.catalog_checked = time.monotonic()
        if "settings" in result:
            self.settings = result["settings"]
        self.ready.emit(result)

    @Slot(str)
    def reject(self, message):
        if not self.stopped and self.job_generation == self.generation:
            self.initialized = True
            if self.job_status_ready:
                self.catalog_failed.emit(message)
            else:
                self.failed.emit(message)

    @Slot()
    def release(self):
        worker, self.worker = self.worker, None
        worker.operation = None
        worker.deleteLater()
        self.busy_changed.emit(False)
        if self.pending and not self.stopped:
            self.pending = False
            self.request()
        self.idle.emit()

    def shutdown(self):
        self.stopped = True
        self.pending = False
        self.timer.stop()
        if self.worker is not None:
            self.worker.stop.set()
