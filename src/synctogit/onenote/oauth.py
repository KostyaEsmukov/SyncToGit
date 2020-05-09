import os
import re

# Inspired by
# https://github.com/microsoftgraph/python-sample-auth/blob/master/sample_requests.py

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_IGNORE_SCOPE_CHANGE"] = "1"

authority_url = "https://login.microsoftonline.com/common"

auth_endpoint = "/oauth2/v2.0/authorize"
token_endpoint = "/oauth2/v2.0/token"

base_api_url = "https://graph.microsoft.com/v1.0/me/onenote"

resource_url_pattern = re.compile(
    r"^https://graph.microsoft.com/v1.0"
    r"/.+/onenote/resources/([^/]+)/content(\?.+)$",
    flags=re.I,
)
