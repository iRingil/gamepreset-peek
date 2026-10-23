"""Tests of the database file and its download."""

from contextlib import closing
from pathlib import Path
from typing import Iterator

import pytest
import responses

from app.core.app_db import AppDb
from app.core.database import AppData, AppDatabase
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()

_URL: str = "https://downloads.example.test/app.db"


class TestAppDatabase:
    """Tests of AppDatabase: loading and downloading."""

    @pytest.fixture(name="http")
    def _http(self) -> Iterator[HttpClient]:
        """
        Create the HTTP client the download goes through.

        :return: HTTP client
        """
        with HttpClient() as http:
            yield http

    @pytest.fixture(name="path")
    def _path(self, tmp_path: Path) -> Path:
        """
        Write the database file naming one game.

        :param tmp_path: temporary directory
        :return: database file
        """
        return self._database(path=tmp_path / "data" / "app.db", name="MORDHAU")

    @pytest.fixture(name="database")
    def _database_fixture(self, http: HttpClient, path: Path) -> AppDatabase:
        """
        Create the database over the file.

        :param http: HTTP client
        :param path: database file
        :return: database under test
        """
        return AppDatabase(http=http, path=path, url=_URL)

    @staticmethod
    def _database(*, path: Path, name: str) -> Path:
        """
        Write a database whose games table names "mordhau".

        :param path: database file
        :param name: display name of the game
        :return: the file
        """
        with closing(AppDb.write(path=path)) as db:
            db.execute("INSERT INTO games (game_id, name) VALUES (?, ?)", ("mordhau", name))
            db.commit()
        return path

    def test_loaded(self, database: AppDatabase, path: Path) -> None:
        """
        Reads the lists from the file.

        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange & Act
        data: AppData = database.load()
        # Assert
        assert (database.path, data.names.name(game_id="mordhau")) == (path, "MORDHAU")

    def test_same_download_dropped(self, mock: responses.RequestsMock, database: AppDatabase, path: Path) -> None:
        """
        Leaves the file alone when the download equals it.

        :param mock: HTTP mock
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        before: bytes = path.read_bytes()
        mock.add(method=responses.GET, url=_URL, body=before)
        # Act
        changed: bool = database.download()
        # Assert
        assert (changed, path.read_bytes() == before, list(path.parent.iterdir())) == (False, True, [path])

    def test_new_download_in_place(
        self, mock: responses.RequestsMock, tmp_path: Path, database: AppDatabase, path: Path
    ) -> None:
        """
        Puts a different database in place of the file, leaving nothing else behind.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        newer: Path = self._database(path=tmp_path / "newer.db", name="Mordhau II")
        mock.add(method=responses.GET, url=_URL, body=newer.read_bytes())
        # Act
        changed: bool = database.download()
        # Assert
        assert (changed, path.read_bytes() == newer.read_bytes(), list(path.parent.iterdir())) == (True, True, [path])
        assert database.load().names.name(game_id="mordhau") == "Mordhau II"

    def test_bad_download_dropped(self, mock: responses.RequestsMock, database: AppDatabase, path: Path) -> None:
        """
        Drops a download that is not a usable database, keeping the file and leaving nothing behind.

        :param mock: HTTP mock
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, body=b"<html>not found</html>")
        # Act & Assert
        with pytest.raises(ValueError, match="not a usable database"):
            database.download()
        assert list(path.parent.iterdir()) == [path]
        assert database.load().names.name(game_id="mordhau") == "MORDHAU"

    def test_failed_download(self, mock: responses.RequestsMock, database: AppDatabase, path: Path) -> None:
        """
        Lets an HTTP failure through, writing nothing.

        :param mock: HTTP mock
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_URL, status=404)
        # Act & Assert
        with pytest.raises(HttpClientError):
            database.download()
        assert list(path.parent.iterdir()) == [path]
