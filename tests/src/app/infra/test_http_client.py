"""Tests of the HTTP client."""

import json
import time
from typing import Any, Iterator
from unittest.mock import Mock

import pytest
import requests
import responses
from responses import matchers

from app.config import HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()

_URL: str = "https://example.test/v3/ops/game/"


class TestHttpClient:
    """Tests of HttpClient answers, retries, request settings and HttpClientError."""

    @pytest.fixture(name="mock")
    def _mock(self) -> Iterator[responses.RequestsMock]:
        """
        Intercept requests sent through requests.

        :return: mock to register answers on and inspect calls of
        """
        with responses.RequestsMock() as mock:
            yield mock

    @pytest.fixture(name="delays", autouse=True)
    def _delays(self, monkeypatch: pytest.MonkeyPatch) -> list[float]:
        """
        Replace the backoff sleep with recording its delays.

        :param monkeypatch: pytest monkeypatch
        :return: delays slept so far, in order
        """
        delays: list[float] = []
        monkeypatch.setattr(target=time, name="sleep", value=delays.append)
        return delays

    @pytest.fixture(name="client")
    def _client(self) -> Iterator[HttpClient]:
        """
        Create a client with the default settings.

        :return: client under test
        """
        with HttpClient() as client:
            yield client

    def test_json_any_content_type(self, mock: responses.RequestsMock, client: HttpClient) -> None:
        """
        Parses the body as JSON whatever its Content-Type, as NVIDIA serves presets as binary/octet-stream.

        :param mock: requests mock
        :param client: client under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=b'{"regular": [1, 2]}', content_type="binary/octet-stream")
        # Act
        result: Any = client.get_json(url=_URL)
        # Assert
        assert result == {"regular": [1, 2]}

    def test_json_invalid(self, mock: responses.RequestsMock, client: HttpClient) -> None:
        """
        Raises a JSON decoding error for a body that is not JSON.

        :param mock: requests mock
        :param client: client under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=b"<html>")
        # Act & Assert
        with pytest.raises(expected_exception=json.JSONDecodeError):
            client.get_json(url=_URL)

    def test_bytes(self, mock: responses.RequestsMock, client: HttpClient) -> None:
        """
        Returns the raw body.

        :param mock: requests mock
        :param client: client under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=b"\x1bLua\x51")
        # Act
        result: bytes = client.get_bytes(url=_URL)
        # Assert
        assert result == b"\x1bLua\x51"

    def test_request_settings(self, mock: responses.RequestsMock, client: HttpClient) -> None:
        """
        Sends the query parameters and the connect and read timeouts.

        :param mock: requests mock
        :param client: client under test
        :return: None
        """
        # Arrange
        params: dict[str, str] = {"gpu.name": "NVIDIA GeForce RTX 4090", "gpu.deviceID": "2684"}
        mock.add(
            method=responses.GET,
            url=_URL,
            body=b"{}",
            match=[
                matchers.query_param_matcher(params=params),
                matchers.request_kwargs_matcher(kwargs={"timeout": (HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT)}),
            ],
        )
        # Act
        result: Any = client.get_json(url=_URL, params=params)
        # Assert
        assert result == {}

    def test_user_agent(self, mock: responses.RequestsMock, client: HttpClient) -> None:
        """
        Sends the same Windows browser User-Agent with every request of a client.

        :param mock: requests mock
        :param client: client under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=b"ok")
        # Act
        client.get_bytes(url=_URL)
        client.get_bytes(url=_URL)
        # Assert
        user_agents: set[str | bytes] = {call.request.headers["User-Agent"] for call in mock.calls}
        assert len(user_agents) == 1
        assert "Windows NT" in str(user_agents.pop())

    def test_client_error_not_retried(
        self, mock: responses.RequestsMock, client: HttpClient, delays: list[float]
    ) -> None:
        """
        Raises HttpClientError with the status, the full URL and the body for a 4xx answer, without retrying.

        :param mock: requests mock
        :param client: client under test
        :param delays: recorded backoff delays
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, status=404, body="not found")
        # Act
        with pytest.raises(expected_exception=HttpClientError) as caught:
            client.get_bytes(url=_URL, params={"cpu.name": "xyz"})
        # Assert
        assert caught.value.status == 404
        assert caught.value.url == f"{_URL}?cpu.name=xyz"
        assert caught.value.body == "not found"
        assert str(caught.value) == f"HTTP 404 for {_URL}?cpu.name=xyz"
        assert len(mock.calls) == 1
        assert not delays

    def test_server_error_retried(self, mock: responses.RequestsMock, client: HttpClient, delays: list[float]) -> None:
        """
        Retries 5xx answers with exponential backoff and returns the first 2xx answer.

        :param mock: requests mock
        :param client: client under test
        :param delays: recorded backoff delays
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, status=502)
        mock.add(method=responses.GET, url=_URL, status=503)
        mock.add(method=responses.GET, url=_URL, body=b"ok")
        # Act
        result: bytes = client.get_bytes(url=_URL)
        # Assert
        assert result == b"ok"
        assert delays == [0.5, 1.0]

    def test_server_error_retries_exhausted(
        self, mock: responses.RequestsMock, client: HttpClient, delays: list[float]
    ) -> None:
        """
        Raises HttpClientError for the last 5xx answer when the retries run out.

        :param mock: requests mock
        :param client: client under test
        :param delays: recorded backoff delays
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, status=503, body="busy")
        # Act
        with pytest.raises(expected_exception=HttpClientError) as caught:
            client.get_bytes(url=_URL)
        # Assert
        assert caught.value.status == 503
        assert len(mock.calls) == 3
        assert delays == [0.5, 1.0]

    @pytest.mark.parametrize(
        argnames="error",
        argvalues=[requests.ConnectionError("refused"), requests.ReadTimeout("slow")],
        ids=["connection", "timeout"],
    )
    def test_transport_error_retried(
        self, mock: responses.RequestsMock, client: HttpClient, delays: list[float], error: requests.RequestException
    ) -> None:
        """
        Retries a connection error or a timeout and returns the next answer.

        :param mock: requests mock
        :param client: client under test
        :param delays: recorded backoff delays
        :param error: transport error of the first attempt
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=error)
        mock.add(method=responses.GET, url=_URL, body=b"ok")
        # Act
        result: bytes = client.get_bytes(url=_URL)
        # Assert
        assert result == b"ok"
        assert delays == [0.5]

    def test_transport_error_retries_exhausted(
        self, mock: responses.RequestsMock, client: HttpClient, delays: list[float]
    ) -> None:
        """
        Re-raises the last transport error when the retries run out.

        :param mock: requests mock
        :param client: client under test
        :param delays: recorded backoff delays
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=requests.ConnectTimeout("no route"))
        # Act
        with pytest.raises(expected_exception=requests.ConnectTimeout):
            client.get_bytes(url=_URL)
        # Assert
        assert len(mock.calls) == 3
        assert delays == [0.5, 1.0]

    def test_no_retries(self, mock: responses.RequestsMock, delays: list[float]) -> None:
        """
        Makes a single attempt when retries are disabled.

        :param mock: requests mock
        :param delays: recorded backoff delays
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, status=500)
        # Act
        with HttpClient(max_retries=0) as client, pytest.raises(expected_exception=HttpClientError):
            client.get_bytes(url=_URL)
        # Assert
        assert len(mock.calls) == 1
        assert not delays

    def test_context_manager_closes_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Closes the session on leaving the context manager.

        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        close: Mock = Mock()
        monkeypatch.setattr(target=requests.Session, name="close", value=close)
        # Act
        with HttpClient():
            pass
        # Assert
        close.assert_called_once_with()
