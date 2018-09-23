import operator
import os
import urllib.parse
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape

import jinja2


def _include_file(name):
    # Raw file loader.
    # See: https://stackoverflow.com/a/9769454
    return jinja2.Markup(template_loader.get_source(template_env, name)[0])


template_path = str(Path(os.path.dirname(__file__)) / 'templates')
template_loader = jinja2.FileSystemLoader(searchpath=template_path)
template_env = jinja2.Environment(loader=template_loader)
template_env.globals['include_file'] = _include_file

_index_template = template_env.get_template("index.j2")


def file_writer(output_filepath) -> Callable[[bytes], None]:  # pragma: no cover
    output_filepath = os.path.realpath(output_filepath)

    def write(data: bytes) -> None:
        with open(output_filepath, 'wb') as f:
            f.write(data)
    return write


# XXX refactor notes
def generate(notes, writer: Callable[[bytes], None]) -> None:
    r = []
    for l in notes:
        text = ' &rarr; '.join(map(escape, l[1]))

        parts = map(lambda s: urllib.parse.quote(s.encode("utf8")),
                    ["Notes"] + l[0])
        url = './' + '/'.join(parts)

        r.append({'text': text, 'url': url})

    r = sorted(r, key=operator.itemgetter('url'))
    b = _index_template.render(dict(notes=r))

    writer(b.encode("utf8"))
