"""Tests of one run of the hardware database update script, with the sources mocked."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import responses
from update_hardware_db import _Update

from hardware_db.cpu_sources import BoincHosts, Downloaded, InstLatDumps
from hardware_db.gpu_sources import PciIds
from hardware_db.storage import HardwareDbWriter

__all__: tuple = ()


class TestUpdate:
    """Tests of _Update.run."""

    @responses.activate
    def test_sources_down(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """
        Lists the CPU sources and the GPU list not read in the report file, adding nothing and asking NVIDIA nothing.

        :param monkeypatch: pytest monkeypatch
        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        monkeypatch.setattr(
            target=BoincHosts,
            name="download",
            value=lambda **_: Downloaded(cpus=set(), failed=BoincHosts.URLS),
        )
        monkeypatch.setattr(
            target=InstLatDumps,
            name="download",
            value=lambda **_: Downloaded(cpus=set(), failed=(InstLatDumps.TREE_URL,)),
        )
        responses.get(url=PciIds.URL, status=503)
        db: Path = tmp_path / "app.db"
        report: Path = tmp_path / "report.md"
        # Act
        _Update.run(db=db, report=report)
        # Assert
        with HardwareDbWriter(path=db) as writer:
            assert (writer.cpu_names(), writer.gpu_names()) == (set(), set())
        assert report.read_text(encoding="utf-8").endswith(
            "Sources not read this time:\n"
            + "".join(f"- {url}\n" for url in (*BoincHosts.URLS, InstLatDumps.TREE_URL, PciIds.URL))
        )

    @responses.activate
    def test_gpu_ranks_read(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """
        Reads the GPU list and stores the chip ranks it gives, logging the report when no report file is asked for.

        :param monkeypatch: pytest monkeypatch
        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        for source in (BoincHosts, InstLatDumps):
            monkeypatch.setattr(target=source, name="download", value=lambda **_: Downloaded(cpus=set(), failed=()))
        responses.get(url=PciIds.URL, body="10de  NVIDIA Corporation\n\t1eb8  TU104GL [Tesla T4]\n")
        db: Path = tmp_path / "app.db"
        # Act
        _Update.run(db=db, report=None)
        # Assert
        with closing(sqlite3.connect(database=db)) as connection:
            ranked: list[tuple[str]] = connection.execute("SELECT device_id FROM gpu_ranks").fetchall()
        assert (ranked, list(tmp_path.iterdir()), len(responses.calls)) == ([("1eb8",)], [db], 1)
