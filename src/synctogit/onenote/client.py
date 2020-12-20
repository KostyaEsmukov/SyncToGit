import contextlib
import logging
import threading
from socket import error as socketerror
from typing import Any, Dict, Iterable, Optional

import requests
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session
from requests_toolbelt.multipart import decoder
from urllib3.util import Retry

from synctogit.service import (
    ServiceAPIError,
    ServiceRateLimitError,
    ServiceTokenExpiredError,
    ServiceUnavailableError,
    retry_ratelimited,
    retry_unavailable,
)

from . import oauth
from .compat import hide_spurious_urllib3_multipart_warning
from .exc import EncryptedSectionError

logger = logging.getLogger(__name__)


class OneNoteAPI:
    # Must be threadsafe
    # https://developer.microsoft.com/en-us/graph/docs/api-reference/v1.0/resources/onenote-api-overview  # noqa

    base_api_url = oauth.base_api_url

    def __init__(self, client: "OauthClient") -> None:
        self._client = client

    def get_page_html(self, page_id: str) -> decoder.MultipartDecoder:
        # https://developer.microsoft.com/en-us/onenote/blogs/onenote-ink-beta-apis/

        with hide_spurious_urllib3_multipart_warning():
            r = self._client.get(
                self.base_api_url
                + "/pages/"
                + str(page_id)
                + "/content?preAuthenticated=true&includeinkML=true"
            )

        multipart_data = decoder.MultipartDecoder.from_response(r)
        return multipart_data

    def get_page_info(self, page_id: str, section_id: Optional[str]) -> Dict[str, Any]:
        # The code below is a fucking shitshow.
        page = None
        if not section_id:
            # If we don't have a `section_id` -- we need to retrieve it first.
            #
            # Actually we should have been simply using the method below,
            # which doesn't require a section_id, but it returns obsolete metadata
            # and returns 404 even for existing pages! Apparently they're
            # having hard times with caches invalidation.
            select_fields = [
                "id",
                "title",
                "createdDateTime",
                "lastModifiedDateTime",
            ]
            expand = [
                "parentSection($select=id)",
            ]
            params = {
                "$select": ",".join(select_fields),
                "$expand": ",".join(expand),
            }
            # This method might return obsolete metadata. Or it might be up to date.
            # You never know. There's *a way* to reliably (well, I hope so) retrieve
            # the up-to-date metadata, but we need to get the section_id first.
            r = self._client.get(
                self.base_api_url + "/pages/" + str(page_id), params=params
            )

            page = r.json()
            section_id = page["parentSection"]["id"]

        select_fields = [
            "id",
            "title",
            "createdDateTime",
            "lastModifiedDateTime",
        ]
        params = {
            "$select": ",".join(select_fields),
            "filter": "id eq '%s'" % page_id,
            "pagelevel": "true",
        }
        # This is wrong on so many levels. Let me remind you: we are just
        # trying to retrieve the fucking Page metadata. And yes, your eyes
        # don't lie to you: we are querying the pages of a section for that.
        #
        # Even so, by default it won't reliably give you the fresh metadata
        # as well, unless you specify a `pagelevel=true` parameter,
        # which is not even documented!
        #
        # What the fuck is wrong with this API?!
        r = self._client.get(
            self.base_api_url + "/sections/%s/pages" % section_id, params=params
        )
        pages = r.json()["value"]
        if len(pages) == 1:
            page = pages[0]
        elif page:
            logger.warning(
                "Unable to retrieve page %s metadata: expected 1 page, "
                "received %s. Using a possibly obsolete metadata instead.",
                page_id,
                len(pages),
            )
        else:
            raise ServiceAPIError(
                "Unable to retrieve page %s metadata: expected 1 page, "
                "received %s." % (page_id, len(pages))
            )
        return page

    def get_pages_of_section(self, section_id: str) -> Iterable[Dict[str, Any]]:
        select_fields = [
            "id",
            "title",
            "createdDateTime",
            "lastModifiedDateTime",
            "parentSection",
            "level",
            "order",
        ]
        params = {
            "$select": ",".join(select_fields),
            "pagelevel": "true",
        }

        # The `/pages` method doesn't support the `order` field and
        # the `pagelevel` parameter. Also I had observed some old metadata
        # being returned for some pages. The /sections/%/pages method doesn't
        # have these issues.
        # url = self.base_api_url + '/pages'
        url = self.base_api_url + "/sections/%s/pages" % section_id
        for resp_page in self._get_paginated(url, params=params):
            for page in resp_page["value"]:
                yield page

    def get_notebooks(self) -> Iterable[Dict[str, Any]]:
        select_fields = [
            "id",
            "displayName",
            "createdDateTime",
            "lastModifiedDateTime",
            "isDefault",
        ]
        section_select_fields = [
            "id",
            "displayName",
            "createdDateTime",
            "lastModifiedDateTime",
            "isDefault",
        ]
        # TODO sectionGroups($expand=sections)
        expand = [
            "sections($select=%s)" % ",".join(section_select_fields),
        ]
        params = {
            "$select": ",".join(select_fields),
            "$expand": ",".join(expand),
            "$orderby": "createdDateTime",
        }

        url = self.base_api_url + "/notebooks"
        for resp_page in self._get_paginated(url, params=params):
            for notebook in resp_page["value"]:
                yield notebook

    def _get_paginated(self, url, **kwargs) -> Iterable[Dict[str, Any]]:
        next_url = url
        while next_url:
            if not next_url.startswith(self.base_api_url):
                raise ValueError(
                    "Received an unexpected foreign URL `%s` as a next "
                    "page link" % next_url
                )
            r = self._client.get(next_url, **kwargs)
            kwargs.pop("params", 0)
            d = r.json()
            yield d
            next_url = d.get("@odata.nextLink")


