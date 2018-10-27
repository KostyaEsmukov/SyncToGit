from synctogit.service import ServiceImplementation

try:
    from . import service
except ImportError:
    is_available = False
else:
    is_available = True


def get_service_implementation():
    if not is_available:
        raise ValueError(
            "Onenote is not available. Please install missing extras with "
            "`pip install 'synctogit[onenote]'`."
        )
    return ServiceImplementation(
        auth_session=service.MicrosoftGraphAuthSession,
        auth=service.MicrosoftGraphAuth,
        sync=service.OneNoteSync,
    )
