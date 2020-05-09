from typing import TypeVar

TNoteKey = TypeVar("TNoteKey", bound=str)  # must be filesystem safe
TNoteMetadata = TypeVar("TNoteMetadata")
TNote = TypeVar("TNote")
