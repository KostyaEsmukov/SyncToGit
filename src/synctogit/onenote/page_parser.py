import abc
import logging
import os
import xml.etree.ElementTree as ET
from typing import Mapping, NamedTuple, Optional, Sequence

from bs4 import BeautifulSoup as bs, Comment, Tag
from cached_property import cached_property
from requests_toolbelt.multipart import decoder

from synctogit.filename_sanitizer import ext_from_mime_type, normalize_filename
from synctogit.templates import template_env

from .models import OneNoteResource

logger = logging.getLogger(__name__)

_page_tail_template = template_env.get_template("onenote/body_tail.j2")


def _is_empty_inkml(inkml: Optional[str]):
    if not inkml:
        return True

    root = ET.fromstring(inkml)
    # https://stackoverflow.com/q/14853243
    tg = root.find("./{http://www.w3.org/2003/InkML}traceGroup")
    return not bool(list(tg))


class ResourceRetrieval(abc.ABC):
    @abc.abstractmethod
    def maybe_queue(self, url) -> Optional[str]:  # resource_id
        pass

    @abc.abstractmethod
    def retrieve_all(self) -> Mapping[str, bytes]:
        pass


class PageParser:
    def __init__(
        self,
        *,
        html: str,
        inkml: str,
        resource_retrieval: ResourceRetrieval,
        resources_base: str
    ) -> None:
        self._raw_html = html
        self._raw_inkml = inkml
        self._resource_retrieval = resource_retrieval
        self._resources_base = resources_base

    @classmethod
    def from_multipart(
        cls,
        multipart_data: decoder.MultipartDecoder,
        *,
        resource_retrieval: ResourceRetrieval,
        resources_base: str
    ) -> "PageParser":
        html = None
        inkml = None
        for part in multipart_data.parts:
            text = part.text
            content_type = part.headers.get(b"content-type", b"").decode().lower()

            if "text/html" in content_type:
                if html is not None:
                    raise ValueError("Multiple html parts received")
                html = text
            elif "application/inkml+xml" in content_type:
                if inkml is not None:
                    raise ValueError("Multiple inkml parts received")
                inkml = text
            else:
                raise ValueError("Unknown content-type '%s' or a part" % content_type)

        if html is None:
            raise ValueError("HTML part hasn't been received")

        if _is_empty_inkml(inkml):
            inkml = None

        return cls(
            html=html,
            inkml=inkml,
            resource_retrieval=resource_retrieval,
            resources_base=resources_base,
        )

    @property
    def html(self) -> bytes:
        return self._parsed.html

    @property
    def resources(self) -> Mapping[str, OneNoteResource]:
        return self._parsed.resources

    @cached_property
    def _parsed(self) -> "_Parsed":
        soup = bs(self._raw_html, "html.parser")
        self._bleach_html(soup)
        resources = self._process_resources(soup)
        html = soup.prettify(formatter="html5")

        html = self._insert_page_tail(html)
        html = html.replace("\r\n", "\n").encode("utf8")

        return _Parsed(html=html, resources=resources)

    def _bleach_html(self, soup: bs) -> None:
        # Strip `<!-- InkNode is not supported -->` comments:
        comments = soup.findAll(text=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()

    def _insert_page_tail(self, html: str):
        inkml = self._raw_inkml

        tail = _page_tail_template.render(dict(inkml=inkml))

        if "</body>" not in html:
            raise ValueError("HTML part doesn't contain the '</body>' tag")
        html = html.replace("</body>", tail + "</body>")
        return html

    def _process_resources(self, soup: bs):
        p = _ParseResources(self._resource_retrieval, self._resources_base)
        return p.parse(soup)


class _ParseResources:
    def __init__(
        self, resource_retrieval: ResourceRetrieval, resources_base: str
    ) -> None:
        self._resource_retrieval = resource_retrieval
        self._resources_base = resources_base
        self.resource_id_to_meta = {}  # type: Mapping[str, Mapping[str, str]]

    def parse(self, soup: bs):
        for img_tag in soup.find_all("img"):
            self._handle_img_tag(img_tag, soup)

        for object_tag in soup.find_all("object"):
            # Documents (pdf), videos
            self._handle_object_tag(object_tag, soup)

        resource_id_to_body = self._resource_retrieval.retrieve_all()

        return {
            resource_id: OneNoteResource(
                body=resource_id_to_body[resource_id],
                mime=meta["mime"],
                filename=meta["filename"],
            )
            for resource_id, meta in self.resource_id_to_meta.items()
        }

    def _handle_img_tag(self, img_tag: Tag, soup: bs) -> None:
        self._handle_resource(
            img_tag,
            src_attrs=("data-fullres-src", "src"),
            mime_attrs=("data-fullres-src-type", "data-src-type"),
            filename_attrs=tuple(),
            final_src_attr="src",
            final_mime_attr="data-src-type",
        )

    def _handle_object_tag(self, object_tag: Tag, soup: bs) -> None:
        handled = self._handle_resource(
            object_tag,
            src_attrs=("data",),
            mime_attrs=("type",),
            filename_attrs=("data-attachment",),
            final_src_attr="data",
            final_mime_attr="type",
        )
        if handled.is_onenote and object_tag["type"].startswith("video"):
            # Replace `object` tag with `video`.
            video_tag = soup.new_tag(
                "video",
                controls="",
                **{k: v for k, v in object_tag.attrs.items() if k.startswith("data-")}
            )
            style = object_tag.get("style")
            if style:
                video_tag["style"] = style

            video_tag.append(
                soup.new_tag("source", type=object_tag["type"], src=object_tag["data"])
            )

            object_tag.replace_with(video_tag)
        else:
            # Insert an `a` link before the object.
            a_tag = soup.new_tag("a", href=object_tag["data"])
            a_tag.string = handled.a_link_text
            if object_tag.get("style"):
                # `style` looks like
                # "position:absolute;left:48px;top:1099px".
                a_tag["style"] = object_tag["style"].rstrip(";") + ";margin-top:-20px;"
            object_tag.insert_before(a_tag)

    def _handle_resource(
        self,
        tag: Tag,
        *,
        src_attrs: Sequence[str],
        mime_attrs: Sequence[str],
        filename_attrs: Sequence[str],
        final_src_attr: str,
        final_mime_attr: str
    ) -> "_HandledResource":
        src = self._first(tag, src_attrs)
        a_link_text = "Document at %s" % src

        resource_id = self._resource_retrieval.maybe_queue(src)
        if not resource_id:
            return _HandledResource(is_onenote=False, a_link_text=a_link_text)

        mime_type = self._first(tag, mime_attrs)
        a_link_text = "Document of type %s" % mime_type

        original_filename = self._first(tag, filename_attrs, empty_raises=False)
        filename = self._resource_filename(resource_id, mime_type, original_filename)
        if original_filename:
            a_link_text = "Document %s" % original_filename

        for attr in src_attrs + mime_attrs:
            del tag[attr]

        tag[final_mime_attr] = mime_type
        tag[final_src_attr] = os.path.join(self._resources_base, filename)

        self.resource_id_to_meta[resource_id] = dict(filename=filename, mime=mime_type)
        return _HandledResource(is_onenote=True, a_link_text=a_link_text)

    def _first(
        self, tag: Tag, candidate_attrs: Sequence[str], *, empty_raises=True
    ) -> str:
        iterator = (tag[attr] for attr in candidate_attrs if tag.get(attr))
        attr_value = next(iterator, None)
        if empty_raises and attr_value is None:
            raise KeyError(
                "None of the %r attributes are set on %s" % (candidate_attrs, tag)
            )
        return attr_value

    def _resource_filename(
        self, resource_id: str, mime_type: str, original_filename: Optional[str]
    ) -> str:
        # resource_id looks like
        # "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa399!1-AAAAAAAAAAAAAAA!999"
        if original_filename and "." in original_filename:
            name, ext = original_filename.rsplit(".", 1)
            filename = "%s.%s.%s" % (name, resource_id, ext)
        else:
            ext = ext_from_mime_type(mime_type)
            filename = "%s.%s" % (resource_id, ext)
        return normalize_filename(filename)


_Parsed = NamedTuple(
    "_Parsed",
    [
        # fmt: off
        ("html", bytes),
        ("resources", Mapping[str, OneNoteResource]),
        # fmt: on
    ],
)


_HandledResource = NamedTuple(
    "_HandledResource",
    [
        # fmt: off
        ("is_onenote", bool),
        ("a_link_text", str),
        # fmt: on
    ],
)
