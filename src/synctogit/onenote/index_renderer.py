import urllib.parse
from typing import Callable, Mapping, Sequence

from synctogit.templates import template_env

from .models import (
    OneNoteNotebook,
    OneNotePageId,
    OneNotePageInfo,
    OneNotePageMetadata,
    OneNoteSectionId,
)

_index_template = template_env.get_template("onenote/index.j2")


def render(
    *,
    notebooks: Sequence[OneNoteNotebook],
    pages: Mapping[OneNoteSectionId, Sequence[OneNotePageInfo]],
    service_metadata: Mapping[OneNotePageId, OneNotePageMetadata],
    write: Callable[[bytes], None],
    notes_dirs: Sequence[str] = ("Notes",)
) -> None:
    page_id_to_url = {
        page_id: _page_url(notes_dirs + page_metadata.dir + (page_metadata.file,))
        for page_id, page_metadata in service_metadata.items()
    }

    t = _index_template.render(
        dict(pages=pages, notebooks=notebooks, page_id_to_url=page_id_to_url)
    )
    write(t.encode())


def _page_url(filesystem_path_parts):
    parts = map(lambda s: urllib.parse.quote(s.encode("utf8")), filesystem_path_parts)
    url = "./" + "/".join(parts)
    return url
