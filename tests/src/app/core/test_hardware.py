"""Tests of the hardware detection."""

import ctypes
import re
import winreg
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import pytest

from app.config import APP_DB
from app.core.hardware import CpuList, GpuList, GpuRanks, HardwareDetector
from app.core.models import Gpu
from db_files import DbFiles

__all__: tuple = ()

_VIDEO_MAP: str = r"hardware\devicemap\video"
_CPU: str = r"hardware\description\system\centralprocessor\0"
_DRIVER: str = r"System\CurrentControlSet\Control\Video\{{{guid}}}\0000"


class _FakeKey:
    """An open key of the fake registry."""

    def __init__(self, *, values: dict[str, Any]) -> None:
        """
        Hold the values of the key.

        :param values: values by name, in enumeration order
        """
        self.values: dict[str, Any] = values

    def __enter__(self) -> Self:
        """
        Use the key as a context manager, like winreg.HKEYType.

        :return: the key itself
        """
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """
        Close the key (nothing to do).

        :param exc_type: exception type
        :param exc_value: exception
        :param traceback: traceback
        :return: None
        """


class _FakeRegistry:
    """Stands in for the winreg functions the detector calls, over keys of HKEY_LOCAL_MACHINE."""

    def __init__(self, *, keys: dict[str, dict[str, Any]]) -> None:
        """
        Hold the registry content.

        :param keys: values by name, by key path relative to HKEY_LOCAL_MACHINE
        """
        self._keys: dict[str, dict[str, Any]] = {path.lower(): values for path, values in keys.items()}

    def install(self, *, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Replace the winreg functions with the ones of this registry for the test.

        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        monkeypatch.setattr(target=winreg, name="OpenKey", value=self.open_key)
        monkeypatch.setattr(target=winreg, name="EnumValue", value=self.enum_value)
        monkeypatch.setattr(target=winreg, name="QueryValueEx", value=self.query_value)

    # noinspection PyUnusedLocal
    def open_key(self, root: int, path: str) -> _FakeKey:
        """
        Open a key like winreg.OpenKey.

        :param root: predefined root key, ignored
        :param path: key path
        :return: the key
        """
        values: dict[str, Any] | None = self._keys.get(path.lower())
        if values is None:
            raise FileNotFoundError(path)
        return _FakeKey(values=values)

    @staticmethod
    def enum_value(key: _FakeKey, index: int) -> tuple[str, Any, int]:
        """
        Enumerate the values of a key like winreg.EnumValue.

        :param key: open key
        :param index: 0-based value index
        :return: name, data and type of the value
        """
        items: list[tuple[str, Any]] = list(key.values.items())
        if index >= len(items):
            raise OSError("No more data is available")
        return items[index][0], items[index][1], winreg.REG_SZ

    @staticmethod
    def query_value(key: _FakeKey, name: str) -> tuple[Any, int]:
        """
        Read a value like winreg.QueryValueEx.

        :param key: open key
        :param name: value name
        :return: data and type of the value
        """
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], winreg.REG_SZ


