from collections import defaultdict
from contextlib import ExitStack
from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest
import pytz
from todoist.models import Item, Project

from synctogit.service import ServiceAPIError, ServiceTokenExpiredError
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
        ("2017-09-02T14:12:53+01:00", (2017, 9, 2, 16, 12, 53)),
        ("2017-10-22T14:12:53Z", (2017, 10, 22, 17, 12, 53)),
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
        Project(
            {
                "shared": False,
                "is_deleted": 0,
                "parent_id": None,
                "name": "New API",
                "id": 99999922222,
                "is_archived": 0,
                "is_favorite": 0,
                "collapsed": 0,
                "child_order": 10,
                "color": 32,
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
        models.TodoistProject(
            id=99999922222,
            color="rgb(255, 153, 51)",
            is_favorite=False,
            is_inbox=False,
            name="New API",
            subprojects=[],
        ),
    ]

    assert todoist.get_projects() == expected_projects


@pytest.mark.parametrize("project_extra", [dict(is_archived=1), dict(is_deleted=1)])
def test_hidden_projects(todoist, project_extra):
    project = {
        "collapsed": 0,
        "color": 35,
        "has_more_notes": False,
        "is_archived": 0,
        "is_deleted": 0,
        "is_favorite": 1,
        "shared": False,
    }
    todoist.api.state["projects"] = [
        Project(
            {
                "id": 1234,
                "indent": 1,
                "item_order": 4,
                "name": "DELETED PROJECT",
                "parent_id": None,
                **project,
                **project_extra,
            },
            None,
        ),
        Project(
            {
                "id": 2222,
                "indent": 2,
                "item_order": 5,
                "name": "CHILD PROJECT",
                "parent_id": 1234,
                **project,
            },
            None,
        ),
    ]
    expected_projects = []

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
                "date_added": "2018-09-25T22:42:56Z",
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
                "date_added": "2018-09-25T22:42:56Z",
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
                "date_added": "2018-09-25T22:42:56Z",
                "date_completed": None,
                "date_lang": "en",
                "date_string": "28 Sep",
                "day_order": 6,
                "due": {
                    "date": "2018-09-29T13:00:00Z",
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": None,
                },
                "due_date_utc": None,
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
                "date_added": "2018-09-25T22:42:56Z",
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
    "item_extra", [dict(is_archived=1), dict(is_deleted=1), dict(checked=1)]
)
def test_hidden_todo_items(todoist, item_extra):
    item = {
        "all_day": True,
        "assigned_by_uid": 999,
        "checked": 0,
        "collapsed": 0,
        "date_added": "2018-09-25T22:42:56Z",
        "date_completed": None,
        "date_lang": "en",
        "date_string": "28 Sep",
        "day_order": 6,
        "due_date_utc": None,
        "has_more_notes": False,
        "in_history": 0,
        "is_archived": 0,
        "is_deleted": 0,
        "labels": [],
        "priority": 1,
        "project_id": 999,
        "responsible_uid": None,
        "sync_id": None,
        "user_id": 999,
    }
    todoist.api.state["items"] = [
        Item(
            {
                "content": "All day Привет",
                "id": 1234,
                "indent": 1,
                "item_order": 820,
                "parent_id": None,
                **item,
                **item_extra,
            },
            None,
        ),
        Item(
            {
                "content": "Non-hidden child",
                "id": 2234,
                "indent": 2,
                "item_order": 821,
                "parent_id": 1234,
                **item,
            },
            None,
        ),
    ]

    expected_items = {}

    assert todoist.get_todo_items() == expected_items


@pytest.mark.parametrize(
    "todo_item, due_date, due_datetime",
    [
        ({}, None, None),
        (
            {
                "due_date_utc": None,
                "due": {
                    "date": "2018-09-29T13:00:00Z",  # fake
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": None,
                },
            },
            date(2018, 9, 29),
            datetime(2018, 9, 29, 16, 0, 0),
        ),
        (
            {
                "due_date_utc": None,
                "due": {
                    "date": "2018-09-29T16:00:00",  # actual
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": None,
                },
            },
            date(2018, 9, 29),
            datetime(2018, 9, 29, 16, 0, 0),
        ),
        (
            {
                "due_date_utc": None,
                "due": {
                    "date": "2018-09-29T16:00:00+03:00",  # fake
                    "is_recurring": False,
                    "lang": "en",
                    "string": "29 Sep 16:00",
                    "timezone": None,
                },
            },
            date(2018, 9, 29),
            datetime(2018, 9, 29, 16, 0, 0),
        ),
        (
            {
                "due_date_utc": None,
                "due": {
                    "date": "2018-09-29",
                    "string": "29 Sep",
                    "is_recurring": False,
                    "lang": "en",
                    "timezone": None,
                },
            },
            date(2018, 9, 29),
            None,
        ),
        (
            {
                "date_string": None,
                "due": {
                    "lang": "en",
                    "string": "30 Sep",
                    "timezone": None,
                    "is_recurring": False,
                    "date": "2018-09-30",
                },
                "due_date_utc": None,
            },
            date(2018, 9, 30),
            None,
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
    # fmt: off
    [
        {"due_date_utc": "2018-09-29T16:00:00"},  # must be None
    ],
    # fmt: on
)
def test_parse_due_time_raises(todoist, todo_item):
    with pytest.raises(AssertionError):
        todoist._parse_due_date_time(todo_item)


@pytest.mark.parametrize(
    "exc, response",
    [
        (ServiceAPIError, "Error!"),
        (
            ServiceTokenExpiredError,
            {
                "error_extra": {"retry_after": 3, "access_type": "access_token"},
                "http_code": 403,
                "error_code": 401,
                "error_tag": "AUTH_INVALID_TOKEN",
                "error": "Invalid token",
            },
        ),
        (
            None,
            {
                "notes": [],
                "projects": [],
                "sync_token": "ZZZZ",
                "items": [],
                "filters": [],
            },
        ),
    ],
)
def test_sync_error_processing(todoist, exc, response):
    with patch.object(todoist.api, "sync", return_value=response):
        with ExitStack() as stack:
            if exc is not None:
                stack.enter_context(pytest.raises(exc))
            todoist.sync()
