import base64

from synctogit.config import Config
from synctogit.service import InvalidAuthSession, BaseAuthSession, BaseAuth
from .auth import InteractiveAuth, UserCancelledError

__all__ = (
    "EvernoteAuth",
    "EvernoteAuthSession",
    "UserCancelledError",
)

# python -c "import base64; print base64.b64encode('123')"
_CONSUMER_KEY = 'kostya0shift-0653'
_CONSUMER_SECRET = base64.b64decode('M2EwMWJkYmJhNDVkYTYwMg==').decode()
_CALLBACK_URL = 'https://localhost:63543/non-existing-url'  # non existing link


class EvernoteAuthSession(BaseAuthSession):
    def __init__(self, token: str) -> None:
        self.token = token

    @classmethod
    def load_from_config(cls, config: Config) -> 'EvernoteAuthSession':
        try:
            encoded_token = config.get_str('evernote', 'token')
        except ValueError:
            raise InvalidAuthSession('Evernote token is missing in config')

        try:
            token = base64.b64decode(encoded_token).decode()
        except Exception:
            raise InvalidAuthSession('Evernote token is invalid')

        return cls(token)

    def save_to_config(self, config: Config) -> None:
        encoded_token = base64.b64encode(self.token.encode()).decode()
        config.set('evernote', 'token', encoded_token)


class EvernoteAuth(BaseAuth[EvernoteAuthSession]):
    @classmethod
    def interactive_auth(cls, config: Config) -> EvernoteAuthSession:
        token = InteractiveAuth(
            consumer_key=config.get_str(
                "evernote", "consumer_key", _CONSUMER_KEY
            ),
            consumer_secret=config.get_str(
                "evernote", "consumer_secret", _CONSUMER_SECRET
            ),
            callback_url=config.get_str(
                "evernote", "callback_url", _CALLBACK_URL
            ),
            sandbox=config.get_bool(
                'evernote', 'sandbox', False
            ),
        ).run()
        return EvernoteAuthSession(token)
