import contextlib
import logging
import sys
from io import StringIO


class PrintOnExceptionOnly:
    def __init__(self, quiet: bool, logging_level=logging.INFO):
        self.quiet = quiet
        self.logging_level = logging_level
        self.captured_output = None
        self.stack = None

    def __enter__(self):
        self.captured_output = StringIO()
        self.stack = contextlib.ExitStack()
        if self.quiet:
            self.stack.enter_context(contextlib.redirect_stdout(self.captured_output))
            self.stack.enter_context(contextlib.redirect_stderr(self.captured_output))
            self._init_logger(self.captured_output)
        else:
            self._init_logger(sys.stderr)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stack.close()
        if self.quiet and exc_type is not None:
            sys.stderr.write(self.captured_output.getvalue())

        self._init_logger(sys.stderr)
        self.captured_output.close()

    def _init_logger(self, stream):
        logging.basicConfig(stream=stream, level=self.logging_level)
