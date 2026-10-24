"""The bundled database: CPUs and GPUs the user can choose from, chip ranks of NVIDIA devices and the games."""

import sqlite3
from pathlib import Path

__all__: tuple[str, ...] = ("AppDb",)


class AppDb:
    """Connections to the SQLite file; the app only reads it and replaces it as a whole with a downloaded update.

    The file is written outside this repository; it only ever gains CPUs and GPUs, so the lists never shrink."""

    @staticmethod
    def read(*, path: Path) -> sqlite3.Connection:
        """
        Open the database read-only and without locks, so nothing keeps the file from being replaced once it is closed.

        :param path: database file
        :return: connection; the caller closes it
        """
        if not path.is_file():
            raise FileNotFoundError(path)
        return sqlite3.connect(database=path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
