from contextlib import ExitStack
from unittest.mock import patch

import pytest

import synctogit.todoist.auth
from synctogit.todoist.auth import InteractiveAuth


@pytest.fixture
def mock_prompt_toolkit():
    with ExitStack() as st:
        shortcuts = ["input_dialog", "yes_no_dialog"]
        mocked = {}
        mocked.update(
            {
                m: st.enter_context(patch.object(synctogit.todoist.auth, m))
                for m in shortcuts
            }
        )
        yield mocked


def test_flow_api_token_auth(mock_prompt_toolkit):
    m = mock_prompt_toolkit
    # Continue? -- True
    # API Token? -- YOU.WON.THIS.TOKEN
    m["yes_no_dialog"].side_effect = [True]
    m["input_dialog"].side_effect = [
        "YOU.WON.THIS.TOKEN",
    ]

    auth = InteractiveAuth()
    assert auth.run() == "YOU.WON.THIS.TOKEN"
