import logging
from contextlib import contextmanager

urllib3_logger = logging.getLogger("urllib3.connectionpool")


@contextmanager
def hide_spurious_urllib3_multipart_warning():
    # https://github.com/urllib3/urllib3/issues/800
    filter = NoHeaderErrorFilter()
    urllib3_logger.addFilter(filter)
    try:
        yield
    finally:
        urllib3_logger.removeFilter(filter)


class NoHeaderErrorFilter(logging.Filter):
    """Filter out urllib3 Header Parsing Errors due to a urllib3 bug."""

    # https://github.com/home-assistant/home-assistant/pull/17042

    def filter(self, record):
        """Filter out Header Parsing Errors."""
        return "Failed to parse headers" not in record.getMessage()
