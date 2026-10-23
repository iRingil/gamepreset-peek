"""Tests of writing the hardware database."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.core.models import Gpu
from hardware_db.cpu_sources import Cpu
from hardware_db.gpu_sources import GpuRank
from hardware_db.storage import HardwareDbWriter

__all__: tuple = ()

_RANK: GpuRank = GpuRank(device_id="2684", chip="AD102", generation=6, tier=4.0)


class _Rows:
    """Reading a database back."""

    @staticmethod
    def read(*, path: Path, sql: str) -> list[tuple[object, ...]]:
        """
        Run a query on a database file.

        :param path: database file
        :param sql: query
        :return: rows
        """
        with closing(sqlite3.connect(database=path)) as db:
            return db.execute(sql).fetchall()


class TestHardwareDbWriter:
    """Tests of HardwareDbWriter."""

    def test_rows_added(self, tmp_path: Path) -> None:
        """
        Creates the database and adds CPUs and GPUs; a row already there is kept.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        with HardwareDbWriter(path=path) as db:
            db.add_cpus(cpus=[Cpu(name="AMD Ryzen 7 7800X3D 8-Core Processor", vendor="amd")])
        # Act
        with HardwareDbWriter(path=path) as db:
            db.add_cpus(
                cpus=[
                    Cpu(name="AMD Ryzen 7 7800X3D 8-Core Processor", vendor="amd"),
                    Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel"),
                ],
            )
            db.add_gpus(gpus=[Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")])
        # Assert
        assert _Rows.read(path=path, sql="SELECT name, vendor FROM cpus ORDER BY name") == [
            ("AMD Ryzen 7 7800X3D 8-Core Processor", "amd"),
            ("Intel(R) Core(TM) i7-14700K", "intel"),
        ]
        assert _Rows.read(path=path, sql="SELECT name, device_id FROM gpus") == [("NVIDIA GeForce RTX 4090", "2684")]

    def test_names(self, tmp_path: Path) -> None:
        """
        Reads back the names of the CPUs and GPUs stored.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        with HardwareDbWriter(path=path) as db:
            db.add_cpus(cpus=[Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel")])
            db.add_gpus(gpus=[Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")])
        # Act
        with HardwareDbWriter(path=path) as db:
            names: tuple[set[str], set[str]] = (db.cpu_names(), db.gpu_names())
        # Assert
        assert names == ({"Intel(R) Core(TM) i7-14700K"}, {"NVIDIA GeForce RTX 4090"})

    def test_ranks_replaced(self, tmp_path: Path) -> None:
        """
        Replaces the ranks when they differ, reporting whether they changed.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        new_rank: GpuRank = GpuRank(device_id="2b85", chip="GB202", generation=7, tier=4.0)
        with HardwareDbWriter(path=path) as db:
            db.replace_ranks(ranks=[_RANK])
        # Act
        with HardwareDbWriter(path=path) as db:
            changes: tuple[bool, bool] = (db.replace_ranks(ranks=[new_rank]), db.replace_ranks(ranks=[new_rank]))
        # Assert
        assert changes == (True, False)
        assert _Rows.read(path=path, sql="SELECT device_id, chip, generation, tier FROM gpu_ranks") == [
            ("2b85", "GB202", 7, 4.0)
        ]

    def test_unchanged_file_kept(self, tmp_path: Path) -> None:
        """
        Leaves the file byte for byte as it was when nothing new is added.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        with HardwareDbWriter(path=path) as db:
            db.add_cpus(cpus=[Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel")])
            db.replace_ranks(ranks=[_RANK])
        before: bytes = path.read_bytes()
        # Act
        with HardwareDbWriter(path=path) as db:
            db.add_cpus(cpus=[])
            db.replace_ranks(ranks=[_RANK])
        # Assert
        assert path.read_bytes() == before

    def test_failure_rolled_back(self, tmp_path: Path) -> None:
        """
        Drops the changes of a block that fails.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        # Act & Assert
        with pytest.raises(ConnectionError), HardwareDbWriter(path=path) as db:
            db.add_cpus(cpus=[Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel")])
            raise ConnectionError("NVIDIA is down")
        assert _Rows.read(path=path, sql="SELECT name FROM cpus") == []
