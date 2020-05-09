from functools import lru_cache
from typing import Dict, NamedTuple, Sequence

import pytz

from synctogit.filename_sanitizer import normalize_filename
from synctogit.templates import template_env

from . import models

_index_template = template_env.get_template("todoist/index.j2")
_project_template = template_env.get_template("todoist/project.j2")


def _flatten_projects(projects):
    flat_projects = []
    for p in projects:
        flat_projects.append(p)
        flat_projects.extend(_flatten_projects(p.subprojects))
    return flat_projects


class ProjectsRenderer:
    def __init__(
        self,
        *,
        projects: Sequence[models.TodoistProject],
        todo_items: Dict[models.TodoistProjectId, Sequence[models.TodoistTodoItem]],
        timezone: pytz.BaseTzInfo
    ) -> None:
        self.projects = tuple(projects)
        self.flat_projects = tuple(_flatten_projects(projects))
        self.id_to_project = {project.id: project for project in self.flat_projects}
        self.todo_items = dict(todo_items)
        self.timezone = timezone

    @lru_cache(maxsize=100)
    def render_project(self, project_id) -> bytes:
        project = self.id_to_project[project_id]

        html_text = _project_template.render(
            dict(project=project, todo_items=self.todo_items, timezone=self.timezone)
        )
        return html_text.encode("utf8")

    @lru_cache()
    def render_index(self) -> bytes:
        project_links = {
            project.id: _IndexProjectLink(
                # XXX move this out for god's sake
                url="./Projects/%s.%s.html"
                % (normalize_filename(project.name), project.id),
                todo_items_count=len(self.todo_items.get(project.id, [])),
            )
            for project in self.flat_projects
        }

        html_text = _index_template.render(
            dict(
                projects=self.projects,
                flat_projects=self.flat_projects,
                project_links=project_links,
                todo_items=self.todo_items,
                timezone=self.timezone,
            )
        )
        return html_text.encode("utf8")


_IndexProjectLink = NamedTuple(
    "IndexProjectLink",
    [
        # fmt: off
        ("url", str),
        ("todo_items_count", int),
        # fmt: on
    ],
)
