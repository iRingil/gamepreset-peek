"""The database file the app reads and its update from the project repository."""

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.config import APP_DB, DB_UPDATE_URL
from app.core.game_catalog import GameCatalog
from app.core.hardware import CpuList, GpuList, GpuRanks
from app.infra.http_client import HttpClient

__all__: tuple[str, ...] = ("AppData", "AppDatabase")


@dataclass(frozen=True, slots=True)
class AppData:
    """What the app reads from its database: the game catalog, the CPU and GPU lists and the GPU ranks."""

    catalog: GameCatalog
    cpu_list: CpuList
    gpu_list: GpuList
    ranks: GpuRanks


class AppDatabase:
    """The database file and its replacement by the latest one from the repository.

    A download equal to the file in use is dropped, and so is one that is not a usable database or lacks games, CPUs
    or GPUs; a new one takes the file's place."""

    def __init__(self, *, http: HttpClient, path: Path = APP_DB, url: str = DB_UPDATE_URL) -> None:
        """
        Use the given file and download URL.

        :param http: HTTP client the download goes through
        :param path: database file
        :param url: URL of the latest database
        """
        self._http: HttpClient = http
        self._path: Path = path
        self._url: str = url

    @property
    def path(self) -> Path:
        """
        Get the database file.

        :return: the file
        """
        return self._path

    def load(self) -> AppData:
        """
        Read the lists from the database file.

        :return: game catalog, CPU and GPU lists and GPU ranks
        """
        return self._load(path=self._path)

    def download(self) -> bool:
        """
        Download the latest database and put it in place of the file when it differs.

        :return: True when a new database is in place, False when the download equals the file
        """
        body: bytes = self._http.get_bytes(url=self._url)
        if hashlib.sha256(body).hexdigest() == hashlib.sha256(self._path.read_bytes()).hexdigest():
            logger.info("Database {} is up to date", self._path)
            return False
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
