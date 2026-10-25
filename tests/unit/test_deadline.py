from threading import Event

from garmin_database.domain import cancellation


def test_deadline_includes_external_cancellation_and_monotonic_budget(monkeypatch):
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 100)
    event = Event()
    stop = cancellation.DeadlineStop(event, 10)
    assert not stop.is_set()
    event.set()
    assert stop.is_set()
    event.clear()
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 110)
    assert stop.is_set()


def test_deadline_supports_reads_without_external_event(monkeypatch):
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 100)
    stop = cancellation.DeadlineStop(None, 10)
    assert not stop.is_set()
    monkeypatch.setattr(cancellation.time, "monotonic", lambda: 111)
    assert stop.is_set()