class TestHardwareDetector:
    """Registry reading of the CPU and the NVIDIA adapters, memory and Windows version."""

    @pytest.fixture(name="registry")
    def _registry(self, monkeypatch: pytest.MonkeyPatch) -> _FakeRegistry:
        """
        Replace the registry with a machine of two NVIDIA cards, Intel graphics and the basic display adapter.

        :param monkeypatch: pytest monkeypatch
        :return: the fake registry
        """
        registry: _FakeRegistry = _FakeRegistry(
            keys={
                _CPU: {"ProcessorNameString": "AMD Ryzen 7 7800X3D 8-Core Processor   "},
                _VIDEO_MAP: {
                    "\\Device\\Video0": "\\Registry\\Machine\\" + _DRIVER.format(guid="rtx4060"),
                    "\\Device\\Video1": "\\Registry\\Machine\\" + _DRIVER.format(guid="rtx4060"),
                    "\\Device\\Video2": "\\REGISTRY\\MACHINE\\" + _DRIVER.format(guid="intel"),
                    "\\Device\\Video3": "\\Registry\\Machine\\" + _DRIVER.format(guid="rtx3090"),
                    "\\Device\\Video4": "\\Registry\\Machine\\" + _DRIVER.format(guid="basic"),
                    "\\Device\\Video5": "\\Registry\\Machine\\" + _DRIVER.format(guid="missing"),
                    "MaxObjectNumber": 5,
                },
                _DRIVER.format(guid="rtx4060"): {
                    "DriverDesc": "NVIDIA GeForce RTX 4060",
                    "MatchingDeviceId": "pci\\ven_10de&dev_2882",
                    "HardwareInformation.qwMemorySize": 8585740288,
                },
                _DRIVER.format(guid="intel"): {
                    "DriverDesc": "Intel(R) UHD Graphics 770",
                    "MatchingDeviceId": "PCI\\VEN_8086&DEV_A780",
                },
                _DRIVER.format(guid="rtx3090"): {
                    "DriverDesc": "NVIDIA GeForce RTX 3090",
                    "MatchingDeviceId": "PCI\\VEN_10DE&DEV_2204&SUBSYS_00000000",
                    "HardwareInformation.qwMemorySize": b"\x00",
                },
                _DRIVER.format(guid="basic"): {"DriverDesc": "Microsoft Basic Display Adapter"},
            }
        )
        registry.install(monkeypatch=monkeypatch)
        return registry

    @pytest.mark.usefixtures("registry")
    def test_cpu_name(self) -> None:
        """
        Reads the CPU name without the trailing spaces Windows pads it with.

        :return: None
        """
        # Arrange & Act
        name: str | None = HardwareDetector.cpu_name()
        # Assert
        assert name == "AMD Ryzen 7 7800X3D 8-Core Processor"

    @pytest.mark.parametrize(
        argnames="keys",
        argvalues=[
            {},
            {_CPU: {"ProcessorNameString": "   "}},
            {_CPU: {"Identifier": "Intel64 Family 6"}},
            {_CPU: {"ProcessorNameString": 6}},
        ],
        ids=["no key", "blank name", "no name", "name not a string"],
    )
    def test_cpu_not_detected(self, monkeypatch: pytest.MonkeyPatch, keys: dict[str, dict[str, Any]]) -> None:
        """
        Reports no CPU when the registry has no usable CPU name.

        :param monkeypatch: pytest monkeypatch
        :param keys: registry content
        :return: None
        """
        # Arrange
        _FakeRegistry(keys=keys).install(monkeypatch=monkeypatch)
        # Act
        name: str | None = HardwareDetector.cpu_name()
        # Assert
        assert name is None

    @pytest.fixture(name="ranks")
    def _ranks(self) -> GpuRanks:
        """
        Rank an RTX 3090 above an RTX 4060, against the order of their model numbers.

        :return: GPU ranks
        """
        return GpuRanks(ranks={"2882": (6, 1.0), "2204": (5, 4.0)})

    @pytest.mark.usefixtures("registry")
    def test_nvidia_gpus(self, ranks: GpuRanks) -> None:
        """
        Reports each active NVIDIA adapter once, the most powerful one first, with the video memory it reports.

        :param ranks: GPU ranks
        :return: None
        """
        # Arrange & Act
        gpus: tuple[Gpu, ...] = HardwareDetector.nvidia_gpus(ranks=ranks)
        # Assert
        assert gpus == (
            Gpu(name="NVIDIA GeForce RTX 3090", device_id="2204"),
            Gpu(name="NVIDIA GeForce RTX 4060", device_id="2882"),
        )
        assert [gpu.memory_gb for gpu in gpus] == [None, 8.0]

    def test_no_nvidia_gpu(self, monkeypatch: pytest.MonkeyPatch, ranks: GpuRanks) -> None:
        """
        Reports nothing when the only active adapter is not an NVIDIA one.

        :param monkeypatch: pytest monkeypatch
        :param ranks: GPU ranks
        :return: None
        """
        # Arrange
        registry: _FakeRegistry = _FakeRegistry(
            keys={
                _VIDEO_MAP: {"\\Device\\Video0": "\\Registry\\Machine\\" + _DRIVER.format(guid="amd")},
                _DRIVER.format(guid="amd"): {
                    "DriverDesc": "AMD Radeon RX 7800 XT",
                    "MatchingDeviceId": "PCI\\VEN_1002&DEV_747E",
                },
            }
        )
        registry.install(monkeypatch=monkeypatch)
        # Act
        gpus: tuple[Gpu, ...] = HardwareDetector.nvidia_gpus(ranks=ranks)
        # Assert
        assert not gpus

    def test_memory_gb(self) -> None:
        """
        Reports a positive memory size of this machine.

        :return: None
        """
        # Arrange & Act
        size: int = HardwareDetector.memory_gb()
        # Assert
        assert size > 0

    def test_os_version(self) -> None:
        """
        Reports the Windows version as major.minor.

        :return: None
        """
        # Arrange & Act
        version: str = HardwareDetector.os_version()
        # Assert
        assert re.fullmatch(pattern=r"\d+\.\d+", string=version)

    def test_screen_resolution(self) -> None:
        """
        Reports the resolution of this machine's primary screen as width x height.

        :return: None
        """
        # Arrange & Act
        resolution: str | None = HardwareDetector.screen_resolution()
        # Assert
        assert resolution is not None and re.fullmatch(pattern=r"[1-9]\d+x[1-9]\d+", string=resolution)

    def test_screen_not_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Reports no resolution when Windows gives no display mode.

        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=ctypes, name="WinDLL", value=lambda name: {"EnumDisplaySettingsW": lambda *_: 0})
        # Act
        resolution: str | None = HardwareDetector.screen_resolution()
        # Assert
        assert resolution is None


