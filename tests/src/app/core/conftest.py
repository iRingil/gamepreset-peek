"""Fixtures shared by the core tests."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, create_autospec

import pytest
import responses

from app.core.database import AppData, AppDatabase, DatabaseManifest
from app.core.covers import CoverCache
from app.core.game_catalog import GameCatalog
from app.core.game_finder import GameFinder
from app.core.hardware import CpuList, GpuList, GpuRanks, HardwareDetector
from app.core.models import Game, Gpu
from app.core.ops_api import OpsApi
from app.core.service import PresetService
from app.core.user_settings import UserSettingsStore
from app.infra.http_client import HttpClient

__all__: tuple[str, ...] = ("CHECKED_MANIFEST",)

# The check of Monday 2026-10-19, started by GitHub at 08:40 UTC instead of 03:00.
CHECKED_MANIFEST: DatabaseManifest = DatabaseManifest(
    sha256="0" * 64, checked=datetime(year=2026, month=10, day=19, hour=8, minute=40, tzinfo=UTC)
)


@pytest.fixture(name="mock")
def _mock() -> Iterator[responses.RequestsMock]:
    """
    Intercept requests sent through requests.

    :return: mock to register answers on
    """
    with responses.RequestsMock() as mock:
        yield mock


@pytest.fixture(name="api")
def _api() -> Iterator[OpsApi]:
    """
    Create the API client over a real HTTP client.

    :return: API client under test
    """
    with HttpClient() as http:
        yield OpsApi(http=http)


@pytest.fixture(name="ops")
def _ops() -> MagicMock:
    """
    Stand in for the NVIDIA endpoints client.

    :return: mock with the interface of OpsApi
    """
    ops: MagicMock = create_autospec(spec=OpsApi, instance=True)
    return ops


@pytest.fixture(name="detector")
def _detector() -> MagicMock:
    """
    Stand in for the hardware detection of a system with no NVIDIA GPU.

    :return: mock with the interface of HardwareDetector
    """
    detector: MagicMock = create_autospec(spec=HardwareDetector, instance=True)
    detector.cpu_name.return_value = "13th Gen Intel(R) Core(TM) i9-13900HX"
    detector.memory_gb.return_value = 16
    detector.os_version.return_value = "10.0"
    detector.screen_resolution.return_value = "2560x1600"
    detector.nvidia_gpus.return_value = ()
    return detector


@pytest.fixture(name="store")
def _store(tmp_path: Path) -> UserSettingsStore:
    """
    Keep the user settings in a temporary folder.

    :param tmp_path: temporary directory
    :return: settings store with nothing saved
    """
    return UserSettingsStore(path=tmp_path / "settings.json")


@pytest.fixture(name="data")
def _data() -> AppData:
    """
    Make small CPU and GPU lists and two games, one with box art, as if read from the database.

    :return: database contents
    """
    return AppData(
        catalog=GameCatalog(
            games=(
                Game(game_id="mordhau", name="MORDHAU"),
                Game(game_id="baldurs_gate_3", name="Baldur's Gate 3", cover_url="https://img.example.test/bg3.jpg"),
            )
        ),
        cpu_list=CpuList(amd=("AMD Ryzen 7 7800X3D 8-Core Processor",), intel=("Intel(R) Core(TM) i7-14700K",)),
        gpu_list=GpuList(gpus=(Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507"),)),
        ranks=GpuRanks(ranks={}),
    )


@pytest.fixture(name="database")
def _database(data: AppData) -> MagicMock:
    """
    Stand in for the database file whose manifest tells of this week's check, whose download changes nothing and whose
    load gives the same contents.

    :param data: database contents
    :return: mock with the interface of AppDatabase
    """
    database: MagicMock = create_autospec(spec=AppDatabase, instance=True)
    database.manifest.return_value = CHECKED_MANIFEST
    database.download.return_value = False
    database.load.return_value = data
    return database


@pytest.fixture(name="clock")
def _clock() -> MagicMock:
    """
    Fix the current moment to Friday 2026-10-23 10:00 UTC, the week of the check on Monday 2026-10-19 03:00 UTC.

    :return: callable giving the moment
    """
    return MagicMock(return_value=datetime(year=2026, month=10, day=23, hour=10, tzinfo=UTC))


@pytest.fixture(name="finder")
def _finder() -> MagicMock:
    """
    Stand in for the search for installed games.

    :return: mock with the interface of GameFinder
    """
    finder: MagicMock = create_autospec(spec=GameFinder, instance=True)
    return finder


@pytest.fixture(name="covers")
def _covers() -> MagicMock:
    """
    Stand in for the box art cache.

    :return: mock with the interface of CoverCache
    """
    covers: MagicMock = create_autospec(spec=CoverCache, instance=True)
    return covers


@pytest.fixture(name="service")
def _service(
    ops: MagicMock,
    database: MagicMock,
    data: AppData,
    detector: MagicMock,
    store: UserSettingsStore,
    finder: MagicMock,
    covers: MagicMock,
    clock: MagicMock,
) -> PresetService:
    """
    Create the service over mocked NVIDIA, database, hardware, game search and covers, with small lists and games.

    :param ops: NVIDIA endpoints mock
    :param database: database mock
    :param data: database contents
    :param detector: hardware detection mock
    :param store: settings store
    :param finder: game search mock
    :param covers: box art cache mock
    :param clock: gives the current moment
    :return: service under test
    """
    return PresetService(
        api=ops,
        database=database,
        data=data,
        detector=detector,
        store=store,
        finder=finder,
        covers=covers,
        now=clock,
    )
