import datetime
import logging
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Union

import dateutil.parser

from synctogit.filename_sanitizer import normalize_filename

from . import oauth
from .client import OauthClient, OneNoteAPI
from .exc import EncryptedSectionError
from .models import (
    OneNoteNotebook,
    OneNotePage,
    OneNotePageId,
    OneNotePageInfo,
    OneNotePageMetadata,
    OneNoteSection,
    OneNoteSectionId,
)
from .page_parser import PageParser, ResourceRetrieval

logger = logging.getLogger(__name__)

_MAXLEN_TITLE_FILENAME = 30


class OneNoteOrder(Enum):
    name = "name"
    reversed_name = "-name"
    created = "created"
    reversed_created = "-created"
    last_modified = "last_modified"
    reversed_last_modified = "-last_modified"


class OneNoteClient:
    # Must be threadsafe

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token: Dict[str, Any],
        notebooks_order: OneNoteOrder = OneNoteOrder.created,
        sections_order: OneNoteOrder = OneNoteOrder.created
    ) -> None:
        # NB: REST API limitations:
        # - no colors
        # - no order of notebooks and sections
        # - no encrypted notes
        #
        # Alternatives:
        # - read the .one files directly (but it seems to be impossible
        #   to retrieve them using any of the Microsoft's public API)
        # - communicate with the running one note (but it requires
        #   the MS Office version of OneNote)

        client = OauthClient(
            client_id=client_id, client_secret=client_secret, token=token,
        )
        self._api = OneNoteAPI(client)

        self.notebooks_order = notebooks_order
        self.sections_order = sections_order

        self.notebooks = None  # type: Sequence[OneNoteNotebook]
        self.section_to_pages = (
            None
        )  # type: Mapping[OneNoteSectionId, Sequence[OneNotePageInfo]]  # noqa
        self.metadata = None  # type: Mapping[OneNotePageId, OneNotePageMetadata]
        self._page_id_to_section_id = (
            None
        )  # type: Mapping[OneNoteSectionId, OneNotePageId]  # noqa

    @property
    def token(self) -> Dict[str, Any]:
        return self._api._client.get_token()

    def sync_metadata(self) -> None:
        # XXX ensure they're converged?
        self.notebooks = self._get_notebooks()
        self.section_to_pages = self._get_pages_of_notebooks(self.notebooks)
        self.metadata = self._metadata_from_pages(self.notebooks, self.section_to_pages)
        self._page_id_to_section_id = self._get_page_id_to_section_id(
            self.section_to_pages
        )

    def get_page(self, page_id: OneNotePageId, resources_base: str) -> OneNotePage:
        # XXX ensure they're converged?
        multipart_data = self._api.get_page_html(page_id)

        resource_retrieval = _PageResourceRetrieval(self._api._client)
        try:
            page_parser = PageParser.from_multipart(
                multipart_data,
                resource_retrieval=resource_retrieval,
                resources_base=resources_base,
            )
        except ValueError as e:
            raise ValueError(
                "Unable to parse multipart data for page "
                "'%s': %s" % (page_id, str(e))
            )

        section_id = self._page_id_to_section_id.get(page_id)
        info = self._map_page_info(self._api.get_page_info(page_id, section_id))
        try:
            return OneNotePage(
                info=info, html=page_parser.html, resources=page_parser.resources,
            )
        except ValueError as e:
            raise ValueError(
                "Unable to parse html data for page '%s': %s" % (page_id, str(e))
            )

    def _metadata_from_pages(
        self,
        notebooks: Sequence[OneNoteNotebook],
        section_to_pages: Mapping[OneNoteSectionId, Sequence[OneNotePageInfo]],
    ) -> Mapping[OneNotePageId, OneNotePageMetadata]:
        metadata = OrderedDict()

        section_id_to_dir = {
            section.id: [notebook.name, section.name]
            for notebook in notebooks
            for section in notebook.sections
        }

        for section_id, page_info_seq in section_to_pages.items():
            for page_info in page_info_seq:
                page_id = page_info.id

                note_location = section_id_to_dir[section_id] + [page_info.title]
                file = normalize_filename(
                    "%s.%s.html" % (page_info.title[:_MAXLEN_TITLE_FILENAME], page_id)
                )
                normalized_note_location = [
                    normalize_filename(s) for s in note_location
                ]

                metadata[page_id] = OneNotePageMetadata(
                    dir=tuple(normalized_note_location[:-1]),
                    name=tuple(note_location),
                    file=file,
                    last_modified=page_info.last_modified,
                )

        return metadata

    def _get_page_id_to_section_id(
        self, section_to_pages: Mapping[OneNoteSectionId, Sequence[OneNotePageInfo]]
    ) -> Mapping[OneNoteSectionId, OneNotePageId]:
        return {
            page_info.id: section_id
            for section_id, page_infos in section_to_pages.items()
            for page_info in page_infos
        }

    def _get_notebooks(self) -> Sequence[OneNoteNotebook]:
        return self._sort_notebooks_sections(
            self.notebooks_order,
            [
                OneNoteNotebook(
                    id=str(notebook["id"]),
                    created=self._map_datetime(notebook["createdDateTime"]),
                    last_modified=self._map_datetime(notebook["lastModifiedDateTime"]),
                    name=str(notebook["displayName"]),
                    is_default=bool(notebook["isDefault"]),
                    sections=self._sort_notebooks_sections(
                        self.sections_order,
                        [
                            OneNoteSection(
                                id=str(section["id"]),
                                created=self._map_datetime(section["createdDateTime"]),
                                last_modified=self._map_datetime(
                                    section["lastModifiedDateTime"]
                                ),
                                name=str(section["displayName"]),
                                is_default=bool(section["isDefault"]),
                            )
                            for section in notebook["sections"]
                        ],
                    ),
                )
                for notebook in self._api.get_notebooks()
            ],
        )

    def _map_datetime(self, dt: str) -> datetime.datetime:
        # 2018-09-22T16:42:29.61Z
        return dateutil.parser.parse(dt)

    def _sort_notebooks_sections(
        self, order: OneNoteOrder, lst: Sequence[Union[OneNoteNotebook, OneNoteSection]]
    ):
        reverse = order.value[0] == "-"

        def key(m):
            if reverse:
                return m.is_default, getattr(m, order.value[1:])
            else:
                return not m.is_default, getattr(m, order.value)

        return sorted(lst, key=key, reverse=reverse)

    def _get_pages_of_notebooks(
        self, notebooks: Sequence[OneNoteNotebook]
    ) -> Mapping[OneNoteSectionId, Sequence[OneNotePageInfo]]:
        section_to_pages = defaultdict(lambda: [])

        for notebook in notebooks:
            for section in notebook.sections:
                try:
                    section_to_pages[section.id].extend(
                        self._api.get_pages_of_section(section.id)
                    )
                except EncryptedSectionError:
                    logger.info("Skipping encrypted section '%s'", section.name)

        return {
            section_id: [
                self._map_page_info(page)
                for page in sorted(pages, key=lambda p: p["order"])
            ]
            for section_id, pages in section_to_pages.items()
        }

    def _map_page_info(self, page: Dict[str, Any]) -> OneNotePageInfo:
        return OneNotePageInfo(
            id=str(page["id"]),
            created=self._map_datetime(page["createdDateTime"]),
            last_modified=self._map_datetime(page["lastModifiedDateTime"]),
            title=str(page["title"]) or "Untitled Page",
        )


class _PageResourceRetrieval(ResourceRetrieval):
    resource_url_pattern = oauth.resource_url_pattern
    max_threads = 6

    def __init__(self, client: OauthClient) -> None:
        self._client = client
        self.resource_id_to_url = {}  # type: Dict[str, str]

    def maybe_queue(self, url: str) -> Optional[str]:
        match = self.resource_url_pattern.match(url)
        if not match:
            return None
        resource_id = match.group(1)
        self.resource_id_to_url[resource_id] = url
        return resource_id

    def retrieve_all(self) -> Mapping[str, bytes]:
        keys_values = list(zip(*self.resource_id_to_url.items()))
        if not keys_values:
            return {}

        with ThreadPoolExecutor(max_workers=self.max_threads) as pool:
            resource_ids, urls = keys_values
            return dict(zip(resource_ids, pool.map(self._retrieve, urls)))

    def _retrieve(self, url: str) -> bytes:
        r = self._client.get(url)
        return r.content
