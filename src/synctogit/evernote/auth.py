import urllib.parse

from evernote.api.client import EvernoteClient
from prompt_toolkit.shortcuts import button_dialog, input_dialog, yes_no_dialog

from synctogit.service import ServiceAuthError
from synctogit.service.auth import abort_if_falsy, wait_for_enter

from .evernote import translate_exceptions


class InteractiveAuth:
    auth_details_url = "https://dev.evernote.com/doc/articles/authentication.php"
    devtokens_details_url = "https://dev.evernote.com/doc/articles/dev_tokens.php"

    devtoken_prod_url = "https://www.evernote.com/api/DeveloperToken.action"
    devtoken_sandbox_url = "https://sandbox.evernote.com/api/DeveloperToken.action"

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str,
        sandbox: bool = True,
    ) -> None:
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.callback_url = callback_url
        self.sandbox = sandbox

    @translate_exceptions
    def run(self) -> str:
        self._ask_continue()

        auth_method = self._ask_auth_method()
        if auth_method == "devtoken":
            token = self._ask_devtoken()
            return token

        assert auth_method == "oauth"

        is_bundled = self._ask_oauth_use_bundled()
        if not is_bundled:
            self._ask_custom_oauth_credentials()

        try:
            token = self._run_oauth()
        except ServiceAuthError:
            raise
        except Exception as e:
            raise ServiceAuthError(e)
        else:
            return token

    def _run_oauth(self) -> str:
        client = self._evernote_client()

        while True:
            request_token = client.get_request_token(self.callback_url)
            self._present_authorize_url(client.get_authorize_url(request_token))
            url = self._ask_redirection_url()
            try:
                query = urllib.parse.urlsplit(url).query
                oauth_verifier = urllib.parse.parse_qs(query)["oauth_verifier"][0]
            except Exception as e:
                self._ask_try_again_for_invalid_redirect_url(e)
            else:
                break

        return client.get_access_token(
            request_token["oauth_token"],
            request_token["oauth_token_secret"],
            oauth_verifier,
        )

    def _ask_continue(self) -> None:
        result = yes_no_dialog(
            title="Continue authentication with Evernote?",
            text="Evernote API token is missing. Do you want to retrieve a new one?",
            no_text="Cancel",
        )
        abort_if_falsy(result)

    def _ask_auth_method(self) -> str:
        result = button_dialog(
            title="Choose authentication method",
            text=(
                "Evernote provides two authentication methods:\n"
                "Developer Token and OAuth. Which one would you like to use?\n"
                "\n"
                "If unsure, choose OAuth.\n"
                "\n"
                "More info:\n"
                "%s"
            )
            % self.auth_details_url,
            buttons=[
                ("OAuth", "oauth"),
                ("Dev Token", "devtoken"),
                ("Cancel", "cancel"),
            ],
        )
        abort_if_falsy(result != "cancel")
        return result

    def _ask_devtoken(self) -> str:
        url = {
            # fmt: off
            False: self.devtoken_prod_url,
            True: self.devtoken_sandbox_url,
            # fmt: on
        }[self.sandbox]
        devtoken = input_dialog(
            title="Input your Developer Token",
            text=(
                "Open the following url in your browser to retrieve "
                "a Developer Token:\n"
                "\n"
                "%s\n"
                "\n"
                "Paste your Developer Token to the prompt below.\n"
                "\n"
                "More about Developer Tokens:\n"
                "%s"
            )
            % (url, self.devtokens_details_url),
        )
        abort_if_falsy(devtoken)
        return devtoken

    def _ask_oauth_use_bundled(self) -> bool:
        is_bundled = yes_no_dialog(
            title="Use bundled application?",
            text=(
                "OAuth application is identified with\n"
                "a consumer_key/consumer_secret pair.\n"
                "\n"
                "Would you like to use the bundled credentials for OAuth app\n"
                "or you want to input credentials for your own?\n"
                "\n"
                "More info on OAuth in Evernote:\n"
                "%s\n"
                "\n"
                "If unsure, choose Bundled."
            )
            % self.auth_details_url,
            yes_text="Bundled",
            no_text="Custom",
        )
        return is_bundled

    def _ask_custom_oauth_credentials(self) -> None:
        consumer_key = None
        consumer_secret = None
        callback_url = None
        while not consumer_key:
            consumer_key = input_dialog(
                title="Input consumer_key for OAuth",
                text="Input consumer_key for OAuth.",
            )
        while not consumer_secret:
            consumer_secret = input_dialog(
                title="Input consumer_secret for OAuth",
                text="Input consumer_secret for OAuth.",
            )
        while not callback_url:
            callback_url = input_dialog(
                title="Input callback_url for OAuth",
                text=(
                    "Input callback_url for OAuth. Note that callback_url\n"
                    "should point to a non-existing site, otherwise the\n"
                    "temporary token will leak."
                ),
            )
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.callback_url = callback_url
        # TODO bundled != the one stored in the conf
        # TODO store custom consumer_* to the conf as well

    def _evernote_client(self) -> EvernoteClient:
        client = EvernoteClient(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            sandbox=self.sandbox,
        )
        return client

    def _present_authorize_url(self, url: str) -> None:
        print()
        print("Open the following URL in your browser:")
        print(url)
        print("Press Enter to continue")
        wait_for_enter()

    def _ask_redirection_url(self) -> str:
        url = input_dialog(
            title="Input the redirection url",
            text=(
                "Follow the steps on the opened page to authorize\n"
                "this application.\n"
                "\n"
                "After giving access you will be redirected to\n"
                "a non-existing page – this is intended.\n"
                "\n"
                "Enter the URL of that page to the prompt below:"
            ),
        )
        abort_if_falsy(url)
        return url

    def _ask_try_again_for_invalid_redirect_url(self, e: Exception) -> None:
        result = yes_no_dialog(
            title="Invalid redirect url. Try again?",
            text=(
                "The given redirect url is invalid:\n"
                "%s\n"
                "\n"
                "It should look like that:\n"
                "%s?oauth_token=...&oauth_verifier=...\n"
                "\n"
                "Do you want to try again?"
            )
            % (repr(e), self.callback_url),
            no_text="Cancel",
        )
        abort_if_falsy(result)
