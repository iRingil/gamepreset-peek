"""Tests of one update of the hardware database, with NVIDIA mocked."""

from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, create_autospec

import pytest

from app.core.models import Compatibility, Gpu, Hardware
from app.core.ops_api import OpsApi
from app.infra.http_client import HttpClientError
from hardware_db.cpu_sources import Cpu
from hardware_db.gpu_sources import PciIds
from hardware_db.storage import HardwareDbWriter
from hardware_db.updater import HardwareUpdater, UpdateReport

__all__: tuple = ()

_ACCEPTED: Compatibility = Compatibility(ok=True, failed=())
_REJECTED_CPU: Compatibility = Compatibility(ok=False, failed=("cpu",))
_KNOWN: Cpu = Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel")
_NEW: Cpu = Cpu(name="AMD Ryzen AI 9 465 w/ Radeon 880M", vendor="amd")
_UNKNOWN_TO_NVIDIA: Cpu = Cpu(name="AMD Ryzen 9 9999X 16-Core Processor", vendor="amd")
_OLD: Cpu = Cpu(name="Intel(R) Core(TM) i7-4790K CPU @ 4.00GHz", vendor="intel")
_SERVER: Cpu = Cpu(name="AMD EPYC 7302 16-Core Processor", vendor="amd")
_PCI_IDS: str = """10de  NVIDIA Corporation
\t2684  AD102 [GeForce RTX 4090]
\t2b85  GB202 [GeForce RTX 5090]
\t2b86  GB202 [GeForce RTX 5090]
\t2c02  GB203 [GeForce RTX 5080]
"""


