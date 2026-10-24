"""Tests of the box art cache."""

from pathlib import Path
from typing import Any, Iterator

import pytest
import responses

from app.config import COVER_WIDTH, NV_GAME_ART_URL
from app.core.covers import CoverCache
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()

_URL: str = "https://img.example.test/apps/1/GAME_BOX_ART_01_a.jpg"
_CURRENT: str = "https://img.example.test/apps/1/GAME_BOX_ART_01_b.jpg"
_APP_ID: str = "ce2eca28-aa8c-4b4b-a3e2-5ad03a9f8ecd"


class TestCoverCache:
    """Getting pictures through the disk cache."""

    @pytest.fixture(name="cache")
    def _cache(self, tmp_path: Path) -> Iterator[CoverCache]:
        """
        Make a cache in a folder that doesn't exist yet.

        :param tmp_path: temporary directory
        :return: cache under test
        """
        with HttpClient() as http:
            yield CoverCache(http=http, folder=tmp_path / "covers")

    @staticmethod
    def _answer(*, app_id: str, url: str) -> dict[str, Any]:
        """
        Build an answer of the image service with one application.

        :param app_id: application id
        :param url: its box art URL
        :return: parsed answer
        """
        return {"data": {"apps": {"items": [{"id": app_id, "images": {"GAME_BOX_ART": url}}]}}}

    def test_downloaded_once(self, mock: responses.RequestsMock, tmp_path: Path, cache: CoverCache) -> None:
        """
        Downloads a picture resized to the cover width once, then gives the cached file.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", body=b"jpeg")
        # Act
        first: Path = cache.get(url=_URL, app_id=_APP_ID)
        second: Path = cache.get(url=_URL, app_id=_APP_ID)
        # Assert
        assert (first, first.read_bytes(), len(mock.calls)) == (second, b"jpeg", 1)
        assert list((tmp_path / "covers").iterdir()) == [first]

    def test_new_url_new_file(self, mock: responses.RequestsMock, cache: CoverCache) -> None:
        """
        Keeps the picture of another URL in a file of its own.

        :param mock: HTTP mock
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", body=b"a")
        mock.add(method=responses.GET, url=f"{_CURRENT};f=jpg;w={COVER_WIDTH}", body=b"b")
        # Act
        pictures: list[Path] = [cache.get(url=_URL, app_id=None), cache.get(url=_CURRENT, app_id=None)]
        # Assert
        assert [picture.read_bytes() for picture in pictures] == [b"a", b"b"]

    def test_failed_download(self, mock: responses.RequestsMock, tmp_path: Path, cache: CoverCache) -> None:
        """
        Lets a failed download of a game without an application id through, writing nothing.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", status=404)
        # Act & Assert
        with pytest.raises(HttpClientError):
            cache.get(url=_URL, app_id=None)
        assert not (tmp_path / "covers").exists()
        assert len(mock.calls) == 1

    def test_current_url(self, mock: responses.RequestsMock, cache: CoverCache) -> None:
        """
        Looks a failed URL up by the application id and keeps the current picture under the failed URL's name.

        :param mock: HTTP mock
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", status=404)
        mock.add(method=responses.GET, url=NV_GAME_ART_URL, json=self._answer(app_id=_APP_ID, url=_CURRENT))
        mock.add(method=responses.GET, url=f"{_CURRENT};f=jpg;w={COVER_WIDTH}", body=b"current")
        # Act
        first: Path = cache.get(url=_URL, app_id=_APP_ID)
        second: Path = cache.get(url=_URL, app_id=_APP_ID)
        # Assert
        assert (first, first.read_bytes(), len(mock.calls)) == (second, b"current", 3)
        assert _APP_ID in str(mock.calls[1].request.url)

    @pytest.mark.parametrize(
        argnames="answer",
        argvalues=[
            {"data": {"apps": {"items": []}}},
            {"data": {"apps": {"items": [{"id": _APP_ID, "images": {"GAME_BOX_ART": _URL}}]}}},
            {"data": {"apps": {"items": [{"id": "other-app", "images": {"GAME_BOX_ART": _CURRENT}}]}}},
            {"data": {"apps": {"items": [{"id": _APP_ID, "images": {"GAME_BOX_ART": ""}}]}}},
            {"errors": [{"message": "bad query"}]},
        ],
        ids=["unknown application", "same url", "other application", "no box art", "error answer"],
    )
    def test_no_current_url(
        self, mock: responses.RequestsMock, tmp_path: Path, cache: CoverCache, answer: dict[str, Any]
    ) -> None:
        """
        Lets the failed download through when the service gives no other URL for the application.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param cache: cache under test
        :param answer: answer of the image service
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", status=404)
        mock.add(method=responses.GET, url=NV_GAME_ART_URL, json=answer)
        # Act & Assert
        with pytest.raises(HttpClientError):
            cache.get(url=_URL, app_id=_APP_ID)
        assert not (tmp_path / "covers").exists()

    def test_current_url_fails_too(self, mock: responses.RequestsMock, tmp_path: Path, cache: CoverCache) -> None:
        """
        Lets the failure of the current URL through, writing nothing.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", status=404)
        mock.add(method=responses.GET, url=NV_GAME_ART_URL, json=self._answer(app_id=_APP_ID, url=_CURRENT))
        mock.add(method=responses.GET, url=f"{_CURRENT};f=jpg;w={COVER_WIDTH}", status=404)
        # Act & Assert
        with pytest.raises(HttpClientError):
            cache.get(url=_URL, app_id=_APP_ID)
        assert not (tmp_path / "covers").exists()
