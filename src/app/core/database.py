"""The database file the app reads and its update from the project repository."""

import hashlib
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger

from app.config import APP_DB, DB_MANIFEST_URL, DB_UPDATE_URL
from app.core.game_catalog import GameCatalog
from app.core.hardware import CpuList, GpuList, GpuRanks
from app.infra.http_client import HttpClient

__all__: tuple[str, ...] = ("AppData", "AppDatabase", "DatabaseManifest")


@dataclass(frozen=True, slots=True)
class DatabaseManifest:
    """The published description of the latest database: its sha256 and when its source data were last checked."""

    sha256: str
    checked: datetime


@dataclass(frozen=True, slots=True)
class AppData:
    """What the app reads from its database: the game catalog, the CPU and GPU lists and the GPU ranks."""

    catalog: GameCatalog
    cpu_list: CpuList
    gpu_list: GpuList
    ranks: GpuRanks


class AppDatabase:
    """The database file and its replacement by the latest one from the repository.

    The manifest tells whether the file in use is the latest: it is downloaded only when the hashes differ. A download
    that doesn't match the manifest is dropped, and so is one that is not a usable database or lacks games, CPUs or
    GPUs; a new one takes the file's place."""

    _SHA256: ClassVar[re.Pattern[str]] = re.compile(pattern=r"[0-9a-f]{64}")

    def __init__(
        self, *, http: HttpClient, path: Path = APP_DB, url: str = DB_UPDATE_URL, manifest_url: str = DB_MANIFEST_URL
    ) -> None:
        """
        Use the given file and download URLs.

        :param http: HTTP client the downloads go through
        :param path: database file
        :param url: URL of the latest database
        :param manifest_url: URL of the latest database's manifest
        """
        self._http: HttpClient = http
        self._path: Path = path
        self._url: str = url
        self._manifest_url: str = manifest_url

    @property
    def path(self) -> Path:
        """
        Get the database file.

        :return: the file
        """
        return self._path

    def writable(self) -> bool:
        """
        Tell whether an update can replace the file: its folder takes a new file and the file itself can be written.

        :return: True when it can
        """
        try:
            handle: int
            name: str
            handle, name = tempfile.mkstemp(dir=self._path.parent)
            os.close(handle)
            os.unlink(path=name)
            with self._path.open(mode="r+b"):
                pass
        except OSError as error:
            logger.warning("Database {} can't be updated: {!r}", self._path, error)
            return False
        return True

    def load(self) -> AppData:
        """
        Read the lists from the database file.

        :return: game catalog, CPU and GPU lists and GPU ranks
        """
        return self._load(path=self._path)

    def manifest(self) -> DatabaseManifest:
        """
        Download the manifest of the latest database.

        :return: its sha256 and when its source data were last checked
        """
        document: Any = self._http.get_json(url=self._manifest_url)
        if not isinstance(document, dict):
            raise TypeError(f"expected an object, got {document!r}")
        sha256: Any = document.get("sha256")
        checked: Any = document.get("checked")
        if not isinstance(sha256, str) or not self._SHA256.fullmatch(string=sha256):
            raise ValueError(f"expected a sha256, got {sha256!r}")
        if not isinstance(checked, str):
            raise TypeError(f"expected a string, got {checked!r}")
        moment: datetime = datetime.fromisoformat(checked)
        if moment.tzinfo is None:
            raise ValueError(f"expected a UTC offset, got {checked!r}")
        manifest: DatabaseManifest = DatabaseManifest(sha256=sha256, checked=moment)
        logger.debug("Database manifest: {}", manifest)
        return manifest

    def download(self, *, manifest: DatabaseManifest) -> bool:
        """
        Download the latest database and put it in place of the file, unless the file already is that database.

        :param manifest: manifest of the latest database
        :return: True when a new database is in place, False when the file already matches the manifest
        """
        if hashlib.sha256(self._path.read_bytes()).hexdigest() == manifest.sha256:
            logger.info("Database {} is up to date", self._path)
            return False
        body: bytes = self._http.get_bytes(url=self._url)
        # The file and its manifest are committed one after the other and cached apart, so they may briefly disagree.
        if hashlib.sha256(body).hexdigest() != manifest.sha256:
            raise ValueError("downloaded database doesn't match its manifest")
        # Written beside the file and checked before it takes the file's place, so a bad download changes nothing.
        temp: Path = self._path.with_suffix(".download")
        temp.write_bytes(data=body)
        try:
            self._check(data=self._load(path=temp))
            os.replace(src=temp, dst=self._path)
        except (sqlite3.Error, ValueError, TypeError) as error:
            raise ValueError(f"downloaded file is not a usable database: {error!r}") from error
        finally:
            temp.unlink(missing_ok=True)
        logger.info("Database updated: {} bytes from {} written to {}", len(body), self._url, self._path)
        return True

    @staticmethod
    def _check(*, data: AppData) -> None:
        """
        Make sure a database has games, CPUs and GPUs: an empty list would leave the user nothing to choose from.

        :param data: lists read from the database
        :return: None
        """
        empty: list[str] = [
            name
            for name, items in (
                ("games", data.catalog.games),
                ("CPUs", data.cpu_list.amd + data.cpu_list.intel),
                ("GPUs", data.gpu_list.gpus),
            )
            if not items
        ]
        if empty:
            raise ValueError(f"no {', '.join(empty)}")

    @staticmethod
    def _load(*, path: Path) -> AppData:
        """
        Read the lists from a database file.

        :param path: database file
        :return: game catalog, CPU and GPU lists and GPU ranks
        """
        return AppData(
            catalog=GameCatalog.load(path=path),
            cpu_list=CpuList.load(path=path),
            gpu_list=GpuList.load(path=path),
            ranks=GpuRanks.load(path=path),
        )
