import urllib.parse
from typing import Callable, NamedTuple, Sequence, Union

from synctogit.templates import template_env

_index_template = template_env.get_template("evernote/index.j2")


def render(
    note_links: Sequence["IndexLink"],
    writer: Callable[[bytes], None],
    notes_dirs: Sequence[str] = ("Notes",),
) -> None:
    dir_items = _note_links_to_tree(note_links, notes_dirs)
    b = _index_template.render(dict(items=dir_items))
    writer(b.encode("utf8"))


IndexLink = NamedTuple(
    "IndexLink",
    [
        # fmt: off
        ("filesystem_path_parts", Sequence[str]),
        ("name_parts", Sequence[str]),
        # fmt: on
    ],
)


def _all_prefix_parts(seq):
    for i in range(len(seq)):
        yield seq[: i + 1]


def _note_links_to_tree(
    note_links: Sequence["IndexLink"], notes_dirs: Sequence[str],
) -> Sequence["_DirItem"]:
    dir_items = []
    name_parts_to_dir_item = {}

    for index_link in note_links:
        dir_item = None
        for parts in _all_prefix_parts(index_link.name_parts[:-1]):
            parts = tuple(parts)
            if parts in name_parts_to_dir_item:
                # An already existing dir item
                dir_item = name_parts_to_dir_item[parts]
            else:
                # A new dir item -- create it and link with the parent
                parent_dir_item = dir_item
                dir_item = _DirItem(name=parts[-1], items=[])
                name_parts_to_dir_item[parts] = dir_item
                if parent_dir_item:
                    # Link it with the parent
                    parent_dir_item.items.append(dir_item)
                if not parent_dir_item:
                    # This is a root dir -- put it to the result list
                    dir_items.append(dir_item)

        if not dir_item:
            raise ValueError("Expected each note to be contained within some notebook")

        parts = map(
            lambda s: urllib.parse.quote(s.encode("utf8")),
            notes_dirs + index_link.filesystem_path_parts,
        )
        url = "./" + "/".join(parts)

        dir_item.items.append(_NoteItem(name=index_link.name_parts[-1], url=url))
    return dir_items


_DirItem = NamedTuple(
    "_DirItem",
    [
        # fmt: off
        ("name", str),
        ("items", Sequence[Union["_DirItem", "_NoteItem"]]),
        # fmt: on
    ],
)

_NoteItem = NamedTuple(
    "_NoteItem",
    [
        # fmt: off
        ("name", str),
        ("url", str),
        # fmt: on
    ],
)
