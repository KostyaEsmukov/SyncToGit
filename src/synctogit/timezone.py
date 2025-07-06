import pytz
import tzlocal

from synctogit.config import Config, StrConfigItem

general_timezone = StrConfigItem("general", "timezone", None)


def get_timezone(config: Config) -> pytz.BaseTzInfo:
    """Returns the pytz timezone in which the datetimes should
    be displayed to the user.
    """
    timezone_name = general_timezone.get(config)
    if not timezone_name:
        timezone_name = tzlocal.get_localzone_name()
    timezone = pytz.timezone(timezone_name)
    return timezone
