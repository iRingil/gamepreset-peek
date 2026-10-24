"""Tests of the box art cache."""

from pathlib import Path
from typing import Iterator

import pytest
import responses

from app.config import COVER_WIDTH
from app.core.covers import CoverCache
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()

_URL: str = "https://img.example.test/apps/1/GAME_BOX_ART_01_a.jpg"


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
        first: Path = cache.get(url=_URL)
        second: Path = cache.get(url=_URL)
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
        other: str = _URL.replace("_a.jpg", "_b.jpg")
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", body=b"a")
        mock.add(method=responses.GET, url=f"{other};f=jpg;w={COVER_WIDTH}", body=b"b")
        # Act
        pictures: list[Path] = [cache.get(url=_URL), cache.get(url=other)]
        # Assert
        assert [picture.read_bytes() for picture in pictures] == [b"a", b"b"]

    def test_failed_download(self, mock: responses.RequestsMock, tmp_path: Path, cache: CoverCache) -> None:
        """
        Lets a failed download through, writing nothing.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param cache: cache under test
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=f"{_URL};f=jpg;w={COVER_WIDTH}", status=404)
        # Act & Assert
        with pytest.raises(HttpClientError):
            cache.get(url=_URL)
        assert not (tmp_path / "covers").exists()
