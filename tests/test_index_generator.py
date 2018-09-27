import io
from typing import BinaryIO, Callable

from synctogit.index_generator import generate

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
</style>
</head>
<body>

<div class="left">
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

SAMPLE_NOTES = [
    [
        ('Projects', 'P - _0A (Й)', 'жизнь.04d42576-e960-4184-aade-9798b1fe403f.html'),
        ('Projects', 'P - !Z (Щ)', 'жизнь'),
    ],
    [
        ('Learning', 'Книги', 'мои.b04b7672-f020-4203-ad1e-6c361c35c9ac.html'),
        ('Learning', 'Книги', 'мои'),
    ],
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
</style>
</head>
<body>

<div class="left">
<ul>

<li><a href="./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.b04b7672-f020-4203-ad1e-6c361c35c9ac.html" onclick="return frmLocation('./Notes/Learning/%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8/%D0%BC%D0%BE%D0%B8.b04b7672-f020-4203-ad1e-6c361c35c9ac.html');">Learning &rarr; Книги &rarr; мои</a></li>

<li><a href="./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.04d42576-e960-4184-aade-9798b1fe403f.html" onclick="return frmLocation('./Notes/Projects/P%20-%20_0A%20%28%D0%99%29/%D0%B6%D0%B8%D0%B7%D0%BD%D1%8C.04d42576-e960-4184-aade-9798b1fe403f.html');">Projects &rarr; P - !Z (Щ) &rarr; жизнь</a></li>

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
    generate([], memory_writer(buf))
    assert buf.getvalue() == EXPECTED_INDEX_EMPTY_NOTES


def test_index_sample_notes():
    buf = io.BytesIO()
    generate(SAMPLE_NOTES, memory_writer(buf))
    assert buf.getvalue() == EXPECTED_INDEX_SAMPLE_NOTES
