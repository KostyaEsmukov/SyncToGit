import urllib.parse

import requests_oauthlib

from . import oauth


def auth(client_id, client_secret, redirect_uri, scopes):

    MSGRAPH = requests_oauthlib.OAuth2Session(
        client_id,
        scope=[s.strip() for s in scopes.split(',')],
        redirect_uri=redirect_uri,
    )

    auth_base = oauth.authority_url + oauth.auth_endpoint
    authorization_url, state = MSGRAPH.authorization_url(auth_base)
    MSGRAPH.auth_state = state

    print(authorization_url)
    redirect_url = input()

    query = urllib.parse.urlsplit(redirect_url).query
    state = urllib.parse.parse_qs(query)["state"][0]
    if state != MSGRAPH.auth_state:
        raise Exception('state returned to redirect URL does not match!')

    token = MSGRAPH.fetch_token(
        oauth.authority_url + oauth.token_endpoint,
        client_secret=client_secret,
        authorization_response=redirect_url,
    )
    return token
