"""Each manual login uses a fresh client; credentials are never persisted here."""

from garmin_database.domain.cancellation import check_stop


class Login:
    def __init__(self, source_factory):
        self.source_factory = source_factory

    def run(self, email, password, mfa, stop, progress):
        check_stop(stop)
        source = self.source_factory()
        source.login(email, password, mfa, stop=stop, progress=progress)
        return "login"
