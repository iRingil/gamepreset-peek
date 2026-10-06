"""Detection of the user's hardware: CPU and NVIDIA GPUs from the registry, memory size and Windows version."""

import ctypes
import json
import re
import sys
import winreg
from pathlib import Path
from typing import Any, Mapping, Self

from loguru import logger

from app.config import GPU_RANKS_FILE, GPUS_FILE
from app.core.models import Gpu

__all__: tuple[str, ...] = ("GpuList", "GpuRanks", "HardwareDetector")


class _MemoryStatus(ctypes.Structure):  # pylint: disable=too-few-public-methods
    """MEMORYSTATUSEX of the Windows API."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class HardwareDetector:
    """Reads the hardware NVIDIA identifies a system by.

    GPUs come from HARDWARE\\DEVICEMAP\\VIDEO, which Windows rebuilds at boot with the active adapters only, so a
    removed or disabled card left in the driver class key is never reported."""

    _CPU_KEY: str = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    _VIDEO_MAP_KEY: str = r"HARDWARE\DEVICEMAP\VIDEO"
    _VIDEO_DEVICE_PREFIX: str = "\\Device\\Video"
    _MACHINE_PREFIX: str = "\\registry\\machine\\"
    _NVIDIA_DEVICE_ID: re.Pattern[str] = re.compile(pattern=r"ven_10de&dev_([0-9a-f]{4})")

    @classmethod
    def cpu_name(cls) -> str:
        """
        Read the CPU name, e.g. "13th Gen Intel(R) Core(TM) i9-13900HX".

        :return: CPU name without surrounding whitespace
        """
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls._CPU_KEY) as key:
            name: str = cls._string(key=key, name="ProcessorNameString").strip()
        logger.info("CPU: {}", name)
        return name

    @classmethod
    def nvidia_gpus(cls, *, ranks: "GpuRanks") -> tuple[Gpu, ...]:
        """
        Find the active NVIDIA adapters, one per device id, the most powerful one first; ties keep the system order.

        :param ranks: performance ranks the adapters are ordered by
        :return: NVIDIA adapters; empty when there is none
        """
        gpus: dict[str, Gpu] = {}
        for driver_key in cls._video_driver_keys():
            gpu: Gpu | None = cls._nvidia_gpu(driver_key=driver_key)
            if gpu is not None and gpu.device_id not in gpus:
                gpus[gpu.device_id] = gpu
        ranked: tuple[Gpu, ...] = tuple(sorted(gpus.values(), key=lambda item: ranks.score(gpu=item), reverse=True))
        logger.info("NVIDIA GPUs: {}", ranked)
        return ranked

    @staticmethod
    def memory_gb() -> int:
        """
        Get the size of the physical memory available to Windows.

        :return: size in GiB, rounded (15.7 -> 16)
        """
        status: _MemoryStatus = _MemoryStatus(dwLength=ctypes.sizeof(_MemoryStatus))
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        global_memory_status: Any = ctypes.WinDLL(name="kernel32")["GlobalMemoryStatusEx"]
        if not global_memory_status(ctypes.byref(status)):
            raise ctypes.WinError()
        size: int = round(status.ullTotalPhys / 2**30)
        logger.info("Memory: {} GB", size)
        return size

    @staticmethod
    def os_version() -> str:
        """
        Get the Windows version as NVIDIA expects it; Windows 11 is "10.0" too.

        :return: major and minor version, e.g. "10.0"
        """
        version: Any = sys.getwindowsversion()
        text: str = f"{version.major}.{version.minor}"
        logger.info("Windows version: {}", text)
        return text

    @classmethod
    def _video_driver_keys(cls) -> list[str]:
        """
        List the driver keys of the active video adapters; an adapter with several outputs is listed several times.

        :return: driver key paths relative to HKEY_LOCAL_MACHINE, in the order of the system
        """
        paths: list[str] = []
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls._VIDEO_MAP_KEY) as key:
            index: int = 0
            while True:
                try:
                    name: str
                    value: Any
                    name, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                if name.startswith(cls._VIDEO_DEVICE_PREFIX) and isinstance(value, str):
                    # Values look like \Registry\Machine\System\CurrentControlSet\Control\Video\{guid}\0000.
                    if value.lower().startswith(cls._MACHINE_PREFIX):
                        paths.append(value[len(cls._MACHINE_PREFIX) :])
        return paths

    @classmethod
    def _nvidia_gpu(cls, *, driver_key: str) -> Gpu | None:
        """
        Read the adapter of a driver key if it is an NVIDIA one.

        :param driver_key: driver key path relative to HKEY_LOCAL_MACHINE
        :return: the adapter, or None for another vendor or an adapter without a hardware id (basic display)
        """
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, driver_key) as key:
                hardware_id: str = cls._string(key=key, name="MatchingDeviceId")
                name: str = cls._string(key=key, name="DriverDesc").strip()
        except OSError:
            logger.debug("Skipped video adapter {}: no hardware id or name", driver_key)
            return None
        match: re.Match[str] | None = cls._NVIDIA_DEVICE_ID.search(string=hardware_id.lower())
        if match is None:
            logger.debug("Skipped video adapter {}: {}", name, hardware_id)
            return None
        return Gpu(name=name, device_id=match.group(1))

    @staticmethod
    def _string(*, key: winreg.HKEYType, name: str) -> str:
        """
        Read a string value of a registry key.

        :param key: open registry key
        :param name: value name
        :return: the value
        """
        value: Any = winreg.QueryValueEx(key, name)[0]
        if not isinstance(value, str):
            raise OSError(f"registry value {name} is not a string: {value!r}")
        return value


class GpuList:
    """The bundled list of GeForce GPUs NVIDIA knows, offered when NVIDIA rejects the detected hardware."""

    def __init__(self, *, gpus: tuple[Gpu, ...]) -> None:
        """
        Use the given GPUs.

        :param gpus: GPUs in display order
        """
        self.gpus: tuple[Gpu, ...] = gpus

    @classmethod
    def load(cls, *, path: Path = GPUS_FILE) -> Self:
        """
        Load the GPUs from a JSON file.

        :param path: JSON list of objects with name and device_id
        :return: GPU list
        """
        entries: list[dict[str, str]] = json.loads(s=path.read_text(encoding="utf-8"))
        gpus: tuple[Gpu, ...] = tuple(Gpu(name=entry["name"], device_id=entry["device_id"]) for entry in entries)
        logger.debug("Loaded {} GPUs from {}", len(gpus), path)
        return cls(gpus=gpus)


class GpuRanks:
    """Rough performance scores of NVIDIA chips by device id: generation number plus the tier of the chip in it.

    A newer generation is about one chip tier faster, so the sum orders an RTX 3090 above an RTX 4060 and a GTX 780
    above a GT 1030. The bundled table covers the chips of the PCI ID database from Fermi on.

    A device id missing from it is guessed: newer than every known id means a generation after the newest known one,
    otherwise a legacy chip; the tier comes from the last two digits of the model number in the name."""

    _LEGACY_GENERATION: int = -1
    _NUMBER: re.Pattern[str] = re.compile(pattern=r"\d+")
    # Lowest last two digits of a model number for each tier, highest tier first: x90 -> 4, x60 -> 2.
    _NAME_TIERS: tuple[tuple[int, float], ...] = ((90, 4.0), (80, 3.5), (70, 3.0), (60, 2.0), (50, 1.0))

    def __init__(self, *, ranks: Mapping[str, tuple[int, float]]) -> None:
        """
        Use the given ranks.

        :param ranks: generation and chip tier by device id (4 lowercase hex digits)
        """
        self._scores: dict[str, float] = {
            device_id: generation + tier for device_id, (generation, tier) in ranks.items()
        }
        self._newest_id: int = max((int(device_id, base=16) for device_id in ranks), default=0)
        self._newest_generation: int = max((generation for generation, _ in ranks.values()), default=0)

    @classmethod
    def load(cls, *, path: Path = GPU_RANKS_FILE) -> Self:
        """
        Load the ranks from a JSON file.

        :param path: JSON object of {"chip", "generation", "tier"} objects by device id
        :return: GPU ranks
        """
        entries: dict[str, dict[str, Any]] = json.loads(s=path.read_text(encoding="utf-8"))
        logger.debug("Loaded {} GPU ranks from {}", len(entries), path)
        return cls(ranks={device_id: (entry["generation"], entry["tier"]) for device_id, entry in entries.items()})

    def score(self, *, gpu: Gpu) -> float:
        """
        Get the performance score of a GPU; a higher score means a more powerful GPU.

        :param gpu: the GPU
        :return: score from the table, or a guess for a device id missing there
        """
        known: float | None = self._scores.get(gpu.device_id)
        if known is not None:
            return known
        generation: int = (
            self._newest_generation + 1 if int(gpu.device_id, base=16) > self._newest_id else self._LEGACY_GENERATION
        )
        logger.debug("No rank for {}: guessed generation {}", gpu, generation)
        return generation + self._name_tier(name=gpu.name)

    @classmethod
    def _name_tier(cls, *, name: str) -> float:
        """
        Guess the chip tier from the last two digits of the largest number in a GPU name: "RTX 6070" -> 3.

        :param name: GPU name
        :return: tier from 0 (entry level) to 4 (flagship)
        """
        model: int = max((int(number) for number in cls._NUMBER.findall(string=name)), default=0)
        return next((tier for lowest, tier in cls._NAME_TIERS if model % 100 >= lowest), 0.0)
