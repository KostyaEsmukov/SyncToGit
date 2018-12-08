from contextlib import ExitStack
from unittest.mock import Mock, call, patch

import pytest
import requests_oauthlib

import synctogit.onenote.auth
from synctogit.onenote.auth import InteractiveAuth


@pytest.fixture
def mock_prompt_toolkit():
    with ExitStack() as st:
        shortcuts = ["input_dialog", "yes_no_dialog"]
        mocked = {}
        mocked.update(
            {
                m: st.enter_context(patch.object(synctogit.onenote.auth, m))
                for m in shortcuts
            }
        )

        # Not really from the prompt_toolkit, but it is just convenient
        # to mock it there as well.
        mocked["wait_for_enter"] = st.enter_context(
            patch.object(synctogit.onenote.auth, "wait_for_enter")
        )
        yield mocked


@pytest.fixture
def auth_params():
    return dict(
        client_id="c88l-gal",
        client_secret="p0sswaD",
        redirect_uri="https://localhost:63543/non-existing-url",
        scopes="offline_access, User.Read, Notes.Read, Notes.Read.All",
    )


@pytest.fixture
def mock_msgraph():
    msgraph = Mock(spec=requests_oauthlib.OAuth2Session)
    with patch.object(
        synctogit.onenote.auth.InteractiveAuth, "_msgraph", return_value=msgraph
    ):
        yield msgraph


def test_flow_bundled_oauth(mock_msgraph, mock_prompt_toolkit, auth_params):
    m = mock_prompt_toolkit
    # Continue? -- True
    # Bundled? -- True
    # Keep scopes? -- True
    # Redirection url? -- https://localhost...
    m["yes_no_dialog"].side_effect = [True, True, True]
    m["input_dialog"].side_effect = [
        "https://localhost:63543/non-existing-url?code=AA&state=BB"
    ]

    mock_msgraph.authorization_url.side_effect = [
        ("https://login.microsoftonline.com/...", "BB")
    ]
    mock_msgraph.fetch_token.side_effect = ["YOU.WON.THIS.TOKEN"]
    auth = InteractiveAuth(**auth_params)
    assert auth.run() == "YOU.WON.THIS.TOKEN"

    assert mock_msgraph.fetch_token.call_args == call(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        authorization_response=(
            "https://localhost:63543/non-existing-url?code=AA&state=BB"
        ),
        client_secret="p0sswaD",
    )
    assert 1 == m["wait_for_enter"].call_count
