import urllib.request
from functools import lru_cache
from io import BytesIO
from xml.sax import ContentHandler, ErrorHandler, InputSource
from xml.sax.handler import EntityResolver

from defusedxml.sax import make_parser


class _CachingEntityResolver(EntityResolver):
    """This class caches DTD contents so they aren't
    requested for each parsed XML document.
    """
    # must be thread-safe.

    def resolveEntity(self, publicId, systemId):
        if systemId.lower().startswith(('http://', 'https://')):
            systemId = BytesIO(self.loadRemote(systemId).encode('ascii'))
        return systemId

    @lru_cache(maxsize=32)
    def loadRemote(self, systemId) -> str:
        data = urllib.request.urlopen(systemId)
        return data.read().decode(data.headers.get_content_charset() or 'ascii')


_caching_entity_resolver = _CachingEntityResolver()


def parseString(string: str, handler: ContentHandler,
                errorHandler=ErrorHandler(),
                forbid_dtd=False, forbid_entities=True,
                forbid_external=True):
    # Copied from defusedxml.sax.parseString

    parser = make_parser()
    parser.setContentHandler(handler)
    parser.setErrorHandler(errorHandler)
    parser.forbid_dtd = forbid_dtd
    parser.forbid_entities = forbid_entities
    parser.forbid_external = forbid_external

    parser.setEntityResolver(_caching_entity_resolver)

    inpsrc = InputSource()
    inpsrc.setByteStream(BytesIO(string))
    parser.parse(inpsrc)
