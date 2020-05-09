import logging
from functools import wraps
from time import sleep

from .exc import ServiceRateLimitError, ServiceUnavailableError

logger = logging.getLogger(__name__)

_RETRIES_RATELIMITED = 10
_RETRIES_UNAVAILABLE = 3
_DELAY_UNAVAILABLE_SECONDS = 5


def retry_ratelimited(f):
    # XXX make it configurable
    @wraps(f)
    def f_with_retries(*args, **kwargs):
        for i in range(_RETRIES_RATELIMITED, 0, -1):
            try:
                return f(*args, **kwargs)
            except ServiceRateLimitError as e:
                if i <= 1:
                    raise
                s = e.rate_limit_duration_seconds
                logger.warning("Rate limit reached. Waiting %d seconds..." % s)
                sleep(s)
        raise RuntimeError("Should not have been reached")

    return f_with_retries


def retry_unavailable(f):
    # XXX make it configurable
    @wraps(f)
    def f_with_retries(*args, **kwargs):
        for i in range(_RETRIES_UNAVAILABLE, 0, -1):
            try:
                return f(*args, **kwargs)
            except ServiceUnavailableError as e:
                if i <= 1:
                    raise
                s = _DELAY_UNAVAILABLE_SECONDS
                logger.warning(
                    "Service unavailable: %s. Waiting %d seconds..." % (e, s)
                )
                sleep(s)
        raise RuntimeError("Should not have been reached")

    return f_with_retries
