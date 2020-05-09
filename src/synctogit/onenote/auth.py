import urllib.parse

import requests_oauthlib
from prompt_toolkit.shortcuts import input_dialog, yes_no_dialog

from synctogit.service import ServiceAuthError
from synctogit.service.auth import abort_if_falsy, wait_for_enter

from . import oauth


class InteractiveAuth:
    auth_details_url = "https://docs.microsoft.com/en-us/graph/auth-overview"
    scopes_details_url = "https://docs.microsoft.com/en-us/graph/permissions-reference"

    def __init__(
        self, client_id: str, client_secret: str, redirect_uri: str, scopes: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    def run(self) -> str:
        self._ask_continue()

        # Apparently Microsoft Graph doesn't provide developer tokens,
        # like Evernote does. So the full OAuth flow seems to be the only
        # way to retrieve the token.

        is_bundled = self._ask_oauth_use_bundled()
        if not is_bundled:
            self._ask_custom_oauth_credentials()

        self._ask_oauth_scopes()

        try:
            token = self._run_oauth()
        except ServiceAuthError:
            raise
        except Exception as e:
            raise ServiceAuthError(e)
        else:
            return token

    def _ask_continue(self) -> None:
        result = yes_no_dialog(
            title="Continue authentication with OneNote (Microsoft Graph)?",
            text=(
                "OneNote (Microsoft Graph) API token is missing. "
                "Do you want to retrieve a new one?"
            ),
            no_text="Cancel",
        )
        abort_if_falsy(result)

    def _ask_oauth_use_bundled(self) -> bool:
        is_bundled = yes_no_dialog(
            title="Use bundled application?",
            text=(
                "OAuth application is identified with\n"
                "a client_id/client_secret pair.\n"
                "\n"
                "Would you like to use the bundled credentials for OAuth app\n"
                "or you want to input credentials for your own?\n"
                "\n"
                "More info on OAuth in OneNote:\n"
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
        client_id = None
        client_secret = None
        redirect_uri = None
        while not client_id:
            client_id = input_dialog(
                title="Input client_id for OAuth", text="Input client_id for OAuth.",
            )
        while not client_secret:
            client_secret = input_dialog(
                title="Input client_secret for OAuth",
                text="Input client_secret for OAuth.",
            )
        while not redirect_uri:
            redirect_uri = input_dialog(
                title="Input redirect_uri for OAuth",
                text=(
                    "Input redirect_uri for OAuth. Note that redirect_uri\n"
                    "should point to a non-existing site, otherwise the\n"
                    "temporary token will leak."
                ),
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        # TODO bundled != the one stored in the conf
        # TODO store custom consumer_* to the conf as well

    def _ask_oauth_scopes(self) -> None:
        result = yes_no_dialog(
            title="Use default OAuth scopes?",
            text=(
                "Default OAuth scopes are:\n\n"
                "%s\n\n"
                "Would you like to use them, or you would prefer\n"
                "to provide a custom set of scopes?\n"
                "If unsure, choose Keep." % self.scopes
            ),
            yes_text="Keep",
            no_text="Change",
        )
        if result:
            return

        self.scopes = input_dialog(
            title="Input OAuth scopes",
            text=(
                "Input desired OAuth scopes.\n"
                "The default OAuth scopes are:\n\n"
                "%s\n\n"
                "The list of available scopes:\n"
                "%s" % (self.scopes, self.scopes_details_url)
            ),
        )
        abort_if_falsy(self.scopes)

    def _run_oauth(self) -> str:
        while True:
            msgraph = self._msgraph()

            auth_base = oauth.authority_url + oauth.auth_endpoint
            authorization_url, state = msgraph.authorization_url(auth_base)
            msgraph.auth_state = state

            self._present_authorize_url(authorization_url)
            redirect_url = self._ask_redirection_url()

            try:
                query = urllib.parse.urlsplit(redirect_url).query
                state = urllib.parse.parse_qs(query)["state"][0]
            except Exception as e:
                self._ask_try_again_for_invalid_redirect_url(e)
            else:
                break

        if state != msgraph.auth_state:
            raise RuntimeError(
                "The `state` from the `redirect` URL does not match "
                "the one of the `authorize` URL! "
                "Perhaps you should try again."
            )

        token = msgraph.fetch_token(
            oauth.authority_url + oauth.token_endpoint,
            client_secret=self.client_secret,
            authorization_response=redirect_url,
        )
        return token

    def _msgraph(self) -> requests_oauthlib.OAuth2Session:
        return requests_oauthlib.OAuth2Session(
            self.client_id,
            scope=[s.strip() for s in self.scopes.split(",")],
            redirect_uri=self.redirect_uri,
        )

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
                "%s?code=...&state=...\n"
                "\n"
                "Do you want to try again?"
            )
            % (repr(e), self.redirect_uri),
            no_text="Cancel",
        )
        abort_if_falsy(result)
