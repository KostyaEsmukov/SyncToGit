import logging
import os
from typing import Mapping, NamedTuple, Optional, Sequence, Tuple

from synctogit.filename_sanitizer import normalize_filename
from synctogit.git_transaction import GitTransaction, rmfile_silent

from .models import TodoistProject, TodoistProjectId
from .projects_renderer import ProjectsRenderer

logger = logging.getLogger(__name__)


class TodoistWorkingCopy:
    projects_dir_name = "Projects"

    def __init__(
        self, git_transaction: GitTransaction, *, projects_renderer: ProjectsRenderer
    ) -> None:
        self.git_transaction = git_transaction
        self.repo_dir = git_transaction.repo_dir
        self.projects_dir = self.repo_dir / self.projects_dir_name
        self.projects_renderer = projects_renderer

    def _project_filename(self, project: TodoistProject) -> str:
        return "%s.%s.html" % (normalize_filename(project.name), project.id)

    def get_changes(self) -> "Changeset":
        working_tree_projects = self._read_working_tree_projects()
        working_tree_index = self._read_working_tree_index()

        actual_projects = self._render_actual_projects()  # value is (html, project)
        actual_index = self.projects_renderer.render_index()

        return self._calculate_changeset(
            working_tree_projects=working_tree_projects,
            working_tree_index=working_tree_index,
            actual_projects=actual_projects,
            actual_index=actual_index,
        )

    def _read_working_tree_projects(self) -> Mapping[str, bytes]:
        working_tree_projects = {}
        for root, _, files in os.walk(str(self.projects_dir)):
            for fn in files:
                project_path = self.projects_dir / fn
                _, ext = os.path.splitext(fn)
                if ext != ".html":
                    logger.warning(
                        "Removing an extraneous file in the Projects directory: %s", fn
                    )
                    rmfile_silent(project_path)
                    continue
                working_tree_projects[fn] = project_path.read_bytes()
        return working_tree_projects

    def _read_working_tree_index(self) -> Optional[bytes]:
        index_path = self.repo_dir / "index.html"
        if index_path.is_file():
            return index_path.read_bytes()
        return None

    def _render_actual_projects(self) -> Mapping[str, Tuple[bytes, TodoistProject]]:
        actual_projects = {}
        for project in self.projects_renderer.flat_projects:
            fn = self._project_filename(project)
            html = self.projects_renderer.render_project(project.id)
            actual_projects[fn] = html, project
        return actual_projects

    def _calculate_changeset(
        self,
        *,
        working_tree_projects,
        working_tree_index,
        actual_projects,
        actual_index
    ) -> "Changeset":
        is_index_obsolete = working_tree_index != actual_index
        changeset = Changeset(new={}, update={}, delete=[], index=is_index_obsolete)

        working_tree_files = set(working_tree_projects.keys())
        actual_projects_files = set(actual_projects.keys())

        changeset.delete.extend(working_tree_files - actual_projects_files)

        new_projects = [
            actual_projects[file][1]
            for file in (actual_projects_files - working_tree_files)
        ]
        changeset.new.update(((project.id, project) for project in new_projects))

        update_projects = [
            actual_projects[file][1]
            for file in (actual_projects_files & working_tree_files)
            if actual_projects[file][0] != working_tree_projects[file]
        ]
        changeset.update.update(((project.id, project) for project in update_projects))

        return changeset

    def apply_changes(self, changeset: "Changeset") -> None:
        os.makedirs(str(self.projects_dir), exist_ok=True)

        for fn in changeset.delete:
            rmfile_silent(self.projects_dir / fn)

        for op in ("new", "update"):
            id_to_project = getattr(changeset, op)
            for project in id_to_project.values():
                fn = self._project_filename(project)
                project_path = self.projects_dir / fn
                html = self.projects_renderer.render_project(project.id)
                project_path.write_bytes(html)

        if changeset.index:
            html = self.projects_renderer.render_index()
            (self.repo_dir / "index.html").write_bytes(html)


Changeset = NamedTuple(
    "Changeset",
    [
        ("new", Mapping[TodoistProjectId, TodoistProject]),
        ("update", Mapping[TodoistProjectId, TodoistProject]),
        ("delete", Sequence[str]),  # Project's HTML file name
        ("index", bool),
    ],
)
