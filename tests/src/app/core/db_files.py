"""Database files written for the core tests, laid out like the bundled database."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Sequence

__all__: tuple[str, ...] = ("DbFiles",)


class DbFiles:
    """Writes database files with the tables the app reads; the real file is written by the scheduled update."""

    _SCHEMA: str = """
        CREATE TABLE cpus (
            name TEXT PRIMARY KEY,
            vendor TEXT NOT NULL CHECK (vendor IN ('amd', 'intel'))
        );
        CREATE TABLE gpus (
            name TEXT PRIMARY KEY,
            device_id TEXT NOT NULL
        );
        CREATE TABLE gpu_ranks (
            device_id TEXT PRIMARY KEY,
            chip TEXT NOT NULL,
            generation INTEGER NOT NULL,
            tier REAL NOT NULL
        );
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
    """

    @classmethod
    def create(cls, *, path: Path, statements: Sequence[tuple[str, tuple[object, ...]]] = ()) -> Path:
        """
        Write a database with every table and the given rows, creating its folder.

        :param path: database file to create
        :param statements: SQL statements with their parameters
        :return: the database file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database=path)) as db:
            db.executescript(cls._SCHEMA)
            for sql, parameters in statements:
                db.execute(sql, parameters)
            db.commit()
        return path
