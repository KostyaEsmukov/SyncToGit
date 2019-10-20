from typing import Any

from .exc import UserCancelledError


def abort_if_falsy(result: Any) -> None:
    if not result:
        raise UserCancelledError("Cancelled by user")


def wait_for_enter() -> None:
    input()
