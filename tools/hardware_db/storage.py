"""Changes to the hardware database: rows are added, chip ranks replaced; nothing else is ever removed."""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Iterable, Self

from hardware_db.cpu_sources import Cpu
from hardware_db.gpu_sources import GpuRank

from app.core.app_db import AppDb
from app.core.models import Gpu

__all__: tuple[str, ...] = ("HardwareDbWriter",)


class HardwareDbWriter:
    """Writes the hardware database; used as a context manager, it commits on success and compacts a changed file.

    A file without changes is left byte for byte as it was, so a run that finds nothing new leaves git clean."""

    def __init__(self, *, path: Path) -> None:
        """
        Open the database, creating it when missing.

        :param path: database file
        """
        self._db: sqlite3.Connection = AppDb.write(path=path)
        self._changed: bool = False

    def __enter__(self) -> Self:
        """
        Use the writer as a context manager.

        :return: the writer itself
        """
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """
        Commit and compact the changes when the block succeeded, otherwise drop them, and close the database.

        :param exc_type: exception type
        :param exc_value: exception
        :param traceback: traceback
        :return: None
        """
        try:
            if exc_type is None and self._changed:
                self._db.commit()
                self._db.execute("VACUUM")
            else:
                self._db.rollback()
        finally:
            self._db.close()

    def cpu_names(self) -> set[str]:
        """
        Read the names of the CPUs in the database.

        :return: CPU names
        """
        return {name for (name,) in self._db.execute("SELECT name FROM cpus")}

    def add_cpus(self, *, cpus: Iterable[Cpu], added: str) -> None:
        """
        Add CPUs; one already there keeps its row.

        :param cpus: CPUs to add
        :param added: date of the update, YYYY-MM-DD
        :return: None
        """
        rows: list[tuple[str, str, str]] = [(cpu.name, cpu.vendor, added) for cpu in cpus]
        self._db.executemany("INSERT OR IGNORE INTO cpus (name, vendor, added) VALUES (?, ?, ?)", rows)
        self._changed = self._changed or bool(rows)

    def gpu_names(self) -> set[str]:
        """
        Read the names of the GPUs in the database.

        :return: GPU names
        """
        return {name for (name,) in self._db.execute("SELECT name FROM gpus")}

    def add_gpus(self, *, gpus: Iterable[Gpu], added: str) -> None:
        """
        Add GPUs; one already there keeps its row.

        :param gpus: GPUs to add
        :param added: date of the update, YYYY-MM-DD
        :return: None
        """
        rows: list[tuple[str, str, str]] = [(gpu.name, gpu.device_id, added) for gpu in gpus]
        self._db.executemany("INSERT OR IGNORE INTO gpus (name, device_id, added) VALUES (?, ?, ?)", rows)
        self._changed = self._changed or bool(rows)

    def replace_ranks(self, *, ranks: Iterable[GpuRank]) -> bool:
        """
        Replace the chip ranks unless they are the same as the stored ones.

        :param ranks: ranks of every ranked device
        :return: True when the ranks changed
        """
        new: set[tuple[str, str, int, float]] = {
            (rank.device_id, rank.chip, rank.generation, rank.tier) for rank in ranks
        }
        old: set[tuple[str, str, int, float]] = set(
            self._db.execute("SELECT device_id, chip, generation, tier FROM gpu_ranks")
        )
        if new == old:
            return False
        self._db.execute("DELETE FROM gpu_ranks")
        self._db.executemany(
            "INSERT INTO gpu_ranks (device_id, chip, generation, tier) VALUES (?, ?, ?, ?)", sorted(new)
        )
        self._changed = True
        return True
