import time


class Cancelled(Exception):
    pass


def check_stop(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()


class DeadlineStop:
    """Combine an external stop signal with a monotonic read deadline."""

    def __init__(self, stop, seconds):
        self.stop = stop
        self.deadline = time.monotonic() + seconds

    def is_set(self):
        return (
            self.stop is not None and self.stop.is_set()
        ) or time.monotonic() >= self.deadline
