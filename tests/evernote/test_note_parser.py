import os

import pytest
import vcr

from synctogit.evernote import note_parser
from synctogit.evernote.exc import EvernoteMalformedNoteError

vcr_dtd = vcr.VCR(cassette_library_dir=os.path.dirname(__file__))


@vcr_dtd.use_cassette("cassette_dtd")
def test_simple_parse():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>привет<br /></div>
</en-note>
"""

    expected = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">

<div>привет<br />
</div>


</body>
</html>
"""  # noqa: E501

    html = note_parser.parse(".", note, title="привет")
    assert html.decode() == expected


@vcr_dtd.use_cassette("cassette_dtd")
def test_encrypted():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div><br /></div>
<div>password: password</div>
<div><br /></div>
<div><en-crypt cipher="AES" length="128" hint="password">RU5DMOMeP0PTb/p9RhoC0b45dOWcejjd1lHxzV8Q/Zx3cIfYaEhByoYAPcLjaotZgJgMVAeQcv2MNFHVZvSBrHruLWds1fcNKkCRiQHp+KcitTwEPTycxk9PAHxhliRHRDneFA==</en-crypt><br />
</div>
<div><br /></div>
</en-note>
"""  # noqa: E501
    expected_head = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">

<div><br />
</div>

<div>password: password</div>

<div><br />
</div>

<div><a data-body="RU5DMOMeP0PTb/p9RhoC0b45dOWcejjd1lHxzV8Q/Zx3cIfYaEhByoYAPcLjaotZgJgMVAeQcv2MNFHVZvSBrHruLWds1fcNKkCRiQHp+KcitTwEPTycxk9PAHxhliRHRDneFA==" data-cipher="AES" data-hint="password" data-length="128" href="#" onclick="return evernote_decrypt(this);">Encrypted content. Click here to decrypt.</a><br />

</div>

<div><br />
</div>



<script>"""  # noqa: E501

    expected_tail = """
</script>
</body>
</html>
"""

    html = note_parser.parse(".", note, title="привет")
    html = html.decode()
    assert html.startswith(expected_head)
    assert html.endswith(expected_tail)
    assert html.count("evernote_decrypt") == 2


@vcr_dtd.use_cassette("cassette_dtd")
def test_malformed_note_raises():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<html>
<en-note></en-note>
</html>
"""
    with pytest.raises(EvernoteMalformedNoteError):
        note_parser.parse(".", note, title="1")

    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
"""
    with pytest.raises(EvernoteMalformedNoteError):
        note_parser.parse(".", note, title="1")


@vcr_dtd.use_cassette("cassette_dtd")
def test_todo():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div><en-todo checked="false" />раз<br /></div>
<div><en-todo checked="true" />два<br /></div>
<div><en-todo checked="false" />три четыре</div>
</en-note>
"""
    expected = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">

<div><input disabled="disabled" type="checkbox" />раз<br />
</div>

<div><input checked="checked" disabled="disabled" type="checkbox" />два<br />
</div>

<div><input disabled="disabled" type="checkbox" />три четыре</div>


</body>
</html>
"""  # noqa: E501

    html = note_parser.parse(".", note, title="привет")
    assert html.decode() == expected


@vcr_dtd.use_cassette("cassette_dtd")
def test_html_entities_unwrapping():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>&lt; &gt; &amp; &nbsp;</div>
<div>&#9986; &#x2702;</div>
</en-note>
"""
    expected = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">

<div>&lt; &gt; &amp; \xa0</div>

<div>✂ ✂</div>


</body>
</html>
"""  # noqa: E501

    html = note_parser.parse(".", note, title="привет")
    assert html.decode() == expected


@vcr_dtd.use_cassette("cassette_dtd")
def test_image():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>

<div><en-media hash="f8d248a22ddc4643e703b53afd95ca8a" type="image/png" /><br /></div>

</en-note>
"""
    expected = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">


<div><img src="../Resource s/123/f8d248a22ddc4643e703b53afd95ca8a.png" /><br />
</div>



</body>
</html>
"""  # noqa: E501

    src_path = "../Resource s/123/"
    html = note_parser.parse(src_path, note, title="привет")
    assert html.decode() == expected


@vcr_dtd.use_cassette("cassette_dtd")
def test_pdf():
    note = """<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>

<div><en-media hash="826b37920ad8673a8fea97a6c57b3689" type="application/pdf" style="cursor:pointer;" /></div>

</en-note>
"""  # noqa: E501
    expected = """<html>
<head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />
<title>привет</title>

</head>
<body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">


<div><a href="../Resource s/123/826b37920ad8673a8fea97a6c57b3689.pdf">Document of type application/pdf</a></div>



</body>
</html>
"""  # noqa: E501

    src_path = "../Resource s/123/"
    html = note_parser.parse(src_path, note, title="привет")
    assert html.decode() == expected
