import io
from typing import BinaryIO, Callable

from synctogit.evernote.index_renderer import IndexLink, render

EXPECTED_INDEX_EMPTY_NOTES = """
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

SAMPLE_NOTES = [
    IndexLink(
        filesystem_path_parts=(
            "Projects",
            "P - _0A (Й)",
            "жизнь.04d42576-e960-4184-aade-9798b1fe403f.html",
        ),
        name_parts=("Projects", "P - !Z (Щ) <>", "жизнь"),
    ),
    IndexLink(
        filesystem_path_parts=(
            "Learning",
            "Книги",
            "мои.b04b7672-f020-4203-ad1e-6c361c35c9ac.html",
        ),
        name_parts=("Learning", "Книги", "мои"),
    ),
    IndexLink(
        filesystem_path_parts=(
            "Learning",
            "Книги",
            "не мои.a5ccfd4c-1338-4b92-8339-16ff43390f10.html",
        ),
        name_parts=("Learning", "Книги", "не мои"),
    ),
]

EXPECTED_INDEX_SAMPLE_NOTES = """
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
    <li><span title="Projects">Projects</span>

        <ul>
            <li><span title="Projects &rarr; P - !Z (Щ) &lt;&gt;">P - !Z (Щ) &lt;&gt;</span>

                    <ul>
                        <li><a title="Projects &rarr; P - !Z (Щ) &lt;&gt; &rarr; жизнь" href="./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.04d42576-e960-4184-aade-9798b1fe403f.html" onclick="return frmLocation('./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.04d42576-e960-4184-aade-9798b1fe403f.html');">жизнь</a></li>
                    </ul>

            </li>
        </ul>

    </li>

    <li><span title="Learning">Learning</span>

        <ul>
            <li><span title="Learning &rarr; Книги">Книги</span>

                    <ul>
                        <li><a title="Learning &rarr; Книги &rarr; мои" href="./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.b04b7672-f020-4203-ad1e-6c361c35c9ac.html" onclick="return frmLocation('./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.b04b7672-f020-4203-ad1e-6c361c35c9ac.html');">мои</a></li>

                        <li><a title="Learning &rarr; Книги &rarr; не мои" href="./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BD%D0%B5%20%D0%BC%D0%BE%D0%B8.a5ccfd4c-1338-4b92-8339-16ff43390f10.html" onclick="return frmLocation('./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BD%D0%B5%20%D0%BC%D0%BE%D0%B8.a5ccfd4c-1338-4b92-8339-16ff43390f10.html');">не мои</a></li>
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


def test_index_empty_notes():
    buf = io.BytesIO()
    render([], memory_writer(buf))
    assert buf.getvalue() == EXPECTED_INDEX_EMPTY_NOTES


def test_index_sample_notes():
    buf = io.BytesIO()
    render(SAMPLE_NOTES, memory_writer(buf))
    assert buf.getvalue() == EXPECTED_INDEX_SAMPLE_NOTES
