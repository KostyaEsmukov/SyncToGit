import re

resource_url_pattern = re.compile(
    r"^https://graph.microsoft.com/v1.0"
    r"/.+/onenote/resources/([^/]+)/content(\?.+)$",
    flags=re.I
)
