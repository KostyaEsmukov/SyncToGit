import os

import vcr

from synctogit.evernote import note_parser

vcr_dtd = vcr.VCR(cassette_library_dir=os.path.dirname(__file__))


@vcr_dtd.use_cassette('cassete_dtd')
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
""".encode("utf8")  # noqa: E501

    res = note_parser.parse('.', note, title='привет')
    assert res == expected


@vcr_dtd.use_cassette('cassete_dtd')
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



<script>""".encode("utf8")  # noqa: E501

    expected_tail = """
</script>
</body>
</html>
""".encode("utf8")

    res = note_parser.parse('.', note, title='привет')
    html = res
    assert html.startswith(expected_head)
    assert html.endswith(expected_tail)
    assert html.count(b'evernote_decrypt') == 2
