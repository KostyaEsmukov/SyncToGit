import logging
from functools import wraps
from time import sleep

from .exc import ServiceRateLimitError

logger = logging.getLogger(__name__)

_RETRIES = 10


def retry_ratelimited(f):
    # XXX make it configurable
    @wraps(f)
    def c(*args, **kwargs):
        for i in range(_RETRIES, 0, -1):
            try:
                return f(*args, **kwargs)
            except ServiceRateLimitError as e:
                if i <= 1:
                    raise
                s = e.rate_limit_duration_seconds
                logger.warning("Rate limit reached. Waiting %d seconds..." % s)
                sleep(s)
        raise RuntimeError("Should not have been reached")

    return c
