import os
from datetime import datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytz
import vcr
from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteMetadata
from evernote.edam.type.ttypes import (
    Accounting,
    Data,
    Note,
    NoteAttributes,
    Notebook,
    NotebookRestrictions,
    Resource,
    ResourceAttributes,
    User,
)

from synctogit.evernote import models
from synctogit.evernote.evernote import Evernote

vcr_dtd = vcr.VCR(cassette_library_dir=os.path.dirname(__file__))


@pytest.fixture
def evernote_user_timezone_name():
    return "Europe/Moscow"


@pytest.fixture
def evernote_user_timezone(evernote_user_timezone_name):
    return pytz.timezone(evernote_user_timezone_name)


@pytest.fixture
def evernote_user(evernote_user_timezone_name):
    return User(
        timezone=evernote_user_timezone_name,
        id=1234,
        businessUserInfo=None,
        attributes=None,
        privilege=1,
        email=None,
        username="johndoe",
        accounting=Accounting(
            uploadLimitEnd=1539932400000,
            premiumLockUntil=None,
            nextPaymentDue=None,
            lastFailedChargeReason=None,
            premiumCommerceService=None,
            premiumSubscriptionNumber=None,
            premiumServiceStatus=0,
            unitPrice=None,
            currency=None,
            unitDiscount=None,
            businessRole=None,
            uploadLimitNextMonth=62914560,
            updated=None,
            lastSuccessfulCharge=None,
            businessName=None,
            premiumServiceSKU=None,
            premiumServiceStart=None,
            premiumOrderNumber=None,
            uploadLimit=62914560,
            lastFailedCharge=None,
            businessId=None,
            nextChargeDate=None,
            lastRequestedCharge=None,
        ),
        shardId="s999999",
        deleted=None,
        active=True,
        premiumInfo=None,
        updated=None,
        created=None,
        name=None,
    )


@pytest.fixture
def evernote(evernote_user):
    client = Mock(EvernoteClient)
    client.get_user_store().getUser.return_value = evernote_user

    e = Evernote()
    e.client = client
    return e


@pytest.mark.parametrize("stack", [None, "надпроект ❤️"])
def test_map_to_notebook_info(evernote, stack):
    guid = str(uuid4())
    notebook = Notebook(
        sharedNotebooks=None,
        restrictions=NotebookRestrictions(
            noShareNotes=None,
            noExpungeTags=True,
            noSetParentTag=None,
            noExpungeNotebook=True,
            noUpdateTags=None,
            noReadNotes=None,
            noEmailNotes=True,
            noPublishToPublic=None,
            noCreateTags=None,
            noSetDefaultNotebook=None,
            updateWhichSharedNotebookRestrictions=None,
            noExpungeNotes=True,
            expungeWhichSharedNotebookRestrictions=2,
            noPublishToBusinessLibrary=True,
            noSetNotebookStack=None,
            noCreateNotes=None,
            noUpdateNotebook=None,
            noUpdateNotes=None,
            noSendMessageToRecipients=None,
            noCreateSharedNotebooks=None,
        ),
        guid=guid,
        defaultNotebook=False,
        name="проектик ✨",
        updateSequenceNum=1234,
        contact=None,
        publishing=None,
        stack=stack,
        serviceCreated=1521115581000,
        serviceUpdated=1526495234000,
        published=None,
        businessNotebook=None,
        sharedNotebookIds=None,
    )

    expected_notebook_info = models.NotebookInfo(
        name="проектик ✨", update_sequence_num=1234, stack=stack
    )

    notebook_info = evernote._map_to_notebook_info(notebook)
    assert notebook_info == expected_notebook_info


