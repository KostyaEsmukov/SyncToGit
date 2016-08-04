# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import urllib
from xml.sax.saxutils import escape

_note_el = """<li><a href="%(url)s" onclick="return frmLocation('%(url)s');">%(text)s</a></li>"""

_index_html = """
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
{NOTES_LIST}
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
"""


def generate(notes, output_filepath):
    output_filepath = os.path.realpath(output_filepath)

    r = []
    for l in notes:
        text = ' &rarr; '.join(map(escape, l[1]))

        parts = map(lambda s: urllib.quote(s.encode("utf8")), ["Notes"] + l[0])
        url = './' + '/'.join(parts)

        r.append(_note_el % {'text': text, 'url': url})

    r = sorted(r)

    b = _index_html.replace("{NOTES_LIST}", '\n'.join(r))

    with open(output_filepath, 'wb') as f:
        f.write(b.encode("utf8"))
