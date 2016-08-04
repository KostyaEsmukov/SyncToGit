import logging
import sys
from cStringIO import StringIO


class PrintOnExceptionOnly(object):
    originalStdout = None
    patchedStdout = None

    originalStderr = None
    patchedStderr = None

    loggingLevel = None

    def __init__(self, loggingLevel):
        self.loggingLevel = loggingLevel

    def _resetLogger(self):
        logging.basicConfig(stream=sys.stdout, level=self.loggingLevel)

    def __enter__(self):
        self.originalStdout = sys.stdout
        self.originalStderr = sys.stderr

        sys.stdout = self.patchedStdout = StringIO()
        sys.stderr = self.patchedStderr = self.patchedStdout

        self._resetLogger()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.originalStdout
        sys.stderr = self.originalStderr

        self._resetLogger()

        if exc_type is not None:
            sys.stderr.write(self.patchedStdout.getvalue())

        self.patchedStdout.close()
