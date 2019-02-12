from datetime import datetime

import pytz

from synctogit.todoist import models
from synctogit.todoist.projects_renderer import ProjectsRenderer


def test_empty_project():
    timezone = pytz.timezone("Europe/London")
    r = ProjectsRenderer(
        projects=[
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
                name="Empty project",
                subprojects=[],
            ),
        ],
        todo_items={
            1111: [
                models.TodoistTodoItem(
                    id=1234,
                    all_day=True,
                    content="All day Привет",
                    added_datetime=timezone.localize(datetime(2018, 9, 26, 1, 42, 56)),
                    due_date=None,
                    due_datetime=None,
                    priority=models.TodoistItemPriority.p1,
                    subitems=[],
                )
            ]
        },
        timezone=timezone,
    )
    assert r.render_index()
