from prompt_toolkit.shortcuts import input_dialog, yes_no_dialog

from synctogit.service.auth import abort_if_falsy


class InteractiveAuth:
    todoist_prefs_url = "https://todoist.com/prefs/integrations"

    def run(self) -> str:
        self._ask_continue()
        api_token = self._ask_api_token()
        return api_token

    def _ask_continue(self) -> None:
        result = yes_no_dialog(
            title="Continue authentication with Todoist?",
            text="Todoist API token is missing. Do you want to retrieve a new one?",
            no_text="Cancel",
        )
        abort_if_falsy(result)

    def _ask_api_token(self) -> str:
        api_token = input_dialog(
            title="Input your API Token",
            text=(
                "Open the following url in your browser to retrieve "
                "an API Token:\n"
                "\n"
                "%s\n"
                "\n"
                "Paste your API Token to the prompt below.\n"
            )
            % self.todoist_prefs_url,
        )
        abort_if_falsy(api_token)
        return api_token
