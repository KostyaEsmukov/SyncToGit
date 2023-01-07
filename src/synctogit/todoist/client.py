"""This is a simplified and updated from the now-disabled v8 api
version of the https://github.com/Doist/todoist-python/ library.
"""
import datetime
import functools
import hashlib
import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class SyncError(Exception):
    pass


class SyncTokenExpiredError(SyncError):
    pass


class TodoistAPI:
    def __init__(self, token, cache):
        self.token = token
        self.session = requests.Session()
        self._cache = Cache(cache, f"{hashlib.sha256(token.encode()).hexdigest()}.v9")

    @property
    def state(self):
        return self._cache.state

    def sync(self, commands=None):
        """
        Sends to the server the changes that were made locally, and also
        fetches the latest updated data from the server.
        """
        self._cache.read_cache()
        post_data = {
            "sync_token": self._cache.sync_token,
            "resource_types": json_dumps(["all"]),
            "commands": json_dumps(commands or []),
        }
        response = self._post("sync", data=post_data)
        if "sync_token" in response and "error" not in response:
            # Successful sync
            pass
        else:
            if "error" in response:
                if "AUTH_INVALID_TOKEN" == response.get("error_tag"):
                    raise SyncTokenExpiredError(response.get("error"))
            error = response.get("error") or str(response)
            raise SyncError(error)

        if "temp_id_mapping" in response:
            for temp_id, new_id in response["temp_id_mapping"].items():
                self._cache.temp_ids[temp_id] = new_id
                self._cache.replace_temp_id(temp_id, new_id)
        self._cache.update_state(response)
        self._cache.write_cache()

    def _post(self, call, **kwargs):
        url = "https://api.todoist.com/sync/v9/"

        kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {self.token}"
        response = self.session.post(url + call, **kwargs)
        try:
            return response.json()
        except ValueError as e:
            raise SyncError(response.text) from e


class Cache:
    def __init__(self, base, name):
        self._base = Path(base).expanduser()
        self._state_path = self._base / f"{name}.json"
        self._sync_path = self._base / f"{name}.sync"
        #
        self.temp_ids = {}
        self.sync_token = "*"
        self.state = {  # Local copy of all of the user's objects
            "collaborator_states": [],
            "collaborators": [],
            "day_orders": {},
            "day_orders_timestamp": "",
            "filters": [],
            "items": [],
            "labels": [],
            "live_notifications": [],
            "live_notifications_last_read_id": -1,
            "locations": [],
            "notes": [],
            "project_notes": [],
            "projects": [],
            "reminders": [],
            "sections": [],
            "settings_notifications": {},
            "user": {},
            "user_settings": {},
        }

    def read_cache(self):
        self._base.mkdir(exist_ok=True)
        try:
            state = json.loads(self._state_path.read_text())
            self.update_state(state)

            self.sync_token = self._sync_path.read_text()
        except FileNotFoundError:
            pass
        except Exception:
            logger.warning("Unable to read todoist cache", exc_info=True)

    def write_cache(self):
        result = json.dumps(self.state, indent=2, sort_keys=True, default=state_default)
        self._state_path.write_text(result)
        self._sync_path.write_text(self.sync_token)

    def update_state(self, syncdata):
        if "sync_token" in syncdata:
            self.sync_token = syncdata["sync_token"]

        # It is straightforward to update these type of data, since it is
        # enough to just see if they are present in the sync data, and then
        # either replace the local values or update them.
        if "day_orders" in syncdata:
            self.state["day_orders"].update(syncdata["day_orders"])
        if "day_orders_timestamp" in syncdata:
            self.state["day_orders_timestamp"] = syncdata["day_orders_timestamp"]
        if "live_notifications_last_read_id" in syncdata:
            self.state["live_notifications_last_read_id"] = syncdata[
                "live_notifications_last_read_id"
            ]
        if "locations" in syncdata:
            self.state["locations"] = syncdata["locations"]
        if "settings_notifications" in syncdata:
            self.state["settings_notifications"].update(
                syncdata["settings_notifications"]
            )
        if "user" in syncdata:
            self.state["user"].update(syncdata["user"])
        if "user_settings" in syncdata:
            self.state["user_settings"].update(syncdata["user_settings"])

        # Updating these type of data is a bit more complicated, since it is
        # necessary to find out whether an object in the sync data is new,
        # updates an existing object, or marks an object to be deleted.  But
        # the same procedure takes place for each of these types of data.
        resp_models_mapping = [
            "collaborators",
            "collaborator_states",
            "filters",
            "items",
            "labels",
            "live_notifications",
            "notes",
            "project_notes",
            "projects",
            "reminders",
            "sections",
        ]
        for datatype in resp_models_mapping:
            if datatype not in syncdata:
                continue

            # Process each object of this specific type in the sync data.
            for remoteobj in syncdata[datatype]:
                # Find out whether the object already exists in the local
                # state.
                localobj = self._find_object(datatype, remoteobj)
                if localobj is not None:
                    # If the object is already present in the local state, then
                    # we either update it, or if marked as to be deleted, we
                    # remove it.
                    is_deleted = remoteobj.get("is_deleted", 0)
                    if is_deleted == 0 or is_deleted is False:
                        localobj.update(remoteobj)
                    else:
                        self._del_object(datatype, localobj)
                else:
                    # If not, then the object is new and it should be added,
                    # unless it is marked as to be deleted (in which case it's
                    # ignored).
                    is_deleted = remoteobj.get("is_deleted", 0)
                    if is_deleted == 0 or is_deleted is False:
                        self.state[datatype].append(remoteobj)

    def _del_object(self, datatype, localobj):
        to_delete_idx = []
        for i, obj in enumerate(self.state[datatype]):
            if obj["id"] == localobj["id"]:
                to_delete_idx.append(i)
        for i in reversed(to_delete_idx):
            del self.state[datatype][i]

    def _find_object(self, objtype, remote_obj):
        for obj in self.state[objtype]:
            if objtype == "collaborator_states":
                if (
                    obj["project_id"] == remote_obj["project_id"]
                    and obj["user_id"] == remote_obj["user_id"]
                ):
                    return obj
            else:
                # https://github.com/Doist/todoist-python/blob/7b85de81619146d3d54fececda068010ae73775b/todoist/managers/generic.py#L36  # noqa
                if (
                    obj["id"] == remote_obj["id"]
                    or obj.get("temp_id") == remote_obj["id"]
                ):
                    return obj
        return None

    def replace_temp_id(self, temp_id, new_id):
        """
        Replaces the temporary id generated locally when an object was first
        created, with a real Id supplied by the server.  True is returned if
        the temporary id was found and replaced, and False otherwise.
        """
        # Go through all the objects for which we expect the temporary id to be
        # replaced by a real one.
        for datatype in [
            "filters",
            "items",
            "labels",
            "notes",
            "project_notes",
            "projects",
            "reminders",
            "sections",
        ]:
            for obj in self.state[datatype]:
                if obj.get("temp_id") == temp_id:
                    obj["id"] = new_id
                    return True
        return False


def state_default(obj):
    return obj.data


def json_default(obj):
    if isinstance(obj, datetime.datetime):
        return obj.strftime("%Y-%m-%dT%H:%M:%S")
    elif isinstance(obj, datetime.date):
        return obj.strftime("%Y-%m-%d")
    elif isinstance(obj, datetime.time):
        return obj.strftime("%H:%M:%S")


json_dumps = functools.partial(json.dumps, separators=",:", default=json_default)
