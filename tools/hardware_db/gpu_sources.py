"""NVIDIA devices of the PCI ID database: GeForce GPUs to offer and the chip ranks of all devices."""

import re
from dataclasses import dataclass

from app.core.models import Gpu

__all__: tuple[str, ...] = ("GpuRank", "PciIds")


@dataclass(frozen=True, slots=True)
class GpuRank:
    """Chip of a device and its rank: generation (Fermi 0 to Blackwell 7) and tier within it (4 flagship)."""

    device_id: str
    chip: str
    generation: int
    tier: float


class PciIds:
    """Reads the NVIDIA section of pci.ids, e.g. "\\t28e0  AD107M [GeForce RTX 4060 Max-Q / Mobile]"."""

    URL: str = "https://pci-ids.ucw.cz/v2.2/pci.ids"
    _NVIDIA_VENDOR_ID: str = "10de"
    _DEVICE_LINE: re.Pattern[str] = re.compile(pattern=r"^\t([0-9a-f]{4})\s+(.*)$")
    _GEFORCE_NAME: re.Pattern[str] = re.compile(pattern=r"\[([^]]*GeForce[^]]*)]")
    # Chip name: family prefix and 3-digit number, e.g. "AD107" of "AD107M".
    _CHIP: re.Pattern[str] = re.compile(pattern=r"^(GF|GK|GM|GP|TU|GA|AD|GB)(\d{3})")
    _GENERATIONS: dict[str, int] = {"GF": 0, "GK": 1, "GM": 2, "GP": 3, "TU": 4, "GA": 5, "AD": 6, "GB": 7}
    # Tier of a chip within its generation by the last two digits of its number: x02 flagship -> 4, x07 -> 1.
    _CHIP_TIERS: dict[str, float] = {
        "00": 4.0,
        "02": 4.0,
        "10": 4.0,
        "03": 3.5,
        "04": 3.0,
        "14": 3.0,
        "05": 2.5,
        "06": 2.0,
        "16": 2.0,
        "07": 1.0,
        "17": 1.0,
        "08": 0.0,
        "18": 0.0,
        "19": 0.0,
    }

    def __init__(self, *, text: str) -> None:
        """
        Read the NVIDIA devices of the database.

        :param text: content of pci.ids
        """
        self._devices: list[tuple[str, str]] = []
        in_vendor: bool = False
        for line in text.splitlines():
            if line and not line.startswith(("\t", "#")):
                in_vendor = line.startswith(self._NVIDIA_VENDOR_ID + " ")
                continue
            match: re.Match[str] | None = self._DEVICE_LINE.match(string=line) if in_vendor else None
            if match is not None:
                self._devices.append((match.group(1), match.group(2)))

    @property
    def device_count(self) -> int:
        """
        Count the NVIDIA devices.

        :return: number of device ids
        """
        return len(self._devices)

    def ranks(self) -> list[GpuRank]:
        """
        Rank every device whose chip is of a known family and tier.

        :return: ranks in the order of the database
        """
        ranks: list[GpuRank] = []
        for device_id, description in self._devices:
            match: re.Match[str] | None = self._CHIP.match(string=description)
            tier: float | None = self._CHIP_TIERS.get(match.group(2)[-2:]) if match is not None else None
            if match is not None and tier is not None:
                ranks.append(
                    GpuRank(
                        device_id=device_id,
                        chip=description.split()[0],
                        generation=self._GENERATIONS[match.group(1)],
                        tier=tier,
                    )
                )
        return ranks

    def geforce(self) -> list[Gpu]:
        """
        Pick the devices with a GeForce name in brackets, named the way Windows names NVIDIA adapters.

        :return: GPUs in the order of the database; a name may come with several device ids
        """
        gpus: list[Gpu] = []
        for device_id, description in self._devices:
            match: re.Match[str] | None = self._GEFORCE_NAME.search(string=description)
            if match is not None:
                gpus.append(Gpu(name="NVIDIA " + match.group(1).strip(), device_id=device_id))
        return gpus
