"""Tests of the database file and its download."""

import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Sequence

import pytest
import responses

from app.core.database import AppData, AppDatabase, DatabaseManifest
from app.infra.http_client import HttpClient, HttpClientError
from tests.src.app.core.db_files import DbFiles

__all__: tuple = ()

_URL: str = "https://downloads.example.test/app.db"
_MANIFEST_URL: str = "https://downloads.example.test/app.db.json"


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
        return AppDatabase(http=http, path=path, url=_URL, manifest_url=_MANIFEST_URL)

    @staticmethod
    def _manifest(*, content: bytes) -> DatabaseManifest:
        """
        Make the manifest of a database file checked on Monday 2026-10-26.

        :param content: the file's content
        :return: its manifest
        """
        return DatabaseManifest(
            sha256=hashlib.sha256(content).hexdigest(),
            checked=datetime(year=2026, month=10, day=26, hour=3, tzinfo=UTC),
        )

    @staticmethod
    def _database(*, path: Path, name: str, extra: Sequence[tuple[str, tuple[object, ...]]] = ()) -> Path:
        """
        Write a database naming "mordhau", with one CPU and one GPU.

        :param path: database file
        :param name: display name of the game
        :param extra: further SQL statements with their parameters
        :return: the file
        """
        return DbFiles.create(
            path=path,
            statements=[
                ("INSERT INTO games (game_id, name) VALUES (?, ?)", ("mordhau", name)),
                ("INSERT INTO cpus (name, vendor) VALUES (?, ?)", ("AMD Ryzen 7 7800X3D 8-Core Processor", "amd")),
                ("INSERT INTO gpus (name, device_id) VALUES (?, ?)", ("NVIDIA GeForce RTX 4090", "2684")),
                *extra,
            ],
        )

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
        assert (database.path, data.catalog.games[0].name) == (path, "MORDHAU")

    def test_writable(self, database: AppDatabase, path: Path) -> None:
        """
        Tells that an update can replace the file in a folder the user can write to, leaving nothing behind.

        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange & Act
        writable: bool = database.writable()
        # Assert
        assert (writable, list(path.parent.iterdir())) == (True, [path])

    def test_read_only_file(self, database: AppDatabase, path: Path) -> None:
        """
        Tells that an update can't replace a read-only file.

        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        path.chmod(mode=stat.S_IREAD)
        # Act
        writable: bool = database.writable()
        # Assert
        path.chmod(mode=stat.S_IREAD | stat.S_IWRITE)
        assert not writable

    def test_missing_folder(self, http: HttpClient, tmp_path: Path) -> None:
        """
        Tells that an update can't be put in a folder that doesn't exist.

        :param http: HTTP client
        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        database: AppDatabase = AppDatabase(http=http, path=tmp_path / "gone" / "app.db", url=_URL)
        # Act
        writable: bool = database.writable()
        # Assert
        assert not writable

    def test_manifest(self, mock: responses.RequestsMock, database: AppDatabase) -> None:
        """
        Reads the hash and the check time of the latest database.

        :param mock: HTTP mock
        :param database: database under test
        :return: None
        """
        # Arrange
        mock.add(
            method=responses.GET,
            url=_MANIFEST_URL,
            body='{"sha256": "' + "ab" * 32 + '", "checked": "2026-10-26T08:40:45+00:00"}',
        )
        # Act
        manifest: DatabaseManifest = database.manifest()
        # Assert
        assert manifest == DatabaseManifest(
            sha256="ab" * 32, checked=datetime(year=2026, month=10, day=26, hour=8, minute=40, second=45, tzinfo=UTC)
        )

    @pytest.mark.parametrize(
        argnames=("body", "error"),
        argvalues=[
            ("<html>not found</html>", ValueError),
            ("[]", TypeError),
            ('{"checked": "2026-10-26T08:40:45+00:00"}', ValueError),
            ('{"sha256": "' + "AB" * 32 + '", "checked": "2026-10-26T08:40:45+00:00"}', ValueError),
            ('{"sha256": "' + "ab" * 32 + '"}', TypeError),
            ('{"sha256": "' + "ab" * 32 + '", "checked": "yesterday"}', ValueError),
            ('{"sha256": "' + "ab" * 32 + '", "checked": "2026-10-26T08:40:45"}', ValueError),
        ],
        ids=["not json", "not an object", "no hash", "hash not lowercase hex", "no time", "not a time", "no offset"],
    )
    def test_broken_manifest(
        self, mock: responses.RequestsMock, database: AppDatabase, body: str, error: type[Exception]
    ) -> None:
        """
        Fails on a manifest that doesn't give a sha256 and a check time with its UTC offset.

        :param mock: HTTP mock
        :param database: database under test
        :param body: content of the manifest
        :param error: expected error
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_MANIFEST_URL, body=body)
        # Act & Assert
        with pytest.raises(error):
            database.manifest()

    def test_up_to_date(self, database: AppDatabase, path: Path) -> None:
        """
        Downloads nothing and leaves the file alone when it matches the manifest.

        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        before: bytes = path.read_bytes()
        manifest: DatabaseManifest = self._manifest(content=before)
        # Act
        changed: bool = database.download(manifest=manifest)
        # Assert
        assert (changed, path.read_bytes() == before, list(path.parent.iterdir())) == (False, True, [path])

    def test_download_not_matching_manifest(
        self, mock: responses.RequestsMock, tmp_path: Path, database: AppDatabase, path: Path
    ) -> None:
        """
        Drops a download whose hash differs from the manifest, keeping the file and leaving nothing behind.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        newer: Path = self._database(path=tmp_path / "newer.db", name="Mordhau II")
        mock.add(method=responses.GET, url=_URL, body=newer.read_bytes())
        manifest: DatabaseManifest = self._manifest(content=b"another database")
        # Act & Assert
        with pytest.raises(ValueError, match="doesn't match its manifest"):
            database.download(manifest=manifest)
        assert list(path.parent.iterdir()) == [path]
        assert database.load().catalog.games[0].name == "MORDHAU"

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
        manifest: DatabaseManifest = self._manifest(content=newer.read_bytes())
        # Act
        changed: bool = database.download(manifest=manifest)
        # Assert
        assert (changed, path.read_bytes() == newer.read_bytes(), list(path.parent.iterdir())) == (True, True, [path])
        assert database.load().catalog.games[0].name == "Mordhau II"

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
        manifest: DatabaseManifest = self._manifest(content=b"<html>not found</html>")
        # Act & Assert
        with pytest.raises(ValueError, match="not a usable database"):
            database.download(manifest=manifest)
        assert list(path.parent.iterdir()) == [path]
        assert database.load().catalog.games[0].name == "MORDHAU"

    @pytest.mark.parametrize(
        argnames=("table", "missing"),
        argvalues=[("games", "games"), ("cpus", "CPUs"), ("gpus", "GPUs")],
        ids=["games", "cpus", "gpus"],
    )
    def test_empty_download_dropped(  # pylint: disable=too-many-arguments
        self,
        mock: responses.RequestsMock,
        tmp_path: Path,
        database: AppDatabase,
        path: Path,
        table: str,
        missing: str,
    ) -> None:
        """
        Drops a database with an empty list, keeping the file and leaving nothing behind.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param database: database under test
        :param path: database file
        :param table: the table left empty
        :param missing: how the error names the empty list
        :return: None
        """
        # Arrange
        empty: Path = self._database(
            path=tmp_path / "empty.db", name="Mordhau II", extra=[(f"DELETE FROM {table}", ())]
        )
        mock.add(method=responses.GET, url=_URL, body=empty.read_bytes())
        manifest: DatabaseManifest = self._manifest(content=empty.read_bytes())
        # Act & Assert
        with pytest.raises(ValueError, match=f"no {missing}"):
            database.download(manifest=manifest)
        assert list(path.parent.iterdir()) == [path]
        assert database.load().catalog.games[0].name == "MORDHAU"

    def test_unknown_value_dropped(
        self, mock: responses.RequestsMock, tmp_path: Path, database: AppDatabase, path: Path
    ) -> None:
        """
        Drops a database holding a value the app doesn't know, keeping the file and leaving nothing behind.

        :param mock: HTTP mock
        :param tmp_path: temporary directory
        :param database: database under test
        :param path: database file
        :return: None
        """
        # Arrange
        unknown: Path = self._database(
            path=tmp_path / "unknown.db",
            name="Mordhau II",
            extra=[
                ("INSERT INTO game_sources (game_id, position) VALUES (?, ?)", ("mordhau", 0)),
                (
                    "INSERT INTO game_source_files (game_id, position, path, role) VALUES (?, ?, ?, ?)",
                    ("mordhau", 0, "Mordhau.exe", "bogus"),
                ),
            ],
        )
        mock.add(method=responses.GET, url=_URL, body=unknown.read_bytes())
        manifest: DatabaseManifest = self._manifest(content=unknown.read_bytes())
        # Act & Assert
        with pytest.raises(ValueError, match="not a usable database"):
            database.download(manifest=manifest)
        assert list(path.parent.iterdir()) == [path]
        assert database.load().catalog.games[0].name == "MORDHAU"

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
        manifest: DatabaseManifest = self._manifest(content=b"another database")
        # Act & Assert
        with pytest.raises(HttpClientError):
            database.download(manifest=manifest)
        assert list(path.parent.iterdir()) == [path]
