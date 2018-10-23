import datetime
import io
from typing import BinaryIO, Callable

import pytz

from synctogit.onenote.index_renderer import render
from synctogit.onenote.models import (
    OneNoteNotebook,
    OneNotePageInfo,
    OneNotePageMetadata,
    OneNoteSection,
)

timezone = pytz.timezone("Europe/Moscow")
dt_tzaware = timezone.localize(datetime.datetime.now())


EXPECTED_INDEX_EMPTY_PAGES = """
<!doctype html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>SyncToGit index</title>

<style>
html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
}
.left, .right {
    height: 100%;
    float: left;
    box-sizing: border-box;
}
.left ul {
    margin: 0;
    padding-left: 10px;
}
.left {
    width: 20%;
    overflow-y: scroll;
    padding: 10px;
}
.right {
    width: 80%;
}
.left a {
    margin: 5px 5px;
}
#frm {
    width: 100%;
    height: 100%;
}
.tree, .tree ul, .tree li {
     position: relative;
}
.tree ul {
    list-style: none;
    padding-left: 20px;
}
.tree li::before, .tree li::after {
    content: "";
    position: absolute;
    left: -12px;
}
.tree li::before {
    border-top: 1px solid #000;
    top: 9px;
    width: 8px;
    height: 0;
}
.tree li::after {
    border-left: 1px solid #000;
    height: 100%;
    width: 0px;
    top: 2px;
}
.tree ul > li:last-child::after {
    height: 8px;
}
</style>
</head>
<body>

<div class="left tree">
<ul>

</ul>
</div>

<div class="right">
<iframe id="frm"></iframe>
</div>

<script>
var frmLocation = (function() {
    var frm = document.getElementById("frm");
    return function(l) {
        frm.src = l;
        return false;
    }
})();
</script>
</body>
</html>
""".encode("utf8")


SAMPLE_PAGES = dict(
    notebooks=[
        OneNoteNotebook(
            id='n1',
            name='Learning',
            created=dt_tzaware,
            last_modified=dt_tzaware,
            is_default=False,
            sections=[
                OneNoteSection(
                    id='s1',
                    name='Книги',
                    created=dt_tzaware,
                    last_modified=dt_tzaware,
                    is_default=False,
                )
            ]
        ),
        OneNoteNotebook(
            id='n2',
            name='Projects',
            created=dt_tzaware,
            last_modified=dt_tzaware,
            is_default=True,
            sections=[
                OneNoteSection(
                    id='s2',
                    name='P - !Z (Щ) <>',
                    created=dt_tzaware,
                    last_modified=dt_tzaware,
                    is_default=True,
                )
            ]
        ),
    ],
    pages={
        's1': [
            OneNotePageInfo(
                id='0-111aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999',
                title='мои',
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
            OneNotePageInfo(
                id='0-222aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999',
                title='не мои',
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
        ],
        's2': [
            OneNotePageInfo(
                id='0-333aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999',
                title='жизнь',
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
        ],
    },
    service_metadata={
        '0-111aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999': OneNotePageMetadata(
            dir=("Learning", "Книги"),
            file="мои.0-111aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Learning", "Книги", "мои"),
            last_modified=dt_tzaware,
        ),
        '0-222aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999': OneNotePageMetadata(
            dir=("Learning", "Книги"),
            file="не мои.0-222aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Learning", "Книги", "не мои"),
            last_modified=dt_tzaware,
        ),
        '0-333aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999': OneNotePageMetadata(
            dir=("Projects", "P - _0A (Й)"),
            file="жизнь.0-333aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Projects", "P - !Z (Щ) <>", "жизнь"),
            last_modified=dt_tzaware,
        ),
    },
)

EXPECTED_INDEX_SAMPLE_PAGES = """
<!doctype html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>SyncToGit index</title>

<style>
html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
}
.left, .right {
    height: 100%;
    float: left;
    box-sizing: border-box;
}
.left ul {
    margin: 0;
    padding-left: 10px;
}
.left {
    width: 20%;
    overflow-y: scroll;
    padding: 10px;
}
.right {
    width: 80%;
}
.left a {
    margin: 5px 5px;
}
#frm {
    width: 100%;
    height: 100%;
}
.tree, .tree ul, .tree li {
     position: relative;
}
.tree ul {
    list-style: none;
    padding-left: 20px;
}
.tree li::before, .tree li::after {
    content: "";
    position: absolute;
    left: -12px;
}
.tree li::before {
    border-top: 1px solid #000;
    top: 9px;
    width: 8px;
    height: 0;
}
.tree li::after {
    border-left: 1px solid #000;
    height: 100%;
    width: 0px;
    top: 2px;
}
.tree ul > li:last-child::after {
    height: 8px;
}
</style>
</head>
<body>

<div class="left tree">
<ul>

    <li><span title="Learning">Learning</span>
        <ul>

            <li><span title="Learning &rarr; Книги">Книги</span>
                <ul>

                    <li><a title="Learning &rarr; Книги &rarr; мои" href="./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.0-111aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html" onclick="return frmLocation('./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.0-111aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html');">мои</a></li>

                    <li><a title="Learning &rarr; Книги &rarr; не мои" href="./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BD%D0%B5%20%D0%BC%D0%BE%D0%B8.0-222aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html" onclick="return frmLocation('./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BD%D0%B5%20%D0%BC%D0%BE%D0%B8.0-222aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html');">не мои</a></li>

                </ul>
            </li>

        </ul>
    </li>

    <li><span title="Projects">Projects</span>
        <ul>

            <li><span title="Projects &rarr; P - !Z (Щ) &lt;&gt;">P - !Z (Щ) &lt;&gt;</span>
                <ul>

                    <li><a title="Projects &rarr; P - !Z (Щ) &lt;&gt; &rarr; жизнь" href="./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.0-333aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html" onclick="return frmLocation('./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.0-333aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html');">жизнь</a></li>

                </ul>
            </li>

        </ul>
    </li>

</ul>
</div>

<div class="right">
<iframe id="frm"></iframe>
</div>

<script>
var frmLocation = (function() {
    var frm = document.getElementById("frm");
    return function(l) {
        frm.src = l;
        return false;
    }
})();
</script>
</body>
</html>
""".encode("utf8")  # noqa: E501


def memory_writer(buf: BinaryIO) -> Callable[[bytes], None]:
    def write(data: bytes) -> None:
        buf.write(data)
    return write


def test_index_empty_pages():
    buf = io.BytesIO()
    render(
        notebooks=[],
        pages={},
        service_metadata={},
        write=memory_writer(buf)
    )
    assert buf.getvalue() == EXPECTED_INDEX_EMPTY_PAGES


def test_index_sample_pages():
    buf = io.BytesIO()
    render(**SAMPLE_PAGES, write=memory_writer(buf))
    assert buf.getvalue() == EXPECTED_INDEX_SAMPLE_PAGES