class OauthClient:
    # Must be threadsafe

    def __init__(
        self, *, client_id: str, client_secret: str, token: Dict[str, Any]
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = token
        self._client = self._get_client()
        self.lock = threading.Lock()

    def get_token(self) -> Dict[str, Any]:
        with self.lock:
            return self._token

    @retry_ratelimited
    @retry_unavailable
    def get(self, *args, **kwargs) -> requests.Response:
        for _ in range(2):
            with self.lock:
                initial_token = self._token
                client = self._client
            with self.translate_exceptions():
                try:
                    response = client.get(*args, **kwargs)
                    response.raise_for_status()
                    return response
                except TokenExpiredError:
                    self._refresh_token(initial_token)
        raise ServiceTokenExpiredError("Failed to update auth token")

    @contextlib.contextmanager
    def translate_exceptions(self):  # noqa
        try:
            yield
        except requests.HTTPError as e:
            if e.response is None:
                raise ServiceAPIError(e)
            status = e.response.status_code
            text = e.response.text
            try:
                json_body = e.response.json()
            except Exception:
                json_body = None

            headers = "\n".join(map(str, e.response.headers.items()))
            if status == 429:  # Throttle
                # Code 20166
                # https://developer.microsoft.com/en-us/graph/docs/concepts/onenote_error_codes#codes-from-20001-to-29999  # noqa

                # As for now OneNote API doesn't return retry-after, but other
                # MS Graph APIs do return it, so maybe they'll consider to add
                # it as well?
                # https://developer.microsoft.com/en-us/graph/docs/concepts/throttling
                s = e.response.headers.get("retry-after")
                if not s:
                    s = 5 * 60
                s = min(s, 3600) + 10
                raise ServiceRateLimitError(e, rate_limit_duration_seconds=s)
            elif (
                status == 403
                and json_body
                and str(json_body["error"]["code"]) == "20185"
            ):
                # "error": {
                #   "code": "20185",
                #   "message": "Encrypted sections are not accessible.",
                # }
                raise EncryptedSectionError(json_body["error"]["message"])
            else:
                logger.warning(
                    "Non-200 response from Microsoft Graph:\n"
                    "Status: %s\n"
                    "Headers: %s\n"
                    "Body: %s",
                    status,
                    headers,
                    text,
                )
                if 500 <= status < 600:
                    raise ServiceUnavailableError(e)
                else:
                    raise ServiceAPIError(e)
        except (socketerror, EOFError) as e:
            raise ServiceAPIError(e)

    def _refresh_token(self, initial_token):
        with self.lock:
            if self._token != initial_token:
                # Probably because some another thread already refreshed
                # the token.
                logger.debug("Skipping token refresh")
                return

            self._token = self._client.refresh_token(
                oauth.authority_url + oauth.token_endpoint,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            self._client = self._get_client()

    def _get_client(self):
        session = OAuth2Session(self.client_id, token=self._token)
        retries = Retry(1, respect_retry_after_header=False)
        a = _HTTPAdapter(max_retries=retries, pool_maxsize=100, timeout=60)
        session.mount("http://", a)
        session.mount("https://", a)
        return session


class _HTTPAdapter(requests.adapters.HTTPAdapter):
    # https://github.com/psf/requests/issues/2011#issuecomment-64440818

    def __init__(self, timeout=None, *args, **kwargs):
        self.__timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        kwargs.setdefault("timeout", self.__timeout)
        return super().send(*args, **kwargs)