class TestCpuList:
    """Loading the bundled CPU lists."""

    def test_from_db(self, tmp_path: Path) -> None:
        """
        Reads the AMD and Intel CPUs of a database, each vendor's names sorted ignoring case.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        sql: str = "INSERT INTO cpus (name, vendor) VALUES (?, ?)"
        path: Path = DbFiles.create(
            path=tmp_path / "app.db",
            statements=[
                (sql, ("AMD Ryzen 7 7800X3D 8-Core Processor", "amd")),
                (sql, ("Intel(R) Core(TM) i7-14700K", "intel")),
                (sql, ("AMD Ryzen 5 3600 6-Core Processor", "amd")),
                (sql, ("13th Gen Intel(R) Core(TM) i9-13900HX", "intel")),
            ],
        )
        # Act
        cpu_list: CpuList = CpuList.load(path=path)
        # Assert
        assert (cpu_list.amd, cpu_list.intel) == (
            ("AMD Ryzen 5 3600 6-Core Processor", "AMD Ryzen 7 7800X3D 8-Core Processor"),
            ("13th Gen Intel(R) Core(TM) i9-13900HX", "Intel(R) Core(TM) i7-14700K"),
        )

    def test_missing_db(self, tmp_path: Path) -> None:
        """
        Fails on a missing database instead of creating an empty one.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "app.db"
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            CpuList.load(path=path)
        assert not path.exists()

    def test_bundled_db(self) -> None:
        """
        Loads the bundled database: both vendors have CPUs, a known Intel one among them.

        :return: None
        """
        # Arrange & Act
        cpu_list: CpuList = CpuList.load(path=APP_DB)
        # Assert
        assert cpu_list.amd and cpu_list.intel
        assert "13th Gen Intel(R) Core(TM) i9-13900HX" in cpu_list.intel


