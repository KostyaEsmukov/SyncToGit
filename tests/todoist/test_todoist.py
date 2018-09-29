from collections import defaultdict
from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest
import pytz
from todoist.models import Item, Project

from synctogit.todoist import models
from synctogit.todoist.todoist import Todoist


def ultimate_defaultdict():
    return defaultdict(ultimate_defaultdict)


@pytest.fixture
def todoist_user_timezone_name():
    return "Europe/Moscow"


@pytest.fixture
def todoist_user_timezone(todoist_user_timezone_name):
    return pytz.timezone(todoist_user_timezone_name)


@pytest.fixture
def todoist(todoist_user_timezone_name):
    with patch("synctogit.todoist.todoist.Todoist._create_api", Mock()):
        todoist = Todoist("", None)
    todoist.api.state = ultimate_defaultdict()
    todoist.api.state["user"]["tz_info"]["timezone"] = todoist_user_timezone_name

    return todoist


@pytest.mark.parametrize(
    "date_raw, date_expected",
    [
        ("Fri 23 Jun 2017 06:39:51 +0000", (2017, 6, 23, 9, 39, 51)),
        ("Sat 07 Oct 2017 20:59:59 +0000", (2017, 10, 7, 23, 59, 59)),
    ],
)
def test_parse_datetime(todoist, date_raw, date_expected, todoist_user_timezone):
    datetime_expected = todoist_user_timezone.localize(datetime(*date_expected))
    assert todoist._parse_datetime(date_raw) == datetime_expected


def test_get_projects(todoist):
    todoist.api.state["projects"] = [
        Project(
            {
                "collapsed": 0,
                "color": 48,
                "has_more_notes": False,
                "id": 1111,
                "inbox_project": True,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "is_favorite": 0,
                "item_order": 0,
                "name": "Inbox",
                "parent_id": None,
                "shared": False,
            },
            None,
        ),
        Project(
            {
                "collapsed": 0,
                "color": 35,
                "has_more_notes": False,
                "id": 23167531,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "is_favorite": 1,
                "item_order": 4,
                "name": "Green Favorite Проект",
                "parent_id": None,
                "shared": False,
            },
            None,
        ),
        Project(
            {
                "collapsed": 0,
                "color": 48,
                "has_more_notes": False,
                "id": 333333,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "is_favorite": 0,
                "item_order": 1,
                "name": "Grey root project",
                "parent_id": None,
                "shared": False,
            },
            None,
        ),
        Project(
            {
                "collapsed": 0,
                "color": 48,
                "has_more_notes": False,
                "id": 555555,
                "indent": 2,
                "is_archived": 0,
                "is_deleted": 0,
                "is_favorite": 0,
                "item_order": 2,
                "name": "Grey child project",
                "parent_id": 333333,
                "shared": False,
            },
            None,
        ),
        Project(
            {
                "collapsed": 0,
                "color": 48,
                "has_more_notes": False,
                "id": 66666,
                "indent": 3,
                "is_archived": 0,
                "is_deleted": 0,
                "is_favorite": 0,
                "item_order": 3,
                "name": "Grey subchild project",
                "parent_id": 555555,
                "shared": False,
            },
            None,
        ),
    ]

    expected_projects = [
        models.TodoistProject(
            id=1111,
            color="rgb(184, 184, 184)",
            is_favorite=False,
            is_inbox=True,
            name="Inbox",
            subprojects=[],
        ),
        models.TodoistProject(
            id=333333,
            color="rgb(184, 184, 184)",
            is_favorite=False,
            is_inbox=False,
            name="Grey root project",
            subprojects=[
                models.TodoistProject(
                    id=555555,
                    color="rgb(184, 184, 184)",
                    is_favorite=False,
                    is_inbox=False,
                    name="Grey child project",
                    subprojects=[
                        models.TodoistProject(
                            id=66666,
                            color="rgb(184, 184, 184)",
                            is_favorite=False,
                            is_inbox=False,
                            name="Grey subchild project",
                            subprojects=[],
                        )
                    ],
                )
            ],
        ),
        models.TodoistProject(
            id=23167531,
            color="rgb(126, 204, 73)",
            is_favorite=True,
            is_inbox=False,
            name="Green Favorite Проект",
            subprojects=[],
        ),
    ]

    assert todoist.get_projects() == expected_projects


