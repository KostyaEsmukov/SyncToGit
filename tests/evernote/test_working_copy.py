from uuid import uuid4

import pytest

from synctogit.evernote.models import NoteMetadata
from synctogit.evernote.working_copy import Changeset, EvernoteWorkingCopy


@pytest.mark.parametrize(
    'dir, url',
    [
        (
            ("Eleven", "Haircut"),
            '../../../Resources/eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7/',
        ),
        (
            ("Eleven",),
            '../../Resources/eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7/',
        ),
    ]
)
def test_relative_resources_url(dir, url):
    metadata = NoteMetadata(
        dir=dir, name="mark", update_sequence_num=123, file="s1.html"
    )
    got_url = EvernoteWorkingCopy.get_relative_resources_url(
        "eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7", metadata
    )
    assert got_url == url


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize("present_in", ["working_copy", "evernote"])
def test_calculate_changes_removals(force_update, present_in):
    guid = str(uuid4())
    note = NoteMetadata(
        dir=('aaa', 'bbb'),
        file='ccc.%s.html' % guid,
        name=('aaa', 'bbb', 'ccc'),
        update_sequence_num=42,
    )
    evernote_metadata = {}
    working_copy_metadata = {}
    dict(
        working_copy=working_copy_metadata,
        evernote=evernote_metadata,
    )[present_in][guid] = note

    new = {}
    delete = {}
    dict(
        working_copy=delete,
        evernote=new,
    )[present_in][guid] = note

    expected_changeset = Changeset(
        new=new,
        update={},
        delete=delete,
    )

    got_changeset = EvernoteWorkingCopy.calculate_changes(
        evernote_metadata=evernote_metadata,
        working_copy_metadata=working_copy_metadata,
        force_update=force_update,
    )
    assert got_changeset == expected_changeset


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize("change", ["guid", "dir", "file", "seq", None])
def test_calculate_changes_detects_moves(force_update, change):
    guid = str(uuid4())
    guid_git = str(uuid4()) if change == 'guid' else guid

    dir = ('aaa', 'bbb')
    dir_git = ('zzz', 'bbb') if change == 'dir' else dir

    name_part = 'beast'
    name_part_git = 'beauty' if change == 'file' else name_part

    name = dir + (name_part,)
    name_git = dir_git + (name_part_git,)

    file = '%s.%s.html' % (name_part, guid)
    file_git = '%s.%s.html' % (name_part_git, guid)

    update_sequence_num = 6772
    update_sequence_num_git = 7000 if change == 'seq' else update_sequence_num

    evernote_metadata = {
        guid: NoteMetadata(
            dir=dir,
            file=file,
            name=name,
            update_sequence_num=update_sequence_num,
        )
    }
    working_copy_metadata = {
        guid_git: NoteMetadata(
            dir=dir_git,
            file=file_git,
            name=name_git,
            update_sequence_num=update_sequence_num_git,
        )
    }

    new = {}
    update = {}
    delete = {}
    if change == 'seq':
        assert guid == guid_git
        update = {guid: evernote_metadata[guid]}
    elif change is None:
        if force_update:
            assert guid == guid_git
            update = {guid: evernote_metadata[guid]}
    else:
        new = {guid: evernote_metadata[guid]}
        delete = {guid_git: working_copy_metadata[guid_git]}

    expected_changeset = Changeset(
        new=new,
        update=update,
        delete=delete,
    )

    got_changeset = EvernoteWorkingCopy.calculate_changes(
        evernote_metadata=evernote_metadata,
        working_copy_metadata=working_copy_metadata,
        force_update=force_update,
    )
    assert got_changeset == expected_changeset


# XXX save_note
# on update note resources are deleted
# note resources are saved as well
# note dir tree is created


# XXX _process_note_metadata_futures


# XXX !!!!!!! also remove files in resources dir and dirs in the notes dir?
