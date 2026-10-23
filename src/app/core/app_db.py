"""The bundled database: CPUs and GPUs the user can choose from, chip ranks of NVIDIA devices and game names."""

import sqlite3
from pathlib import Path

__all__: tuple[str, ...] = ("AppDb",)


class AppDb:
    """Schema of the SQLite file and connections to it; the app only reads it.

    tools/update_hardware_db.py fills the hardware tables, and only ever adds rows to them: a CPU or GPU found once
    stays, so a source that drops it doesn't shrink the lists. The game names are a bundled list."""

    SCHEMA: str = """
        CREATE TABLE IF NOT EXISTS cpus (
            name TEXT PRIMARY KEY,
            vendor TEXT NOT NULL CHECK (vendor IN ('amd', 'intel')),
            added TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gpus (
            name TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            added TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gpu_ranks (
            device_id TEXT PRIMARY KEY,
            chip TEXT NOT NULL,
            generation INTEGER NOT NULL,
            tier REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
    """

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

    @classmethod
    def write(cls, *, path: Path) -> sqlite3.Connection:
        """
        Open the database for changes, creating the file and the tables when missing.

        :param path: database file
        :return: connection; the caller commits and closes it
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        connection: sqlite3.Connection = sqlite3.connect(database=path)
        connection.executescript(cls.SCHEMA)
        return connection
