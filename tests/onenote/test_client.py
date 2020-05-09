from unittest.mock import MagicMock, call, patch, sentinel

import pytest
import requests
from oauthlib.oauth2 import TokenExpiredError

from synctogit.onenote.client import OauthClient, OneNoteAPI
from synctogit.service import ServiceAPIError


@patch.object(OauthClient, "_get_client")
def test_oauth_client_get_refresh_token(mock_get_client):
    client_obsolete = MagicMock()
    client_obsolete.get.side_effect = [
        TokenExpiredError,
    ]

    client_refreshed = MagicMock()
    response = MagicMock()
    client_refreshed.get.return_value = response

    mock_get_client.side_effect = [
        client_obsolete,
        client_refreshed,
    ]
    oauth_client = OauthClient(client_id="", client_secret="", token={})
    assert response is oauth_client.get(sentinel.url)
    assert mock_get_client.call_count == 2
    assert client_obsolete.get.call_count == 1
    assert client_obsolete.get.call_args == call(sentinel.url)
    assert client_refreshed.get.call_count == 1
    assert client_refreshed.get.call_args == call(sentinel.url)


def test_oauth_client_translate_exceptions():
    client = OauthClient(client_id="", client_secret="", token={})

    with pytest.raises(ServiceAPIError):
        with client.translate_exceptions():
            raise EOFError()


@patch("synctogit.service.retries.sleep")
@patch.object(OauthClient, "_get_client")
def test_oauth_client_ratelimit_retries_norecover(mock_get_client, mock_sleep):
    client = MagicMock()

    response = requests.Response()
    response.status_code = 429
    client.get.side_effect = requests.HTTPError(response=response)

    mock_get_client.return_value = client

    oauth_client = OauthClient(client_id="", client_secret="", token={})

    with pytest.raises(ServiceAPIError):
        oauth_client.get(sentinel.url)
    assert client.get.call_count == 10
    assert mock_sleep.call_count == 9


@patch("synctogit.service.retries.sleep")
@patch.object(OauthClient, "_get_client")
def test_oauth_client_ratelimit_retries_recover(mock_get_client, mock_sleep):
    client = MagicMock()
    success_response = MagicMock()

    response = requests.Response()
    response.status_code = 429
    client.get.side_effect = (
        # fmt: off
        [requests.HTTPError(response=response)] * 5
        + [success_response]
        # fmt: on
    )

    mock_get_client.return_value = client

    oauth_client = OauthClient(client_id="", client_secret="", token={})

    assert success_response is oauth_client.get(sentinel.url)
    assert client.get.call_count == 6
    assert mock_sleep.call_count == 5


@patch("requests_toolbelt.multipart.decoder.MultipartDecoder")
def test_onenote_api_page_html(mock_decoder):
    client = MagicMock()
    api = OneNoteAPI(client=client)

    mock_decoder.from_response.side_effect = [sentinel.multipart]
    assert sentinel.multipart is api.get_page_html("PAPAPAGE")
    assert client.get.call_count == 1
    assert client.get.call_args == call(
        "https://graph.microsoft.com/v1.0/me/onenote/pages/"
        "PAPAPAGE/content?preAuthenticated=true&includeinkML=true"
    )


def test_onenote_api_page_info_with_section():
    client = MagicMock()
    api = OneNoteAPI(client=client)

    client.get().json.side_effect = [
        {"value": [sentinel.page]},
    ]
    client.get.reset_mock()
    assert sentinel.page is api.get_page_info("PAPAPAGE", "SESESECTION")
    assert client.get.call_count == 1
    assert client.get.call_args == call(
        "https://graph.microsoft.com/v1.0/me/onenote/sections/SESESECTION/pages",
        params={
            "$select": "id,title,createdDateTime,lastModifiedDateTime",
            "filter": "id eq 'PAPAPAGE'",
            "pagelevel": "true",
        },
    )


def test_onenote_api_page_info_without_section():
    client = MagicMock()
    api = OneNoteAPI(client=client)

    client.get().json.side_effect = [
        {"parentSection": {"id": "SESESECTION"}},
        {"value": [sentinel.page]},
    ]
    client.get.reset_mock()
    assert sentinel.page is api.get_page_info("PAPAPAGE", None)
    assert client.get.call_count == 2
    assert client.get.call_args_list == [
        call(
            "https://graph.microsoft.com/v1.0/me/onenote/pages/PAPAPAGE",
            params={
                "$select": "id,title,createdDateTime,lastModifiedDateTime",
                "$expand": "parentSection($select=id)",
            },
        ),
        call(
            "https://graph.microsoft.com/v1.0/me/onenote/sections/SESESECTION/pages",
            params={
                "$select": "id,title,createdDateTime,lastModifiedDateTime",
                "filter": "id eq 'PAPAPAGE'",
                "pagelevel": "true",
            },
        ),
    ]


def test_onenote_api_pages_of_section():
    client = MagicMock()
    api = OneNoteAPI(client=client)

    client.get().json.side_effect = [
        {"value": [sentinel.page1, sentinel.page2]},
    ]
    client.get.reset_mock()
    assert [sentinel.page1, sentinel.page2] == list(
        api.get_pages_of_section("SESESECTION")
    )


def test_onenote_api_notebooks():
    client = MagicMock()
    api = OneNoteAPI(client=client)

    client.get().json.side_effect = [
        {"value": [sentinel.nb1, sentinel.nb2]},
    ]
    client.get.reset_mock()
    assert [sentinel.nb1, sentinel.nb2] == list(api.get_notebooks())
