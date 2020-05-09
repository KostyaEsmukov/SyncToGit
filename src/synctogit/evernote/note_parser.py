import re
from typing import Any, Iterable, List, Mapping
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from xml.sax import ContentHandler, SAXParseException

from synctogit.filename_sanitizer import ext_from_mime_type
from synctogit.templates import template_env
from synctogit.xmlutils import parseString

from .exc import EvernoteMalformedNoteError


def _copy_preserve(orig: Mapping[str, Any], preserve: Iterable[str]):
    """Return `preserve` keys from `orig`."""
    return {k: orig[k] for k in preserve if k in orig}


# Add newline after:
_an_pattern = re.compile("<(br|/?html|/?head|/?body|/title|/div)[^>]*>")

# Add newline before:
_bn_pattern = re.compile("<(/head|/body|title)[^>]*>")

_note_tail_template = template_env.get_template("evernote/body_tail.j2")


def resource_filename(file_hash: str, mime_type: str) -> str:
    ext = ext_from_mime_type(mime_type)
    return "%s.%s" % (file_hash, ext)


class _EWrapper:
    """Element wrapper. Contains Element and a required context."""

    def __init__(self, element):
        self.e = element  # type: Element
        self.latest_child = None  # type: '_EWrapper'
        self.en_crypt = False  # type: bool


class _EvernoteNoteParser(ContentHandler):
    def __init__(self, resources_base: str, title: str):
        super().__init__()

        self.resources_base = resources_base

        self.hierarchy = []  # type: List[_EWrapper]
        self.hierarchy.append(_EWrapper(Element("html")))

        self._writeHead(title)

        self.body_started = False
        self.include_encrypted_js = False

    def _writeHead(self, title):
        self._startElement("head")
        self._startElement(
            "meta",
            attrib={
                "content": "text/html; charset=UTF-8",
                "http-equiv": "Content-Type",
            },
        )
        self._endElement()

        self._startElement("title", text=title)
        self._endElement()

        self._endElement()

    def _startElement(self, tag, text=None, attrib=None, **extraattrib):
        z = extraattrib.copy()
        z.update(attrib or {})

        se = _EWrapper(SubElement(self.hierarchy[-1].e, tag, attrib=z))
        self.hierarchy[-1].latest_child = se

        if text is not None:
            se.e.text = text

        self.hierarchy.append(se)

    def _endElement(self):
        self.hierarchy = self.hierarchy[:-1]

    def startElement(self, tag, attrs):
        # https://dev.evernote.com/doc/articles/enml.php

        attrs = attrs.copy()
        attrs = dict(attrs)

        # todo in-app note links https://dev.evernote.com/doc/articles/note_links.php

        if tag == "en-note":
            if "style" not in attrs:
                attrs["style"] = (
                    "word-wrap: break-word; "
                    "-webkit-nbsp-mode: space; "
                    "-webkit-line-break: after-white-space;"
                )

            attrs.pop("xmlns", 0)

            self._startElement("body", attrib=attrs)
            self.body_started = True
        else:
            if not self.body_started:
                raise EvernoteMalformedNoteError(
                    "Malformed note: tag %s appeared before en-note" % tag
                )
            self._processTag(tag, attrs)

    def endElement(self, tag):
        self._endElement()

    def characters(self, content):
        current_el = self.hierarchy[-1]
        if current_el.en_crypt:
            current_el.e.attrib["data-body"] += content
            return

        if current_el.latest_child is None:
            if current_el.e.text is None:
                current_el.e.text = ""
            current_el.e.text += content
            return

        if current_el.latest_child.e.tail is None:
            current_el.latest_child.e.tail = ""
        current_el.latest_child.e.tail += content

    def _processTag(self, tag, attrs):
        m = {
            "en-todo": self._processTagEnTodo,
            "en-media": self._processTagEnMedia,
            "en-crypt": self._processTagEnCrypt,
        }
        if tag in m:
            m[tag](attrs)
        else:
            self._startElement(tag, attrib=attrs)

    def _processTagEnTodo(self, attrs):
        a = {}

        if attrs["checked"].lower() in ("true", "checked"):
            a["checked"] = "checked"

        a.update({"disabled": "disabled", "type": "checkbox"})

        self._startElement("input", attrib=a)

    def _processTagEnMedia(self, attrs):
        # https://dev.evernote.com/doc/reference/Limits.html

        # "image/gif", "image/jpeg", "image/png"
        # "audio/wav", "audio/mpeg", "audio/amr", "audio/aac", "audio/mp4"
        # "application/vnd.evernote.ink"
        # "application/pdf"
        # "video/mp4"

        # "application/msword", "application/mspowerpoint", "application/excel"
        #
        # "application/vnd.ms-word", "application/vnd.ms-powerpoint", "application/vnd.ms-excel"  # noqa: E501
        #
        # "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # noqa: E501
        # "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # noqa: E501
        # "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        #
        # "application/vnd.apple.pages", "application/vnd.apple.numbers", "application/vnd.apple.keynote",  # noqa: E501
        # "application/x-iwork-pages-sffpages", "application/x-iwork-numbers-sffnumbers",  # noqa: E501
        # "application/x-iwork-keynote-sffkey"

        toptype, _ = attrs["type"].split("/", 2)

        src = "%s%s" % (
            self.resources_base,
            resource_filename(attrs["hash"], attrs["type"]),
        )
        if toptype == "image":
            a = _copy_preserve(attrs, ["alt", "style", "width", "height"])
            a["src"] = src
            self._startElement("img", attrib=a)
        else:
            # TODO other types

            self._startElement("a", text="Document of type " + attrs["type"], href=src)

    def _processTagEnCrypt(self, attrs):
        self.include_encrypted_js = True

        a = {
            "data-body": "",
        }
        for k in ["cipher", "hint", "length"]:
            if k in attrs:
                a["data-" + k] = attrs[k]
        a.update({"href": "#", "onclick": "return evernote_decrypt(this);"})

        self._startElement(
            "a", text="Encrypted content. Click here to decrypt.", attrib=a
        )
        self.hierarchy[-1].en_crypt = True

    def getResult(self) -> bytes:  # utf8-encoded
        if len(self.hierarchy) != 1:  # pragma: no cover
            raise RuntimeError(
                "Note is not parsed yet: hierarchy size is %d" % len(self.hierarchy)
            )

        r = ElementTree.tostring(
            self.hierarchy[0].e,
            encoding="unicode",
            # method="html",  # XXX uncomment this?
        )

        r = _an_pattern.sub(lambda m: m.group(0) + "\n", r)
        r = _bn_pattern.sub(lambda m: "\n" + m.group(0), r)

        r = r.encode("utf8")

        tail = _note_tail_template.render(
            dict(include_encrypted_js=self.include_encrypted_js)
        )

        r = r.replace(b"</body>", tail.encode("utf8") + b"</body>", 1)
        return r


def parse(resources_base_path: str, enbody: str, title: str) -> bytes:
    p = _EvernoteNoteParser(resources_base_path, title)

    try:
        parseString(
            enbody, p, forbid_dtd=False, forbid_entities=False, forbid_external=False,
        )
    except SAXParseException as e:
        raise EvernoteMalformedNoteError(e)

    return p.getResult()
