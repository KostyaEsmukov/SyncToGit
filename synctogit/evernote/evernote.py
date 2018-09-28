import binascii
import datetime
import logging
from functools import wraps
from socket import error as socketerror
from time import sleep
from typing import Mapping, Optional

import evernote.edam as Edam
import evernote.edam.error.constants as Errors
import evernote.edam.limits.constants as Constants
import pytz
from cached_property import cached_property
from evernote.api.client import EvernoteClient

from . import exc, models, note_parser
from ..filename_sanitizer import normalize_filename

# import evernote.edam.userstore.constants as UserStoreConstants
# import evernote.edam.type.ttypes as Types

logger = logging.getLogger(__name__)

_RETRIES = 10
_MAXLEN_TITLE_FILENAME = 30


# required API permissions:
# Read existing notebooks
# Read existing notes


def translate_exceptions(f):
    @wraps(f)
    def c(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (socketerror, EOFError) as e:
            raise exc.EvernoteIOError(e)
        except Errors.EDAMSystemException as e:
            if e.errorCode == Errors.EDAMErrorCode.RATE_LIMIT_REACHED:
                s = float(e.rateLimitDuration + 1)
                # XXX sleep?
                raise exc.EvernoteApiRateLimitError(e, rate_limit_duration_seconds=s)
            else:
                raise exc.EvernoteApiError(e)
        except Errors.EDAMUserException as e:
            if (
                e.errorCode == Errors.EDAMErrorCode.AUTH_EXPIRED
                or e.errorCode == Errors.EDAMErrorCode.BAD_DATA_FORMAT
            ):
                raise exc.EvernoteTokenExpiredError(e)
            else:
                raise exc.EvernoteApiError(e)

    return c


def retry_ratelimited(f):
    # XXX make it configurable
    @wraps(f)
    def c(*args, **kwargs):
        for i in range(_RETRIES, 0, -1):
            try:
                return f(*args, **kwargs)
            except exc.EvernoteApiRateLimitError as e:
                if i <= 1:
                    raise
                s = e.rate_limit_duration_seconds
                logger.warning("Rate limit reached. Waiting %d seconds..." % s)
                sleep(s)
        raise RuntimeError("Should not have been reached")

    return c


class Evernote:
    # Must be thread-safe.

    def __init__(self, sandbox=True):
        self.sandbox = sandbox
        self.client = None

    @translate_exceptions
    def auth(self, access_token: str) -> None:
        self.client = EvernoteClient(token=access_token, sandbox=self.sandbox)

    def get_actual_metadata(self) -> Mapping[models.NoteGuid, models.NoteMetadata]:
        notes_metadata = self._get_all_notes_metadata()
        notebooks = self._get_notebooks()
        return self._process_metadata(notes_metadata, notebooks)

    @retry_ratelimited
    @translate_exceptions
    def _get_notebooks(self) -> Mapping[models.NotebookGuid, models.NotebookInfo]:
        note_store = self.client.get_note_store()
        notebooks = note_store.listNotebooks()
        return {
            n.guid: models.NotebookInfo(
                name=n.name,
                update_sequence_num=n.updateSequenceNum,
                stack=n.stack if n.stack is not None else None,
            )
            for n in notebooks
        }

    @retry_ratelimited
    @translate_exceptions
    def _get_all_notes_metadata(self) -> Mapping[models.NoteGuid, models.NoteInfo]:
        note_store = self.client.get_note_store()

        noteFilter = Edam.notestore.NoteStore.NoteFilter()
        noteFilter.ascending = False

        spec = Edam.notestore.NoteStore.NotesMetadataResultSpec()
        spec.includeTitle = True
        spec.includeUpdateSequenceNum = True
        spec.includeNotebookGuid = True
        spec.includeTagGuids = True
        spec.includeCreated = True
        spec.includeUpdated = True
        spec.includeDeleted = True

        res = {}
        offset = 0
        while True:

            metadata = note_store.findNotesMetadata(
                noteFilter, offset, Constants.EDAM_USER_NOTES_MAX, spec
            )

            for n in metadata.notes:
                res[n.guid] = models.NoteInfo(
                    title=n.title,
                    notebook_guid=n.notebookGuid,
                    update_sequence_num=n.updateSequenceNum,
                    tag_guids=list(n.tagGuids or []),
                    updated=self._normalize_timestamp(n.updated),
                    created=self._normalize_timestamp(n.created),
                    deleted=self._normalize_timestamp(n.deleted),
                )

            offset = metadata.startIndex + len(metadata.notes)
            if offset >= metadata.totalNotes:
                break

        return res

    def _process_metadata(
        self,
        notes_metadata: Mapping[models.NoteGuid, models.NoteInfo],
        notebooks: Mapping[models.NotebookGuid, models.NotebookInfo],
    ) -> Mapping[models.NoteGuid, models.NoteMetadata]:
        res = {}

        for note_guid, note_info in notes_metadata.items():
            notebook_info = notebooks[note_info.notebook_guid]

            note_location = [notebook_info.name, note_info.title]
            if notebook_info.stack:
                note_location = [notebook_info.stack] + note_location

            normalized_note_location = [normalize_filename(s) for s in note_location]

            file = normalize_filename(
                "%s.%s.html" % (note_info.title[:_MAXLEN_TITLE_FILENAME], note_guid)
            )

            res[note_guid] = models.NoteMetadata(
                dir=normalized_note_location[:-1],
                name=note_location,
                update_sequence_num=note_info.update_sequence_num,
                file=file,
            )

        return res

    @retry_ratelimited
    @translate_exceptions
    def get_note(self, guid: models.NoteGuid, resources_base) -> models.Note:
        note_store = self.client.get_note_store()

        # These args must be positional :(
        # Otherwise it raises:
        #
        # TypeError("getNote() missing 4 required positional arguments:
        # 'withContent', 'withResourcesData', 'withResourcesRecognition',
        # and 'withResourcesAlternateData'",)
        note = note_store.getNote(
            guid,
            True,
            True,
            False,
            False,
        )

        note_parsed = note_parser.parse(
            resources_base, note.content, note.title
        )

        resources = {}
        if note.resources:
            for r in note.resources:
                chash = binascii.hexlify(r.data.bodyHash).decode()
                resources[chash] = models.NoteResource(
                    body=r.data.body,
                    mime=r.mime,
                    filename=note_parser.resource_filename(chash, r.mime),
                )

        return models.Note(
            title=note.title,
            update_sequence_num=note.updateSequenceNum,
            guid=note.guid,
            created=self._normalize_timestamp(note.created),
            updated=self._normalize_timestamp(note.updated),
            html=note_parsed,
            resources=resources,
        )

    @cached_property
    def _timezone(self) -> datetime.tzinfo:
        return pytz.timezone(self.client.get_user_store().getUser().timezone)

    def _normalize_timestamp(self, ts: Optional[int]) -> Optional[datetime.datetime]:
        if not ts:
            return None
        return datetime.datetime.fromtimestamp(ts / 1000).replace(tzinfo=self._timezone)
