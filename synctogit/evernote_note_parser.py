from __future__ import absolute_import

import os
import re
from xml.sax import ContentHandler
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement

import defusedxml.sax as sax


def _copy_preserve(orig, preserve, merge=None):
    # return keys $preserve from $orig and merge with $merge
    res = {}
    for k in preserve:
        if k in orig:
            res[k] = orig[k]

    res.update(merge or {})

    return res


def _get_file_contents(p):  # relative to this file path
    tp = os.path.realpath(os.path.dirname(os.path.realpath(__file__)) + os.sep + u'' + p)
    with open(tp, "rb") as f:
        s = f.read()
    return s


_ENCRYPTED_JS = """


// This is a set of scripts required for decrypting encrypted content. Please don't touch it.


function evernote_decrypt(o) {
    var h = o.dataset.hint ? " Hint: " + o.dataset.hint : "";
    var p = prompt("Enter the passphrase." + h);
    try {
        o.outerHTML = decrypt(o.dataset.cipher || "AES", o.dataset.length, p, o.dataset.body);
    }
    catch(e) {
        alert("Failed: " + e);
    }
    return false;
}

""" + _get_file_contents("js/decrypt.min.js")

_AN_PATTERN = re.compile("<(br|/?html|/?head|/?body|/title|/div)[^>]*>")
_BN_PATTERN = re.compile("<(/head|/body|title)[^>]*>")

_ENTITY_PATTERN = re.compile("&#?\w+;")


def _unescape_entities(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        return text  # leave as is

    return _ENTITY_PATTERN.sub(fixup, text)


class _EWrapper:
    def __init__(self, e):
        self.e = e
        self.st = {}


class _EvernoteNoteParser(ContentHandler):
    def __init__(self, resources_base, title):
        ContentHandler.__init__(self)

        self.resources_base = resources_base

        self.hierarchy = []
        self.hierarchy.append(_EWrapper(Element("html")))
        self.hierarchy[0].st['latest_child'] = None

        self._startElement("head")
        self._startElement("meta", attrib={'http-equiv': 'Content-Type', 'content': 'text/html; charset=UTF-8'})
        self._endElement()

        self._startElement("title", text=title)
        self._endElement()

        self._endElement()

        self.body_started = False
        self.include_encrypted_js = False

    def _startElement(self, tag, text=None, attrib=None, **extraattrib):
        z = extraattrib.copy()
        z.update(attrib or {})

        se = _EWrapper(SubElement(self.hierarchy[-1].e, tag, attrib=z))
        se.st['latest_child'] = None
        self.hierarchy[-1].st['latest_child'] = se

        if text is not None:
            se.e.text = text

        self.hierarchy.append(se)

    def _endElement(self):
        self.hierarchy = self.hierarchy[:-1]

    def _text(self, t):
        if self.hierarchy[-1].st['latest_child'] is None:
            if self.hierarchy[-1].e.text is None:
                self.hierarchy[-1].e.text = t
            else:
                self.hierarchy[-1].e.text += t
        else:
            if self.hierarchy[-1].st['latest_child'].e.tail is None:
                self.hierarchy[-1].st['latest_child'].e.tail = t
            else:
                self.hierarchy[-1].st['latest_child'].e.tail += t

    def startElement(self, tag, attrs):
        # https://dev.evernote.com/doc/articles/enml.php

        attrs = attrs.copy()
        attrs = dict(attrs)

        # todo in-app note links https://dev.evernote.com/doc/articles/note_links.php

        if tag == "en-note":
            if 'style' not in attrs:
                attrs['style'] = 'word-wrap: break-word;' \
                                 + ' -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;'

            attrs.pop('xmlns', 0)

            self._startElement("body", attrib=attrs)
            self.body_started = True
        else:
            if not self.body_started:
                raise Exception('Malformed note: tag %s appeared before en-note' % tag)

            if tag == 'en-todo':
                a = {'type': "checkbox", 'disabled': "disabled"}

                if attrs['checked'].lower() in ("true", "checked"):
                    a['checked'] = 'checked'
                self._startElement("input", attrib=a)

            elif tag == 'en-media':
                # https://dev.evernote.com/doc/reference/Limits.html

                # "image/gif", "image/jpeg", "image/png"
                # "audio/wav", "audio/mpeg", "audio/amr", "audio/aac", "audio/mp4"
                # "application/vnd.evernote.ink"
                # "application/pdf"
                # "video/mp4"

                # "application/msword", "application/mspowerpoint", "application/excel"
                #
                # "application/vnd.ms-word", "application/vnd.ms-powerpoint", "application/vnd.ms-excel"
                #
                # "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                # "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                # "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                #
                # "application/vnd.apple.pages", "application/vnd.apple.numbers", "application/vnd.apple.keynote",
                # "application/x-iwork-pages-sffpages", "application/x-iwork-numbers-sffnumbers",
                # "application/x-iwork-keynote-sffkey"

                toptype, subtype = attrs['type'].split('/', 2)

                src = ''.join([self.resources_base, attrs['hash'], ".", subtype])
                if toptype == "image":
                    a = _copy_preserve(attrs, ["alt", "style", "width", "height"], {'src': src})
                    self._startElement("img", attrib=a)
                else:
                    # TODO other types

                    self._startElement("a", text="Document of type " + attrs['type'], href=src)

            elif tag == 'en-crypt':
                self.include_encrypted_js = True

                a = {
                    'href': '#',
                    'onclick': 'return evernote_decrypt(this);',
                    'data-body': ''
                }
                for k in ['cipher', 'length', 'hint']:
                    if k in attrs:
                        a['data-' + k] = attrs[k]

                self._startElement("a", text="Encrypted content. Click here to decrypt.", attrib=a)
                self.hierarchy[-1].st['en-crypt'] = True
            else:
                self._startElement(tag, attrib=attrs)

    def endElement(self, tag):
        self._endElement()

    def characters(self, content):
        if 'en-crypt' in self.hierarchy[-1].st and self.hierarchy[-1].st['en-crypt']:
            self.hierarchy[-1].e.attrib['data-body'] += content
        else:
            self._text(content)

    def getResult(self):  # utf8-encoded
        if len(self.hierarchy) != 1:
            raise Exception("Note is not parsed yet: hierarchy size is %d" % len(self.hierarchy))

        r = ElementTree.tostring(self.hierarchy[0].e)

        r = _AN_PATTERN.sub(lambda m: m.group(0) + "\n", r)
        r = _BN_PATTERN.sub(lambda m: "\n" + m.group(0), r)

        r = _unescape_entities(r)
        r = r.encode("utf8")

        if self.include_encrypted_js:
            # avoid dealing with XML text escapes
            r = r.replace("</body>", "<script>" + _ENCRYPTED_JS + "</script></body>", 1)
        return r


def parse(resources_base_path, enbody, title):
    p = _EvernoteNoteParser(resources_base_path, title)
    sax.parseString(enbody, p, forbid_dtd=False, forbid_entities=False, forbid_external=False)

    return p.getResult()
