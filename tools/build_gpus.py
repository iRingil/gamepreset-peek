"""Build the bundled GPU files from the PCI ID database: GeForce GPUs NVIDIA accepts and chip ranks of all devices.

Run from the repository root with src on the import path: PYTHONPATH=src python tools/build_gpus.py [--ranks-only]"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.models import Compatibility, Gpu, Hardware
from app.core.ops_api import OpsApi
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()

_DATA_DIR: Path = Path(__file__).resolve().parents[1] / "src" / "app" / "data"
_GPUS_OUTPUT: Path = _DATA_DIR / "gpus.json"
_RANKS_OUTPUT: Path = _DATA_DIR / "gpu_ranks.json"
_PCI_IDS_URL: str = "https://pci-ids.ucw.cz/v2.2/pci.ids"
_NVIDIA_VENDOR_ID: str = "10de"
# Device lines of a vendor: "\t28e0  AD107M [GeForce RTX 4060 Max-Q / Mobile]".
_DEVICE_LINE: re.Pattern[str] = re.compile(pattern=r"^\t([0-9a-f]{4})\s+(.*)$")
_GEFORCE_NAME: re.Pattern[str] = re.compile(pattern=r"\[([^]]*GeForce[^]]*)]")
# Chip name: family prefix and 3-digit number, e.g. "AD107" of "AD107M".
_CHIP: re.Pattern[str] = re.compile(pattern=r"^(GF|GK|GM|GP|TU|GA|AD|GB)(\d{3})")
# Generation number of each chip family, Fermi to Blackwell.
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
# Hardware NVIDIA accepts; only the GPU varies between the checks.
_CPU_NAME: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
_MEMORY_GB: int = 16
_OS_VERSION: str = "10.0"
_CHECK_GAME: str = "baldurs_gate_3"
_HTTP_NOT_FOUND: int = 404


class _GpusBuilder:
    """Reads NVIDIA devices from the PCI ID database, ranks their chips and checks the GeForce ones with NVIDIA."""

    @classmethod
    def build(cls, *, ranks_only: bool) -> None:
        """
        Download the PCI ID database and write the chip ranks and, unless skipped, the accepted GeForce GPUs.

        :param ranks_only: write the ranks only, without the slow NVIDIA checks of the GPU list
        :return: None
        """
        with HttpClient() as http:
            devices: list[tuple[str, str]] = cls._read(text=http.get_bytes(url=_PCI_IDS_URL).decode(encoding="utf-8"))
            logger.info("PCI ID database: {} NVIDIA device ids", len(devices))
            ranks: dict[str, dict[str, Any]] = cls._ranks(devices=devices)
            cls._write(obj=dict(sorted(ranks.items())), output=_RANKS_OUTPUT)
            logger.info("Wrote {} GPU ranks to {}", len(ranks), _RANKS_OUTPUT)
            if ranks_only:
                return
            gpus: list[Gpu] = cls._accepted_gpus(api=OpsApi(http=http), candidates=cls._geforce(devices=devices))
        cls._write(obj=[{"name": gpu.name, "device_id": gpu.device_id} for gpu in gpus], output=_GPUS_OUTPUT)
        logger.info("Wrote {} GPUs to {}", len(gpus), _GPUS_OUTPUT)

    @staticmethod
    def _read(*, text: str) -> list[tuple[str, str]]:
        """
        Read the devices of the NVIDIA vendor section.

        :param text: content of pci.ids
        :return: device id and description ("AD107M [GeForce RTX 4060 Max-Q / Mobile]"), in the order of the database
        """
        devices: list[tuple[str, str]] = []
        in_vendor: bool = False
        for line in text.splitlines():
            if line and not line.startswith(("\t", "#")):
                in_vendor = line.startswith(_NVIDIA_VENDOR_ID + " ")
                continue
            match: re.Match[str] | None = _DEVICE_LINE.match(string=line) if in_vendor else None
            if match is not None:
                devices.append((match.group(1), match.group(2)))
        return devices

    @staticmethod
    def _ranks(*, devices: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
        """
        Rank every device whose chip is of a known family and tier.

        :param devices: device ids and descriptions
        :return: chip, generation and tier by device id
        """
        ranks: dict[str, dict[str, Any]] = {}
        for device_id, description in devices:
            match: re.Match[str] | None = _CHIP.match(string=description)
            tier: float | None = _CHIP_TIERS.get(match.group(2)[-2:]) if match is not None else None
            if match is None or tier is None:
                continue
            ranks[device_id] = {
                "chip": description.split()[0],
                "generation": _GENERATIONS[match.group(1)],
                "tier": tier,
            }
        return ranks

    @staticmethod
    def _geforce(*, devices: list[tuple[str, str]]) -> list[Gpu]:
        """
        Pick the devices with a GeForce name in brackets, named the way Windows names NVIDIA adapters.

        :param devices: device ids and descriptions
        :return: GPUs in the order of the database
        """
        gpus: list[Gpu] = []
        for device_id, description in devices:
            match: re.Match[str] | None = _GEFORCE_NAME.search(string=description)
            if match is not None:
                gpus.append(Gpu(name="NVIDIA " + match.group(1).strip(), device_id=device_id))
        return gpus

    @classmethod
    def _accepted_gpus(cls, *, api: OpsApi, candidates: list[Gpu]) -> list[Gpu]:
        """
        Keep the first device id NVIDIA accepts for each GPU name.

        :param api: NVIDIA API client
        :param candidates: GeForce GPUs of the database
        :return: accepted GPUs, sorted by name
        """
        accepted: dict[str, Gpu] = {}
        for number, gpu in enumerate(candidates, start=1):
            if gpu.name in accepted:
                continue
            if cls._accepted(api=api, gpu=gpu):
                accepted[gpu.name] = gpu
            logger.info("{}/{} {} {}", number, len(candidates), gpu.device_id, gpu.name)
        return sorted(accepted.values(), key=lambda item: item.name.casefold())

    @staticmethod
    def _accepted(*, api: OpsApi, gpu: Gpu) -> bool:
        """
        Check that NVIDIA passes the GPU in the compatibility check and knows its device id for presets.

        :param api: NVIDIA API client
        :param gpu: GPU to check
        :return: True when both checks pass
        """
        hardware: Hardware = Hardware(
            cpu_name=_CPU_NAME,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=_MEMORY_GB,
            os_version=_OS_VERSION,
        )
        compatibility: Compatibility = api.check_compatibility(hardware=hardware)
        if not compatibility.ok:
            return False
        try:
            api.game_presets(game_id=_CHECK_GAME, hardware=hardware)
        except HttpClientError as error:
            if error.status != _HTTP_NOT_FOUND:
                raise
            return False
        return True

    @staticmethod
    def _write(*, obj: Any, output: Path) -> None:
        """
        Write a JSON file with LF line endings.

        :param obj: JSON value
        :param output: path to the file
        :return: None
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(data=json.dumps(obj=obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    _parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Build gpus.json and gpu_ranks.json.")
    _parser.add_argument("--ranks-only", action="store_true", help="write gpu_ranks.json only, skip the NVIDIA checks")
    _GpusBuilder.build(ranks_only=_parser.parse_args().ranks_only)