@pytest.mark.parametrize("tag_guids", [None, [str(uuid4()), str(uuid4())]])
def test_map_to_note_info(evernote, evernote_user_timezone, tag_guids):
    tzinfo = evernote_user_timezone
    guid = str(uuid4())
    notebook_guid = str(uuid4())
    note_metadata = NoteMetadata(
        updateSequenceNum=1234,
        updated=1379683729000,
        title="заметка ✨",
        created=1378136167000,
        contentLength=None,
        largestResourceMime=None,
        largestResourceSize=None,
        guid=guid,
        tagGuids=tag_guids,
        notebookGuid=notebook_guid,
        attributes=None,
        deleted=None,
    )

    expected_note_info = models.NoteInfo(
        title="заметка ✨",
        notebook_guid=notebook_guid,
        update_sequence_num=1234,
        tag_guids=tag_guids or [],
        updated=tzinfo.localize(datetime(2013, 9, 20, 17, 28, 49)),
        created=tzinfo.localize(datetime(2013, 9, 2, 19, 36, 7)),
        deleted=None,
    )

    note_info = evernote._map_to_note_info(note_metadata)
    assert note_info == expected_note_info


@pytest.mark.parametrize(
    "stack, stack_normalized", [(None, None), ("надпроект ❤️", "надпроект _2764_fe0f")]
)
@pytest.mark.parametrize("tag_guids", [None, [str(uuid4()), str(uuid4())]])
def test_map_to_note_metadata(
    evernote, evernote_user_timezone, stack, stack_normalized, tag_guids
):
    tzinfo = evernote_user_timezone
    note_guid = str(uuid4())
    notebook_guid = str(uuid4())
    notebook_info = models.NotebookInfo(
        name="проектик ✨", update_sequence_num=100, stack=stack
    )
    note_info = models.NoteInfo(
        title="заметка ✨",
        notebook_guid=notebook_guid,
        update_sequence_num=1234,
        tag_guids=tag_guids or [],
        updated=tzinfo.localize(datetime(2013, 9, 20, 17, 28, 49)),
        created=tzinfo.localize(datetime(2013, 9, 2, 19, 36, 7)),
        deleted=None,
    )

    if stack:
        dir = (stack_normalized, "проектик _2728")
        name = (stack, "проектик ✨", "заметка ✨")
    else:
        dir = ("проектик _2728",)
        name = ("проектик ✨", "заметка ✨")

    expected_note_metadata = models.NoteMetadata(
        dir=dir,
        name=name,
        update_sequence_num=1234,
        file="заметка _2728.%s.html" % note_guid,
    )

    note_metadata = evernote._map_to_note_metadata(notebook_info, note_guid, note_info)
    assert note_metadata == expected_note_metadata


@vcr_dtd.use_cassette("cassette_dtd")
def test_map_to_note(evernote, evernote_user_timezone):
    tzinfo = evernote_user_timezone
    note_guid = str(uuid4())
    notebook_guid = str(uuid4())
    resources_base = "../../Resources/%s/" % note_guid
    note = Note(
        contentHash=b"\x03\x1b:\x07\xf4\x99\xeb\x84\xbc\x99\xd8\xa1\xa3V\x07\xc1",
        created=1538162492000,
        resources=None,
        tagNames=None,
        content=(
            '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
            "<en-note><div>1</div></en-note>"
        ),
        attributes=NoteAttributes(
            creatorId=None,
            subjectDate=None,
            lastEditedBy=None,
            placeName=None,
            reminderTime=None,
            classifications=None,
            altitude=None,
            reminderOrder=None,
            reminderDoneTime=None,
            applicationData=None,
            source="desktop.mac",
            shareDate=None,
            latitude=None,
            author="user@example.org",
            sourceURL=None,
            lastEditorId=None,
            contentClass=None,
            sourceApplication=None,
            longitude=None,
        ),
        notebookGuid=notebook_guid,
        updateSequenceNum=1234,
        guid=note_guid,
        title="заметка ✨",
        tagGuids=None,
        deleted=None,
        contentLength=96,
        active=True,
        updated=1538162496000,
    )

    expected_note = models.Note(
        title="заметка ✨",
        update_sequence_num=1234,
        guid=note_guid,
        created=tzinfo.localize(datetime(2018, 9, 28, 22, 21, 32)),
        updated=tzinfo.localize(datetime(2018, 9, 28, 22, 21, 36)),
        html=(
            "<html>\n"
            "<head>\n"
            '<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />\n'
            "<title>заметка ✨</title>\n"
            "\n"
            "</head>\n"
            '<body style="word-wrap: break-word; -webkit-nbsp-mode: space; '
            '-webkit-line-break: after-white-space;">\n'
            "<div>1</div>\n"
            "\n"
            "</body>\n"
            "</html>\n"
        ).encode(),
        resources={},
    )

    got_note = evernote._map_to_note(note, resources_base)
    assert got_note == expected_note


