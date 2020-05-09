import contextlib
import threading
import urllib.request
from functools import lru_cache
from io import BytesIO, StringIO
from xml.sax import ContentHandler, ErrorHandler, InputSource
from xml.sax.handler import EntityResolver, feature_external_ges

from defusedxml.sax import make_parser


class _LockedMap:
    def __init__(self):
        self._lock = threading.Lock()
        self._map = dict()

    @contextlib.contextmanager
    def acquire(self, key):
        is_leader = False
        with self._lock:
            event = self._map.get(key)
            if event is None:
                self._map[key] = threading.Event()
                is_leader = True
        if not is_leader:
            event.wait()
        try:
            yield
        finally:
            with self._lock:
                if is_leader:
                    self._map[key].set()
                    del self._map[key]


class _CachingEntityResolver(EntityResolver):
    """This class caches DTD contents so they aren't
    requested for each parsed XML document.
    """

    # must be thread-safe.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._locked_map = _LockedMap()

    def resolveEntity(self, publicId, systemId):
        if systemId.lower().startswith(("http://", "https://")):
            with self._locked_map.acquire(systemId):
                # TODO lock only for downloads??
                data_str = self.loadRemote(systemId)
            systemId = BytesIO(data_str.encode("ascii"))
        return systemId

    @lru_cache(maxsize=32)
    def loadRemote(self, systemId) -> str:
        data = urllib.request.urlopen(systemId)
        return data.read().decode(data.headers.get_content_charset() or "ascii")


_caching_entity_resolver = _CachingEntityResolver()


def parseString(
    string: str,
    handler: ContentHandler,
    errorHandler=ErrorHandler(),
    forbid_dtd=False,
    forbid_entities=True,
    forbid_external=True,
):
    # Copied from defusedxml.sax.parseString

    parser = make_parser()
    parser.setContentHandler(handler)
    parser.setErrorHandler(errorHandler)
    parser.forbid_dtd = forbid_dtd
    parser.forbid_entities = forbid_entities
    parser.forbid_external = forbid_external

    parser.setEntityResolver(_caching_entity_resolver)

    # Since Python 3.7.1 external DTDs are not processed by default.
    parser.setFeature(feature_external_ges, True)

    inpsrc = InputSource()
    inpsrc.setCharacterStream(StringIO(string))
    parser.parse(inpsrc)
