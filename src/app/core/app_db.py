"""The bundled database: CPUs and GPUs the user can choose from, chip ranks of NVIDIA devices and game names."""

import sqlite3
from pathlib import Path

__all__: tuple[str, ...] = ("AppDb",)


class AppDb:
    """Connections to the SQLite file; the app only reads it.

    A scheduled update refreshes the file in the repository; it only ever adds CPUs and GPUs, so a source that drops
    one doesn't shrink the lists."""

    @staticmethod
    def read(*, path: Path) -> sqlite3.Connection:
        """
        Open the database read-only; the bundled file may sit in a read-only folder, so it is opened without locks.

        :param path: database file
        :return: connection; the caller closes it
        """
        if not path.is_file():
            raise FileNotFoundError(path)
        return sqlite3.connect(database=path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