@vcr_dtd.use_cassette("cassette_dtd")
def test_map_to_note_with_resources(evernote, evernote_user_timezone):
    tzinfo = evernote_user_timezone
    note_guid = str(uuid4())
    notebook_guid = str(uuid4())
    resource_guid = str(uuid4())
    resources_base = "../../Resources/%s/" % note_guid
    resource_body = b"\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82 q\n"
    note = Note(
        active=True,
        content=(
            '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
            "<en-note><div>1"
            '<en-media hash="a9f6d89f06411341248f85e22ea4fd4f" type="text/plain" '
            'style="cursor:pointer;" /></div>'
            "<div><br /></div>"
            "</en-note>"
        ),
        guid=note_guid,
        tagGuids=None,
        tagNames=None,
        notebookGuid=notebook_guid,
        deleted=None,
        created=1538162492000,
        contentLength=207,
        updated=1538163219000,
        title="заметка ✨",
        resources=[
            Resource(
                active=True,
                duration=None,
                guid=resource_guid,
                data=Data(
                    size=15,
                    bodyHash=b"\xa9\xf6\xd8\x9f\x06A\x13A$\x8f\x85\xe2.\xa4\xfdO",
                    body=resource_body,
                ),
                height=0,
                width=0,
                mime="text/plain",
                recognition=None,
                alternateData=None,
                updateSequenceNum=1234,
                attributes=ResourceAttributes(
                    clientWillIndex=None,
                    longitude=None,
                    attachment=False,
                    timestamp=None,
                    fileName="привет.txt",
                    latitude=None,
                    cameraMake=None,
                    altitude=None,
                    cameraModel=None,
                    recoType=None,
                    sourceURL=None,
                    applicationData=None,
                ),
                noteGuid=note_guid,
            )
        ],
        attributes=NoteAttributes(
            reminderOrder=None,
            longitude=None,
            subjectDate=None,
            contentClass=None,
            lastEditedBy=None,
            shareDate=None,
            latitude=None,
            classifications=None,
            source="desktop.mac",
            creatorId=None,
            sourceApplication=None,
            altitude=None,
            reminderDoneTime=None,
            lastEditorId=None,
            placeName=None,
            reminderTime=None,
            author="user@example.org",
            sourceURL=None,
            applicationData=None,
        ),
        updateSequenceNum=1234,
        contentHash=b"g\x15\xd1\xe5\x8c&NX:\xb5w\x0e%\xeb04",
    )

    expected_note = models.Note(
        title="заметка ✨",
        update_sequence_num=1234,
        guid=note_guid,
        created=tzinfo.localize(datetime(2018, 9, 28, 22, 21, 32)),
        updated=tzinfo.localize(datetime(2018, 9, 28, 22, 33, 39)),
        html=(
            "<html>\n"
            "<head>\n"
            '<meta content="text/html; charset=UTF-8" http-equiv="Content-Type" />\n'
            "<title>заметка ✨</title>\n"
            "\n"
            "</head>\n"
            '<body style="word-wrap: break-word; -webkit-nbsp-mode: space; '
            '-webkit-line-break: after-white-space;">\n'
            "<div>1"
            '<a href="../../Resources/%s/a9f6d89f06411341248f85e22ea4fd4f.txt">'
            "Document of type text/plain</a></div>"
            "\n"
            "<div><br />\n"
            "</div>\n"
            "\n"
            "</body>\n"
            "</html>\n" % note_guid
        ).encode(),
        resources={
            "a9f6d89f06411341248f85e22ea4fd4f": models.NoteResource(
                body=resource_body,
                mime="text/plain",
                filename="a9f6d89f06411341248f85e22ea4fd4f.txt",
            ),
        },
    )

    got_note = evernote._map_to_note(note, resources_base)
    assert got_note == expected_note
