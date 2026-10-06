"""Synchronous HTTP client: GET with retries on connection errors, timeouts and 5xx answers."""

import json
import time
from types import TracebackType
from typing import Any, Mapping, Self

import requests
from fake_useragent import UserAgent
from loguru import logger

from app.config import (
    HTTP_CONNECT_TIMEOUT,
    HTTP_MAX_RETRIES,
    HTTP_READ_TIMEOUT,
    HTTP_RETRY_BACKOFF,
    USER_AGENT_OS,
)

__all__: tuple[str, ...] = ("HttpClient", "HttpClientError")


class HttpClientError(Exception):
    """Raised when a server answers with a non-2xx status."""

    def __init__(self, *, status: int, url: str, body: str) -> None:
        """
        Keep the details of the failed answer.

        :param status: HTTP status code of the answer
        :param url: final URL of the request, query string included
        :param body: body of the answer as text
        """
        super().__init__(f"HTTP {status} for {url}")
        self.status: int = status
        self.url: str = url
        self.body: str = body


class HttpClient:
    """Sends GET requests through one session with a fake Windows User-Agent and retries transient failures.

    Connection errors, timeouts and 5xx answers are retried with exponential backoff. When the retries run out, the
    last requests exception or HttpClientError propagates; other non-2xx answers raise HttpClientError at once."""

    def __init__(
        self,
        *,
        connect_timeout: float = HTTP_CONNECT_TIMEOUT,
        read_timeout: float = HTTP_READ_TIMEOUT,
        max_retries: int = HTTP_MAX_RETRIES,
    ) -> None:
        """
        Open a session with a fake Windows browser User-Agent kept until the client is closed.

        :param connect_timeout: seconds to wait for a connection to the server
        :param read_timeout: seconds to wait for the next bytes of the answer
        :param max_retries: retries after the first attempt
        """
        self._timeout: tuple[float, float] = (connect_timeout, read_timeout)
        self._max_retries: int = max_retries
        self._session: requests.Session = requests.Session()
        user_agent: str = UserAgent(os=USER_AGENT_OS).random
        self._session.headers["User-Agent"] = user_agent
        logger.debug("User-Agent: {}", user_agent)

    def __enter__(self) -> Self:
        """
        Use the client as a context manager that closes the session on exit.

        :return: the client itself
        """
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """
        Close the session.

        :param exc_type: type of the exception that ended the block, if any
        :param exc_value: exception that ended the block, if any
        :param traceback: traceback of that exception, if any
        :return: None
        """
        self.close()

    def close(self) -> None:
        """
        Close the session and its pooled connections.

        :return: None
        """
        self._session.close()

    def get_json(self, *, url: str, params: Mapping[str, str] | None = None) -> Any:
        """
        GET a URL and parse the body as JSON, whatever its Content-Type.

        :param url: URL to request
        :param params: query string parameters
        :return: parsed JSON
        """
        return json.loads(s=self.get_bytes(url=url, params=params))

    def get_bytes(self, *, url: str, params: Mapping[str, str] | None = None) -> bytes:
        """
        GET a URL and return the raw body.

        :param url: URL to request
        :param params: query string parameters
        :return: body of the answer
        """
        return self._get(url=url, params=params).content

    def _get(self, *, url: str, params: Mapping[str, str] | None) -> requests.Response:
        """
        GET a URL, retrying connection errors, timeouts and 5xx answers.

        :param url: URL to request
        :param params: query string parameters
        :return: the 2xx answer
        """
        attempt: int = 0
        while True:
            reason: str
            try:
                logger.debug("GET {}", url)
                response: requests.Response = self._session.get(url=url, params=params, timeout=self._timeout)
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt >= self._max_retries:
                    raise
                reason = type(error).__name__
            else:
                if response.status_code < 500 or attempt >= self._max_retries:
                    self._raise_for_status(response=response)
                    return response
                reason = f"HTTP {response.status_code}"
            delay: float = HTTP_RETRY_BACKOFF * 2**attempt
            attempt += 1
            logger.warning("GET {} failed ({}), retry {} of {} in {} s", url, reason, attempt, self._max_retries, delay)
            time.sleep(delay)

    @staticmethod
    def _raise_for_status(*, response: requests.Response) -> None:
        """
        Raise HttpClientError for a non-2xx answer.

        :param response: answer to check
        :return: None
        """
        if not 200 <= response.status_code < 300:
            raise HttpClientError(status=response.status_code, url=response.url, body=response.text)
