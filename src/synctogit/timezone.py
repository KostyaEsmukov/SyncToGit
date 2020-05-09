import pytz
import tzlocal

from synctogit.config import Config, StrConfigItem

general_timezone = StrConfigItem("general", "timezone", None)


def get_timezone(config: Config) -> pytz.BaseTzInfo:
    """Returns the pytz timezone in which the datetimes should
    be displayed to the user.
    """
    timezone_name = general_timezone.get(config)
    if timezone_name:
        timezone = pytz.timezone(timezone_name)
    else:
        timezone = tzlocal.get_localzone()
    return timezone
