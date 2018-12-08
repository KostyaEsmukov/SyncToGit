from contextlib import ExitStack
from unittest.mock import Mock, call, patch

import pytest
from evernote.api.client import EvernoteClient

import synctogit.evernote.auth
from synctogit.evernote.auth import InteractiveAuth


@pytest.fixture
def mock_prompt_toolkit():
    with ExitStack() as st:
        shortcuts = ["button_dialog", "input_dialog", "yes_no_dialog"]
        mocked = {}
        mocked.update(
            {
                m: st.enter_context(patch.object(synctogit.evernote.auth, m))
                for m in shortcuts
            }
        )

        # Not really from the prompt_toolkit, but it is just convenient
        # to mock it there as well.
        mocked["wait_for_enter"] = st.enter_context(
            patch.object(synctogit.evernote.auth, "wait_for_enter")
        )
        yield mocked


@pytest.fixture
def auth_params():
    return dict(
        consumer_key="c88l-gal",
        consumer_secret="p0sswaD",
        callback_url="https://localhost:63543/non-existing-url",
        sandbox=True,
    )


@pytest.fixture
def mock_evernote_client():
    evernote_client = Mock(spec=EvernoteClient)
    with patch.object(
        synctogit.evernote.auth.InteractiveAuth,
        "_evernote_client",
        return_value=evernote_client,
    ):
        yield evernote_client


def test_flow_bundled_oauth(mock_evernote_client, mock_prompt_toolkit, auth_params):
    m = mock_prompt_toolkit
    # Continue? -- True
    # Method? -- oauth
    # Bundled? -- True
    # Redirection url? -- https://localhost...
    m["yes_no_dialog"].side_effect = [True, True]
    m["button_dialog"].side_effect = ["oauth"]
    m["input_dialog"].side_effect = [
        "https://localhost:63543/non-existing-url?oauth_token=AA&oauth_verifier=BB",
    ]

    mock_evernote_client.get_request_token.side_effect = [
        {
            "oauth_token_secret": "WHOAH",
            "oauth_token": "AAAAAA.OOOOOOO.UUUUUUUU",
            "oauth_callback_confirmed": "true",
        }
    ]
    mock_evernote_client.get_authorize_url.side_effect = [
        "https://www.evernote.com/OAuth.action?oauth_token=AAAAAA.OOOOOOO.UUUUUUUU",
    ]
    mock_evernote_client.get_access_token.side_effect = ["YOU.WON.THIS.TOKEN"]
    auth = InteractiveAuth(**auth_params)
    assert auth.run() == "YOU.WON.THIS.TOKEN"

    assert mock_evernote_client.get_access_token.call_args == call(
        "AAAAAA.OOOOOOO.UUUUUUUU", "WHOAH", "BB"
    )
    assert 1 == m["wait_for_enter"].call_count


# TODO:
# - oauth custom app flow
# - devtoken flow
# - aborts
# - token validation