class TestGpuList:
    """Loading the bundled GPU list."""

    def test_from_db(self, tmp_path: Path) -> None:
        """
        Reads the GPUs of a database sorted by name, ignoring case.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        sql: str = "INSERT INTO gpus (name, device_id) VALUES (?, ?)"
        path: Path = DbFiles.create(
            path=tmp_path / "app.db",
            statements=[(sql, ("NVIDIA GeForce RTX 4090", "2684")), (sql, ("NVIDIA GeForce GTX 1060 6GB", "1c03"))],
        )
        # Act
        gpu_list: GpuList = GpuList.load(path=path)
        # Assert
        assert gpu_list.gpus == (
            Gpu(name="NVIDIA GeForce GTX 1060 6GB", device_id="1c03"),
            Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684"),
        )

    def test_bundled_db(self) -> None:
        """
        Loads the bundled database: names are unique and device ids are 4 lowercase hex digits.

        :return: None
        """
        # Arrange & Act
        gpu_list: GpuList = GpuList.load(path=APP_DB)
        # Assert
        assert gpu_list.gpus
        assert len({gpu.name for gpu in gpu_list.gpus}) == len(gpu_list.gpus)
        assert all(re.fullmatch(pattern=r"[0-9a-f]{4}", string=gpu.device_id) for gpu in gpu_list.gpus)


class TestGpuRanks:
    """Scores of known and unknown device ids."""

    @pytest.fixture(name="ranks")
    def _ranks(self) -> GpuRanks:
        """
        Rank a GTX 780 (Kepler flagship) and an RTX 5090 (the newest known chip).

        :return: GPU ranks
        """
        return GpuRanks(ranks={"1004": (1, 4.0), "2b85": (7, 4.0)})

    @pytest.mark.parametrize(
        argnames=("gpu", "expected"),
        argvalues=[
            (Gpu(name="NVIDIA GeForce GTX 780", device_id="1004"), 5.0),
            (Gpu(name="NVIDIA GeForce RTX 6070", device_id="2f80"), 11.0),
            (Gpu(name="NVIDIA GeForce RTX 6050", device_id="2f81"), 9.0),
            (Gpu(name="NVIDIA GeForce RTX 6090 Laptop GPU", device_id="2f82"), 12.0),
            (Gpu(name="NVIDIA TITAN Next", device_id="2f83"), 8.0),
            (Gpu(name="NVIDIA GeForce GTX 480", device_id="06c0"), 2.5),
            (Gpu(name="NVIDIA GeForce GT 630", device_id="0f00"), -1.0),
        ],
        ids=["known", "newer x70", "newer x50", "newer x90", "newer without number", "legacy x80", "legacy x30"],
    )
    def test_score(self, ranks: GpuRanks, gpu: Gpu, expected: float) -> None:
        """
        Takes a known score from the table and guesses an unknown one from the device id and the name.

        :param ranks: GPU ranks
        :param gpu: GPU to score
        :param expected: expected score
        :return: None
        """
        # Arrange & Act
        score: float = ranks.score(gpu=gpu)
        # Assert
        assert score == expected

    def test_from_db(self, tmp_path: Path) -> None:
        """
        Reads the ranks of a database.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = DbFiles.create(
            path=tmp_path / "app.db",
            statements=[
                (
                    "INSERT INTO gpu_ranks (device_id, chip, generation, tier) VALUES (?, ?, ?, ?)",
                    ("2684", "AD102", 6, 4.0),
                )
            ],
        )
        # Act
        ranks: GpuRanks = GpuRanks.load(path=path)
        # Assert
        assert ranks.score(gpu=Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")) == 10.0

    def test_bundled_db(self) -> None:
        """
        Loads the bundled database and orders real cards by their power across generations.

        :return: None
        """
        # Arrange
        ranks: GpuRanks = GpuRanks.load(path=APP_DB)
        stronger_weaker: list[tuple[Gpu, Gpu]] = [
            (
                Gpu(name="NVIDIA GeForce GTX 780", device_id="1004"),
                Gpu(name="NVIDIA GeForce GT 1030", device_id="1d01"),
            ),
            (
                Gpu(name="NVIDIA GeForce RTX 3090", device_id="2204"),
                Gpu(name="NVIDIA GeForce RTX 4060", device_id="2882"),
            ),
            (
                Gpu(name="NVIDIA GeForce RTX 4060", device_id="2882"),
                Gpu(name="NVIDIA GeForce GTX 1080", device_id="1b80"),
            ),
            (
                Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507"),
                Gpu(name="NVIDIA GeForce GT 710", device_id="128b"),
            ),
        ]
        # Act
        scores: list[tuple[float, float]] = [
            (ranks.score(gpu=stronger), ranks.score(gpu=weaker)) for stronger, weaker in stronger_weaker
        ]
        # Assert
        assert all(stronger > weaker for stronger, weaker in scores)
