class ServiceError(Exception):
    pass


class ServiceAuthError(ServiceError):
    """Error during authentication."""

    pass


class UserCancelledError(ServiceAuthError):
    pass


class ServiceTokenExpiredError(ServiceError):
    pass


class ServiceAPIError(ServiceError):
    pass


class ServiceRateLimitError(ServiceAPIError):
    def __init__(self, *args, rate_limit_duration_seconds: float, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rate_limit_duration_seconds = rate_limit_duration_seconds


class ServiceUnavailableError(ServiceAPIError):
    pass