def test_get_todo_items(todoist, todoist_user_timezone):
    todoist.api.state["items"] = [
        Item(
            {
                "all_day": True,
                "assigned_by_uid": 999,
                "checked": 0,
                "collapsed": 0,
                "content": "Child",
                "date_added": "Tue 25 Sep 2018 22:42:56 +0000",
                "date_completed": None,
                "date_lang": "en",
                "date_string": "28 Sep",
                "day_order": 6,
                "due_date_utc": None,
                "has_more_notes": False,
                "id": 3456,
                "in_history": 0,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "item_order": 822,
                "labels": [],
                "parent_id": 2345,
                "priority": 1,
                "project_id": 999,
                "responsible_uid": None,
                "sync_id": None,
                "user_id": 999,
            },
            None,
        ),
        Item(
            {
                "all_day": True,
                "assigned_by_uid": 999,
                "checked": 0,
                "collapsed": 0,
                "content": "Subchild",
                "date_added": "Tue 25 Sep 2018 22:42:56 +0000",
                "date_completed": None,
                "date_lang": "en",
                "date_string": "28 Sep",
                "day_order": 10,
                "due_date_utc": None,
                "has_more_notes": False,
                "id": 4567,
                "in_history": 0,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "item_order": 1822,
                "labels": [],
                "parent_id": 3456,
                "priority": 1,
                "project_id": 999,
                "responsible_uid": None,
                "sync_id": None,
                "user_id": 999,
            },
            None,
        ),
        Item(
            {
                "all_day": False,
                "assigned_by_uid": 999,
                "checked": 0,
                "collapsed": 0,
                "content": "Root",
                "date_added": "Tue 25 Sep 2018 22:42:56 +0000",
                "date_completed": None,
                "date_lang": "en",
                "date_string": "28 Sep",
                "day_order": 6,
                "due": {
                    "date": "2018-09-29T13:00:00Z",
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": "Europe/Moscow",
                },
                "due_date_utc": "Sat 29 Sep 2018 20:59:59 +0000",
                "has_more_notes": False,
                "id": 2345,
                "in_history": 0,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "item_order": 821,
                "labels": [],
                "parent_id": None,
                "priority": 4,
                "project_id": 999,
                "responsible_uid": None,
                "sync_id": None,
                "user_id": 999,
            },
            None,
        ),
        Item(
            {
                "all_day": True,
                "assigned_by_uid": 999,
                "checked": 0,
                "collapsed": 0,
                "content": "All day Привет",
                "date_added": "Tue 25 Sep 2018 22:42:56 +0000",
                "date_completed": None,
                "date_lang": "en",
                "date_string": "28 Sep",
                "day_order": 6,
                "due_date_utc": None,
                "has_more_notes": False,
                "id": 1234,
                "in_history": 0,
                "indent": 1,
                "is_archived": 0,
                "is_deleted": 0,
                "item_order": 820,
                "labels": [],
                "parent_id": None,
                "priority": 1,
                "project_id": 999,
                "responsible_uid": None,
                "sync_id": None,
                "user_id": 999,
            },
            None,
        ),
    ]

    expected_items = {
        999: [
            models.TodoistTodoItem(
                id=1234,
                all_day=True,
                content="All day Привет",
                added_datetime=todoist_user_timezone.localize(
                    datetime(2018, 9, 26, 1, 42, 56)
                ),
                due_date=None,
                due_datetime=None,
                priority=models.TodoistItemPriority.p1,
                subitems=[],
            ),
            models.TodoistTodoItem(
                id=2345,
                all_day=False,
                content="Root",
                added_datetime=todoist_user_timezone.localize(
                    datetime(2018, 9, 26, 1, 42, 56)
                ),
                due_date=date(2018, 9, 29),
                due_datetime=todoist_user_timezone.localize(
                    datetime(2018, 9, 29, 16, 0, 0)
                ),
                priority=models.TodoistItemPriority.p4,
                subitems=[
                    models.TodoistTodoItem(
                        id=3456,
                        all_day=True,
                        content="Child",
                        added_datetime=todoist_user_timezone.localize(
                            datetime(2018, 9, 26, 1, 42, 56)
                        ),
                        due_date=None,
                        due_datetime=None,
                        priority=models.TodoistItemPriority.p1,
                        subitems=[
                            models.TodoistTodoItem(
                                id=4567,
                                all_day=True,
                                content="Subchild",
                                added_datetime=todoist_user_timezone.localize(
                                    datetime(2018, 9, 26, 1, 42, 56)
                                ),
                                due_date=None,
                                due_datetime=None,
                                priority=models.TodoistItemPriority.p1,
                                subitems=[],
                            )
                        ],
                    )
                ],
            ),
        ]
    }

    assert todoist.get_todo_items() == expected_items


@pytest.mark.parametrize(
    "todo_item, due_date, due_datetime",
    [
        ({}, None, None),
        ({"due_date_utc": "Sat 29 Sep 2018 20:59:59 +0000"}, date(2018, 9, 29), None),
        (
            {"due_date_utc": "Sat 29 Sep 2018 23:59:59 +0300", "due": {}},  # unexpected
            date(2018, 9, 29),
            None,
        ),
        (
            {
                "due_date_utc": "Sat 29 Sep 2018 20:59:59 +0000",
                "due": {
                    "date": "2018-09-29T13:00:00Z",
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": "Europe/Moscow",
                },
            },
            date(2018, 9, 29),
            datetime(2018, 9, 29, 16, 0, 0),
        ),
        (
            {
                "due_date_utc": "Sat 29 Sep 2018 20:59:59 +0000",
                "due": {
                    "date": "2018-09-29T16:00:00+03:00",  # unexpected
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": "Europe/Moscow",
                },
            },
            date(2018, 9, 29),
            datetime(2018, 9, 29, 16, 0, 0),
        ),
    ],
)
def test_parse_due_time(
    todoist, todo_item, due_date, due_datetime, todoist_user_timezone
):
    if due_datetime is not None:
        due_datetime = todoist_user_timezone.localize(due_datetime)
    assert todoist._parse_due_date_time(todo_item) == (due_date, due_datetime)


@pytest.mark.parametrize(
    "todo_item",
    [
        {"due_date_utc": "Sat 29 Sep 2018 10:00:00 +0000"},  # must be 23:59:59
        {
            "due_date_utc": "Sat 29 Sep 2018 20:59:59 +0000",
            "due": {
                "date": "2018-09-10T13:00:00Z",  # date must not differ from due_date_utc
                "is_recurring": False,
                "lang": "en",
                "string": "29 Sep 16:00",
                "timezone": "Europe/Moscow",
            },
        },
    ],
)
def test_parse_due_time_raises(todoist, todo_item):
    with pytest.raises(ValueError):
        todoist._parse_due_date_time(todo_item)