class _UpdaterTests:
    """Fixtures: a database holding one CPU and the RTX 4090, and NVIDIA accepting everything unless told otherwise."""

    @pytest.fixture(name="api")
    def _api(self) -> MagicMock:
        """
        Mock the NVIDIA API.

        :return: mock with the interface of OpsApi
        """
        api: MagicMock = create_autospec(spec=OpsApi, instance=True)
        api.check_compatibility.return_value = _ACCEPTED
        return api

    @pytest.fixture(name="db")
    def _db(self, tmp_path: Path) -> Iterator[HardwareDbWriter]:
        """
        Open a database with one CPU and one GPU.

        :param tmp_path: temporary directory
        :return: open writer
        """
        with HardwareDbWriter(path=tmp_path / "app.db") as db:
            db.add_cpus(cpus=[_KNOWN], added="2026-09-30")
            db.add_gpus(gpus=[Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")], added="2026-09-30")
            yield db

    @pytest.fixture(name="updater")
    def _updater(self, db: HardwareDbWriter, api: MagicMock) -> HardwareUpdater:
        """
        Create the updater.

        :param db: database writer
        :param api: NVIDIA API mock
        :return: updater under test
        """
        return HardwareUpdater(db=db, api=api, added="2026-10-31")


class TestUpdateCpus(_UpdaterTests):
    """Tests of HardwareUpdater.update_cpus."""

    def test_new_cpus(self, updater: HardwareUpdater, db: HardwareDbWriter, api: MagicMock) -> None:
        """
        Adds a new CPU NVIDIA accepts; asks NVIDIA nothing about known CPUs and the ones the rules leave out.

        :param updater: updater under test
        :param db: database writer
        :param api: NVIDIA API mock
        :return: None
        """
        # Arrange
        api.check_compatibility.side_effect = lambda hardware: (
            _REJECTED_CPU if hardware.cpu_name == _UNKNOWN_TO_NVIDIA.name else _ACCEPTED
        )
        # Act
        updater.update_cpus(candidates={_KNOWN, _NEW, _UNKNOWN_TO_NVIDIA, _OLD, _SERVER})
        # Assert
        assert db.cpu_names() == {_KNOWN.name, _NEW.name}
        assert (updater.report.cpus, dict(updater.report.skipped)) == (
            [_NEW],
            {"rejected by NVIDIA": 1, "old": 1, "server": 1},
        )
        assert sorted(call.kwargs["hardware"].cpu_name for call in api.check_compatibility.call_args_list) == sorted(
            [_NEW.name, _UNKNOWN_TO_NVIDIA.name]
        )


class TestUpdateGpus(_UpdaterTests):
    """Tests of HardwareUpdater.update_gpus."""

    def test_first_accepted_id(self, updater: HardwareUpdater, db: HardwareDbWriter, api: MagicMock) -> None:
        """
        Adds each new GeForce name with the first device id NVIDIA knows for presets, and refreshes the ranks.

        :param updater: updater under test
        :param db: database writer
        :param api: NVIDIA API mock
        :return: None
        """

        # Arrange
        def presets(*, game_id: str, hardware: Hardware) -> MagicMock:
            """
            Answer 404 for the first RTX 5090 id and for the RTX 5080.

            :param game_id: game of the request
            :param hardware: hardware of the request
            :return: presets mock
            """
            if hardware.gpu_device_id in ("2b85", "2c02"):
                raise HttpClientError(status=404, url=f"https://ops.test/{game_id}", body="")
            return MagicMock()

        api.game_presets.side_effect = presets
        # Act
        updater.update_gpus(pci_ids=PciIds(text=_PCI_IDS))
        # Assert
        assert updater.report.gpus == [Gpu(name="NVIDIA GeForce RTX 5090", device_id="2b86")]
        assert db.gpu_names() == {"NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090"}
        assert updater.report.ranks_changed

    def test_rejected_gpu(self, updater: HardwareUpdater, db: HardwareDbWriter, api: MagicMock) -> None:
        """
        Leaves out a GPU the compatibility check rejects without asking for its presets.

        :param updater: updater under test
        :param db: database writer
        :param api: NVIDIA API mock
        :return: None
        """
        # Arrange
        api.check_compatibility.side_effect = lambda hardware: Compatibility(
            ok=hardware.gpu_device_id != "2c02", failed=() if hardware.gpu_device_id != "2c02" else ("gpu",)
        )
        # Act
        updater.update_gpus(pci_ids=PciIds(text=_PCI_IDS))
        # Assert
        assert db.gpu_names() == {"NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090"}
        assert "2c02" not in [call.kwargs["hardware"].gpu_device_id for call in api.game_presets.call_args_list]

    def test_nvidia_error(self, updater: HardwareUpdater, api: MagicMock) -> None:
        """
        Stops on an NVIDIA error other than 404 instead of taking the GPU as unknown.

        :param updater: updater under test
        :param api: NVIDIA API mock
        :return: None
        """
        # Arrange
        api.game_presets.side_effect = HttpClientError(status=503, url="https://ops.test/", body="")
        # Act & Assert
        with pytest.raises(HttpClientError):
            updater.update_gpus(pci_ids=PciIds(text=_PCI_IDS))


class TestUpdateReport:
    """Tests of UpdateReport."""

    def test_markdown(self) -> None:
        """
        Lists the added CPUs by vendor and the GPUs, the CPUs left out and the sources not read.

        :return: None
        """
        # Arrange
        report: UpdateReport = UpdateReport(
            cpus=[_NEW, _KNOWN],
            gpus=[Gpu(name="NVIDIA GeForce RTX 5090", device_id="2b86")],
            ranks_changed=True,
            failed=["https://numberfields.asu.edu/NumberFields/stats/host.gz"],
        )
        report.skipped.update({"old": 3, "server": 5})
        # Act
        text: str = report.markdown()
        # Assert
        assert text == (
            "Update hardware database: 2 CPUs, 1 GPUs\n"
            "\n"
            "AMD CPUs:\n"
            "- AMD Ryzen AI 9 465 w/ Radeon 880M\n"
            "\n"
            "Intel CPUs:\n"
            "- Intel(R) Core(TM) i7-14700K\n"
            "\n"
            "GPUs:\n"
            "- NVIDIA GeForce RTX 5090 (2b86)\n"
            "\n"
            "GPU chip ranks changed.\n"
            "\n"
            "CPUs left out: server 5, old 3\n"
            "\n"
            "Sources not read this time:\n"
            "- https://numberfields.asu.edu/NumberFields/stats/host.gz\n"
        )
