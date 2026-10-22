"""Tests of reading NVIDIA devices from the PCI ID database."""

import pytest

from app.core.models import Gpu
from hardware_db.gpu_sources import GpuRank, PciIds

__all__: tuple = ()

# A cut of pci.ids: a vendor before NVIDIA, NVIDIA devices with a subsystem line, and a vendor after it.
_PCI_IDS: str = """# List of PCI ID's
1002  Advanced Micro Devices, Inc. [AMD/ATI]
\t744c  Navi 31 [Radeon RX 7900 XT/7900 XTX]
10de  NVIDIA Corporation
\t1004  GK110 [GeForce GTX 780]
\t2684  AD102 [GeForce RTX 4090]
\t\t10de 167c  RTX 4090 Founders Edition
\t28e0  AD107M [GeForce RTX 4060 Max-Q / Mobile]
\t28e1  AD107M [GeForce RTX 4060 Max-Q / Mobile]
\t1eb8  TU104GL [Tesla T4]
\t0fef  GK104 [GRID K520]
\t1aeb  TU116 High Definition Audio Controller
10df  Emulex Corporation
\t0720  OneConnect NIC [GeForce lookalike]
"""


class TestPciIds:
    """Tests of PciIds."""

    @pytest.fixture(name="pci_ids")
    def _pci_ids(self) -> PciIds:
        """
        Read the cut of pci.ids.

        :return: the database
        """
        return PciIds(text=_PCI_IDS)

    def test_devices(self, pci_ids: PciIds) -> None:
        """
        Reads only the device lines of the NVIDIA section.

        :param pci_ids: the database
        :return: None
        """
        # Arrange & Act
        count: int = pci_ids.device_count
        # Assert
        assert count == 7

    def test_ranks(self, pci_ids: PciIds) -> None:
        """
        Ranks the devices whose chip is of a known family and tier, a server chip included.

        :param pci_ids: the database
        :return: None
        """
        # Arrange & Act
        ranks: list[GpuRank] = pci_ids.ranks()
        # Assert
        assert ranks == [
            GpuRank(device_id="1004", chip="GK110", generation=1, tier=4.0),
            GpuRank(device_id="2684", chip="AD102", generation=6, tier=4.0),
            GpuRank(device_id="28e0", chip="AD107M", generation=6, tier=1.0),
            GpuRank(device_id="28e1", chip="AD107M", generation=6, tier=1.0),
            GpuRank(device_id="1eb8", chip="TU104GL", generation=4, tier=3.0),
            GpuRank(device_id="0fef", chip="GK104", generation=1, tier=3.0),
            GpuRank(device_id="1aeb", chip="TU116", generation=4, tier=2.0),
        ]

    def test_geforce(self, pci_ids: PciIds) -> None:
        """
        Names the GeForce devices the way Windows does, every device id of a name kept.

        :param pci_ids: the database
        :return: None
        """
        # Arrange & Act
        gpus: list[Gpu] = pci_ids.geforce()
        # Assert
        assert gpus == [
            Gpu(name="NVIDIA GeForce GTX 780", device_id="1004"),
            Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684"),
            Gpu(name="NVIDIA GeForce RTX 4060 Max-Q / Mobile", device_id="28e0"),
            Gpu(name="NVIDIA GeForce RTX 4060 Max-Q / Mobile", device_id="28e1"),
        ]
