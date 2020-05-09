import datetime
from unittest.mock import patch

import pytest
import pytz

from synctogit.timezone import get_timezone


def local_datetime_pair():
    for _ in range(100):
        # If you have any better idea how to achieve this with
        # the std library -- let me know. But for now...
        local = datetime.datetime.now()
        utc = datetime.datetime.utcnow()
        if local.second <= utc.second:  # otherwise they aren't of the same minute
            y, m, d, h, mm, *_ = utc.timetuple()
            utc = datetime.datetime(
                y,
                m,
                d,
                h,
                mm,
                local.second,
                local.microsecond,
                tzinfo=datetime.timezone.utc,
            )
            break
    else:
        raise RuntimeError("Unable to converge local and utc time")

    return local, utc


@pytest.mark.parametrize(
    "timezone, naive_dt, aware_utc_dt",
    [
        (None, *local_datetime_pair()),
        (
            "Asia/Novosibirsk",
            datetime.datetime(2018, 9, 20, 17, 0, 0),
            datetime.datetime(2018, 9, 20, 10, 0, 0, tzinfo=pytz.utc),
        ),
    ],
)
def test_timezone(timezone, naive_dt, aware_utc_dt):
    config = None

    with patch("synctogit.timezone.general_timezone.get", return_value=timezone):
        tz = get_timezone(config)
        d1 = tz.normalize(tz.localize(naive_dt))
        print(d1)
        d2 = tz.normalize(aware_utc_dt.astimezone(tz))
        print(d2)
        assert d1 == d2
