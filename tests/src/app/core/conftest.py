"""Fixtures shared by the core tests."""

from typing import Iterator

import pytest
import responses

from app.core.ops_api import OpsApi
from app.infra.http_client import HttpClient

__all__: tuple = ()


@pytest.fixture(name="mock")
def _mock() -> Iterator[responses.RequestsMock]:
    """
    Intercept requests sent through requests.

    :return: mock to register answers on
    """
    with responses.RequestsMock() as mock:
        yield mock


@pytest.fixture(name="api")
def _api() -> Iterator[OpsApi]:
    """
    Create the API client over a real HTTP client.

    :return: API client under test
    """
    with HttpClient() as http:
        yield OpsApi(http=http)
