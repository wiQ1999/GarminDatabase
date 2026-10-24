class Cancelled(Exception):
    pass


def check_stop(stop):
    if stop is not None and stop.is_set():
        raise Cancelled()
