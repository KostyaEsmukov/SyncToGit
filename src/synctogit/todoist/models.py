import datetime
from enum import Enum
from typing import NamedTuple, NewType, Optional, Sequence

TodoistProjectId = NewType("TodoistProjectId", int)


class TodoistItemPriority(Enum):
    p4 = 4  # grey
    p3 = 3  # yellow
    p2 = 2  # orange
    p1 = 1  # red


TodoistProject = NamedTuple(
    "TodoistProject",
    [
        ("id", TodoistProjectId),
        ("color", str),  # css-compatible background-color.
        ("is_favorite", bool),
        ("is_inbox", bool),
        ("name", str),
        ("subprojects", Sequence["TodoistProject"]),
    ],
)


TodoistTodoItem = NamedTuple(
    "TodoistTodoItem",
    [
        ("id", int),
        ("all_day", bool),
        ("content", str),
        ("added_datetime", datetime.datetime),
        ("due_date", Optional[datetime.date]),
        #
        # Due datetimes are a mess. due_datetime will be None when a
        # specific time is not set -- i.e. no due date or just a day.
        # If specific due time is set, it will be in the due_datetime.
        # It's guaranteed that the date parts between the two are equal.
        ("due_datetime", Optional[datetime.time]),
        #
        ("priority", TodoistItemPriority),
        ("subitems", Sequence["TodoistTodoItem"]),
        # has_more_notes: false
        # labels: []
    ],
)
