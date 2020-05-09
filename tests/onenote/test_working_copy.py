import datetime

import pytest
import pytz

from synctogit.onenote.models import OneNotePageMetadata
from synctogit.onenote.working_copy import OneNoteWorkingCopy

tz1 = pytz.timezone("Europe/Moscow")
tz2 = pytz.timezone("Asia/Novosibirsk")


@pytest.mark.parametrize(
    "d1, d2, is_updated",
    [
        (
            # Equal -- not updated
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            False,
        ),
        (
            # One is greater -- updated
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            tz1.localize(datetime.datetime(2018, 10, 2, 10, 10, 10)),
            True,
        ),
        (
            # Another is greater -- updated
            tz1.localize(datetime.datetime(2018, 10, 2, 10, 10, 10)),
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            True,
        ),
        (
            # Same local dates in different timezones -- updated
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            tz2.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            True,
        ),
        (
            # Same points in time in different timezones -- not updated
            tz1.localize(datetime.datetime(2018, 10, 1, 10, 10, 10)),
            tz2.localize(datetime.datetime(2018, 10, 1, 14, 10, 10)),
            False,
        ),
    ],
)
def test_is_updated_note(d1, d2, is_updated):
    m1 = OneNotePageMetadata(
        dir=("a", "b"), file="c", name=("a", "b", "c"), last_modified=d1,
    )
    m2 = OneNotePageMetadata(
        dir=("a", "b"), file="c", name=("a", "b", "c"), last_modified=d2,
    )
    assert is_updated is OneNoteWorkingCopy._is_updated_note(m1, m2)
