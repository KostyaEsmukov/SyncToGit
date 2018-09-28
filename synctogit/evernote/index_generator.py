import operator
import urllib.parse
from typing import Callable, NamedTuple, Sequence
from xml.sax.saxutils import escape

from synctogit.templates import template_env

_index_template = template_env.get_template("evernote/index.j2")


def generate(note_links: Sequence['IndexLink'],
             writer: Callable[[bytes], None]) -> None:
    r = []
    for index_link in note_links:
        text = ' &rarr; '.join(map(escape, index_link.name_parts))

        parts = map(lambda s: urllib.parse.quote(s.encode("utf8")),
                    ("Notes",) + index_link.filesystem_path_parts)
        url = './' + '/'.join(parts)

        r.append({'text': text, 'url': url})

    r = sorted(r, key=operator.itemgetter('url'))
    b = _index_template.render(dict(notes=r))

    writer(b.encode("utf8"))


IndexLink = NamedTuple(
    'IndexLink',
    [
        ('filesystem_path_parts', Sequence[str]),
        ('name_parts', Sequence[str]),
    ]
)
