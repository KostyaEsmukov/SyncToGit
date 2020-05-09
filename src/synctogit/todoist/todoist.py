import datetime
import os
from collections import defaultdict
from collections.abc import Mapping
from logging import getLogger
from typing import Dict, Optional, Sequence, Tuple

import dateutil.parser
import pytz
import todoist
from cached_property import cached_property

from synctogit.service import ServiceAPIError, ServiceTokenExpiredError

from . import models

logger = getLogger(__name__)


class Todoist:
    def __init__(self, cache_dir: str, auth_token: str) -> None:
        cache_dir = cache_dir.rstrip(os.sep) + os.sep
        self.api = self._create_api(cache_dir, auth_token)

    def _create_api(self, cache_dir, auth_token):
        assert auth_token
        return todoist.TodoistAPI(cache=cache_dir, token=auth_token)

    def sync(self):
        response = self.api.sync()
        if isinstance(response, Mapping):
            if "sync_token" in response and "error" not in response:
                # Successful sync
                return
            if "error" in response:
                if "AUTH_INVALID_TOKEN" == response.get("error_tag"):
                    raise ServiceTokenExpiredError(response.get("error"))
            error = response.get("error") or response
        else:
            error = response
        raise ServiceAPIError(str(error))

    def get_projects(self) -> Sequence[models.TodoistProject]:
        def key(p):
            # All root items should go first, so they would exist when
            # a child item is processed.
            return (
                p.data.get("parent_id") or -1,
                p.data.get("item_order", 999999),
                p.data.get("child_order", 999999),
            )

        ordered_raw_projects = sorted(self.api.state["projects"], key=key)

        result_id_to_project = {}
        result_ids = []

        for raw_project in ordered_raw_projects:
            project_id = raw_project.data["id"]
            p = raw_project.data
            if p.get("is_deleted") or p.get("is_archived"):
                logger.debug("Skipping project as deleted/archived: %s", p)
                continue

            project = models.TodoistProject(
                id=int(p["id"]),
                name=str(p["name"]),
                is_favorite=bool(p.get("is_favorite", False)),
                is_inbox=bool(p.get("inbox_project", False)),
                color=self._map_project_color(p["color"]),
                subprojects=[],
            )

            parent_id = p.get("parent_id")
            if parent_id is None:
                # This is a root project
                result_ids.append(project_id)
            else:
                # Child project
                if parent_id not in result_id_to_project:
                    # It was filtered out as deleted/archived/etc.
                    continue
                result_id_to_project[parent_id].subprojects.append(project)
            result_id_to_project[project_id] = project

        return [result_id_to_project[project_id] for project_id in result_ids]

    def get_todo_items(
        self,
    ) -> Dict[models.TodoistProjectId, Sequence[models.TodoistTodoItem]]:
        def key(i):
            # All root items should go first, so they would exist when
            # a child item is processed.
            return (
                i.data.get("parent_id") or -1,
                i.data.get("item_order") or -1,
                i.data["id"],
            )

        ordered_items = sorted(self.api.state["items"], key=key)

        id_to_item = {}
        project_id_to_items = defaultdict(lambda: [])

        for raw_item in ordered_items:
            i = raw_item.data

            # NOTE: The original Todoist doesn't hide the checked items
            # when they're nested under a non-checked todo item, but
            # the code below hides them. This is my personal preference
            # and perhaps it should be made configurable.
            if i.get("is_deleted") or i.get("is_archived") or i.get("checked"):
                logger.debug("Skipping todo item as deleted/archived/checked: %s", i)
                continue

            project_id = i["project_id"]

            date_added = self._parse_datetime(i["date_added"])
            assert date_added

            try:
                due_date, due_datetime = self._parse_due_date_time(i)
            except ValueError:
                logger.error(
                    "Unable to parse due time, using None. Todo item: %s", i,
                )
                due_date, due_datetime = None, None

            item = models.TodoistTodoItem(
                id=int(i["id"]),
                all_day=bool(i.get("all_day", False)),
                content=str(i["content"]),
                added_datetime=date_added,
                due_date=due_date,
                due_datetime=due_datetime,
                priority=models.TodoistItemPriority(i["priority"]),
                subitems=[],
            )

            parent_id = i["parent_id"]
            if parent_id is None:
                project_id_to_items[project_id].append(item)
            else:
                if parent_id not in id_to_item:
                    # It was filtered out as checked/deleted/etc.
                    continue
                id_to_item[parent_id].subitems.append(item)
            id_to_item[i["id"]] = item

        return dict(project_id_to_items)

    def _parse_due_date_time(
        self, item_data
    ) -> Tuple[Optional[datetime.date], Optional[datetime.datetime]]:
        # The situation with due dates in the current Todoist API
        # is deeply fucked up, so the code below is rather fragile.
        due_date = None
        due_datetime = None

        if item_data.get("due"):
            due = item_data["due"]

            assert due.get("timezone") is None  # This is a legacy key, I believe
            timezone = self._timezone

            # date -- is a datetime. In ISO format. Or just a date.
            # Live with it.
            try:
                fmt = "%Y-%m-%d"
                due_datetime = datetime.datetime.strptime(due["date"], fmt)
                # If it didn't raise yet -- then it's indeed just a date.
                # Drop the datetime -- we don't need it if it doesn't
                # contain time.
                due_date = due_datetime.date()
                due_datetime = None
            except ValueError:
                # It's not a date -- thus it's a full datetime.
                due_datetime = dateutil.parser.parse(due["date"])
                if due_datetime.tzinfo is None:
                    due_datetime = timezone.localize(due_datetime)
                due_datetime = due_datetime.astimezone(timezone)
                due_date = due_datetime.date()

        assert item_data.get("due_date_utc") is None  # This is a legacy key, I believe

        return due_date, due_datetime

    @staticmethod
    def _map_project_color(color_index: int) -> str:
        # Taken from the Project color palette by using a browser's Web Inspector:
        #
        # e = [...document.querySelectorAll('.colors .object_color')]
        # e.map(f => `${f.dataset.index}: "${f.style.backgroundColor}"`).join(',\n')
        palette = {
            30: "rgb(184, 37, 95)",
            31: "rgb(219, 64, 53)",
            32: "rgb(255, 153, 51)",
            33: "rgb(250, 208, 0)",
            34: "rgb(175, 184, 59)",
            35: "rgb(126, 204, 73)",
            36: "rgb(41, 148, 56)",
            37: "rgb(106, 204, 188)",
            38: "rgb(21, 143, 173)",
            39: "rgb(20, 170, 245)",
            40: "rgb(150, 195, 235)",
            41: "rgb(64, 115, 255)",
            42: "rgb(136, 77, 255)",
            43: "rgb(175, 56, 235)",
            44: "rgb(235, 150, 235)",
            45: "rgb(224, 81, 148)",
            46: "rgb(255, 141, 133)",
            47: "rgb(128, 128, 128)",
            48: "rgb(184, 184, 184)",
            49: "rgb(204, 172, 147)",
        }
        if color_index not in palette:
            color_index = 48  # light gray
        return palette[color_index]

    @cached_property
    def _timezone(self) -> datetime.tzinfo:
        timezone = self.api.state["user"]["tz_info"]["timezone"]
        return pytz.timezone(timezone)

    def _parse_datetime(self, date: Optional[str]) -> Optional[datetime.datetime]:
        if not date:
            return None
        parsed_dt = dateutil.parser.parse(date)
        if not parsed_dt.tzinfo:
            raise ValueError("Expected tz-aware datetime, received '%s'" % date)
        return parsed_dt.astimezone(self._timezone)
