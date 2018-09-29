from synctogit.service import ServiceAuthError, ServiceTokenExpiredError


class EvernoteError(Exception):
    pass


class EvernoteAuthError(ServiceAuthError, EvernoteError):
    pass


class EvernoteTokenExpiredError(ServiceTokenExpiredError, EvernoteError):
    pass


class EvernoteIOError(IOError, EvernoteError):
    pass


class EvernoteApiError(EvernoteError):
    pass


class EvernoteApiRateLimitError(EvernoteApiError):
    def __init__(self, *args, rate_limit_duration_seconds: float,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rate_limit_duration_seconds = rate_limit_duration_seconds


class EvernoteMalformedNoteError(EvernoteError):
    pass
