from pathlib import Path
from typing import Mapping, Optional

import pytest

from synctogit.onenote import oauth
from synctogit.onenote.models import OneNoteResource
from synctogit.onenote.page_parser import PageParser, ResourceRetrieval, _is_empty_inkml

data_path = Path(__file__).parents[0] / "data"


class DummyResourceRetrieval(ResourceRetrieval):
    def __init__(self):
        self.queue = {}

    def maybe_queue(self, url: str) -> Optional[str]:
        url_pattern = oauth.resource_url_pattern
        match = url_pattern.match(url)
        if not match:
            return None
        resource_id = match.group(1)
        self.queue[resource_id] = ("test data|" + resource_id).encode()
        return resource_id

    def retrieve_all(self) -> Mapping[str, bytes]:
        return self.queue


@pytest.mark.parametrize(
    "is_empty, inkml",
    [
        (True, None),
        (True, (data_path / "page_parser_inkml_empty.xml").read_text()),
        (False, (data_path / "page_parser_inkml_dot.xml").read_text()),
    ],
)
def test_is_empty_inkml(is_empty, inkml):
    assert is_empty is _is_empty_inkml(inkml)


def test_full_html():  # without inkml
    input_html = (data_path / "page_parser_full_input.html").read_text()
    output_html = (data_path / "page_parser_full_output.html").read_text()

    rr = DummyResourceRetrieval()
    p = PageParser(
        html=input_html,
        inkml=None,
        resource_retrieval=rr,
        resources_base=(
            "../../Resources/"
            "0-111aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999"
        ),
    )

    assert p.html.decode() == output_html
    assert p.resources == {
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa0af!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa0af!1-AAAAAAAAAAAAAAA!999",
            mime="image/png",
            filename=(
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa0af_00211-AAAAAAAAAAAAAAA_0021999.png"
            ),
        ),
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa193!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa193!1-AAAAAAAAAAAAAAA!999",
            mime="application/javascript",
            filename=(
                "t."
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa193_00211-AAAAAAAAAAAAAAA_0021999.js"
            ),
        ),
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa399!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa399!1-AAAAAAAAAAAAAAA!999",
            mime="video/mp4",
            filename=(
                "Audio 1."
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa399_00211-AAAAAAAAAAAAAAA_0021999.mp4"
            ),
        ),
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa3e4!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa3e4!1-AAAAAAAAAAAAAAA!999",
            mime="image/png",
            filename=(
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa3e4_00211-AAAAAAAAAAAAAAA_0021999.png"
            ),
        ),
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa481!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa481!1-AAAAAAAAAAAAAAA!999",
            mime="image/png",
            filename=(
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa481_00211-AAAAAAAAAAAAAAA_0021999.png"
            ),
        ),
        "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa8ea!1-AAAAAAAAAAAAAAA!999": OneNoteResource(
            body=b"test data|0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa8ea!1-AAAAAAAAAAAAAAA!999",
            mime="application/pdf",
            filename=(
                "1 - log."
                "0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaa8ea_00211-AAAAAAAAAAAAAAA_0021999.pdf"
            ),
        ),
    }
