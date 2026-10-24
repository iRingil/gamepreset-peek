"""Orchestration for the UI: games, installed games, the hardware to request presets with, settings of a preset."""

from dataclasses import dataclass, replace
from datetime import date
from functools import cached_property
from pathlib import Path
from typing import Callable, Sequence

from loguru import logger

from app.config import DB_UPDATE_DAYS, DEFAULT_GAME_FOLDERS, DEFAULT_RESOLUTION, SCREEN_RESOLUTIONS
from app.core.covers import CoverCache
from app.core.database import AppData, AppDatabase
from app.core.game_finder import GameFinder
from app.core.hardware import HardwareDetector
from app.core.models import (
    Compatibility,
    DatabaseUpdate,
    Game,
    GamePresets,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
    InstalledGame,
    RemoteFile,
    SystemHardware,
    ThemeMode,
    UserSettings,
)
from app.core.ops_api import OpsApi
from app.core.user_settings import UserSettingsStore

__all__: tuple[str, ...] = ("PresetService",)


@dataclass(frozen=True, slots=True)
class _GameFiles:
    """Downloaded presets and translations of a game, with the key they were requested by."""

    key: tuple[str, str, RemoteFile]
    settings: GameSettings


class PresetService:
    """Answers the UI by chaining NVIDIA requests, the bundled data, hardware detection and the saved settings.

    Every method may block on the network, the disk or the registry: the UI calls them from a worker thread, one at a
    time, so the files of the last game shown are cached without a lock. find_games() alone runs in a thread of its
    own: it only reads the catalog in use, which an update replaces as a whole."""

    _CPU: str = "cpu"
    _GPU: str = "gpu"

    def __init__(
        self,
        *,
        api: OpsApi,
        database: AppDatabase,
        data: AppData,
        detector: HardwareDetector,
        store: UserSettingsStore,
        finder: GameFinder,
        covers: CoverCache,
        today: Callable[[], date] = date.today,
    ) -> None:
        """
        Use the given data sources.

        :param api: NVIDIA endpoints client
        :param database: the database file and its updates
        :param data: game catalog, CPU and GPU lists and GPU ranks read from the database
        :param detector: hardware detection
        :param store: saved user settings
        :param finder: search for installed games
        :param covers: box art cache
        :param today: gives the current date, for the database update schedule
        """
        self._api: OpsApi = api
        self._database: AppDatabase = database
        self._data: AppData = data
        self._detector: HardwareDetector = detector
        self._store: UserSettingsStore = store
        self._finder: GameFinder = finder
        self._covers: CoverCache = covers
        self._today: Callable[[], date] = today
        self._files: _GameFiles | None = None

    def games(self) -> tuple[Game, ...]:
        """
        Get the games of the database in use.

        :return: games sorted by display name, case-insensitive
        """
        return self._data.catalog.games

    def game_folders(self) -> tuple[str, ...]:
        """
        Get the folders to search for games: the saved ones, or the default ones before the list is first saved.

        Folders missing on the computer are dropped from the list, which is saved when that changes it.

        :return: existing folders in the user's order
        """
        saved: UserSettings = self._store.load()
        folders: tuple[str, ...] = DEFAULT_GAME_FOLDERS if saved.game_folders is None else saved.game_folders
        existing: tuple[str, ...] = tuple(folder for folder in folders if Path(folder).is_dir())
        if existing != saved.game_folders:
            dropped: list[str] = [folder for folder in folders if folder not in existing]
            if dropped:
                logger.info("Dropped missing game folders: {}", ", ".join(dropped))
            self._store.save(settings=replace(saved, game_folders=existing))
        return existing

    def save_game_folders(self, *, folders: Sequence[str]) -> None:
        """
        Save the folders to search for games, keeping the other settings.

        :param folders: folders in the user's order
        :return: None
        """
        self._store.save(settings=replace(self._store.load(), game_folders=tuple(folders)))

    def find_games(self, *, folders: Sequence[str]) -> tuple[InstalledGame, ...]:
        """
        Find the games of the database in use installed on this computer.

        :param folders: folders to search
        :return: installed games sorted by display name, case-insensitive
        """
        return self._finder.find(catalog=self._data.catalog, folders=[Path(folder) for folder in folders])

    def cover(self, *, game: Game) -> Path | None:
        """
        Get the box art of a game, downloading it unless it is cached.

        :param game: the game
        :return: the picture file, None when the game has no box art
        """
        return None if game.cover_url is None else self._covers.get(url=game.cover_url)

    def update_database_if_due(self) -> DatabaseUpdate:
        """
        Download the latest database when automatic updates are on and the last one is older than the update interval.

        A download is recorded as an update whether or not it changed anything.

        :return: SKIPPED when no update is due, UNCHANGED when the download equals the database in use, UPDATED when
            a new database is in use
        """
        saved: UserSettings = self._store.load()
        today: date = self._today()
        if not saved.auto_update or (
            saved.database_updated is not None and (today - saved.database_updated).days <= DB_UPDATE_DAYS
        ):
            return DatabaseUpdate.SKIPPED
        changed: bool = self._database.download()
        if changed:
            self._data = self._database.load()
        self._store.save(settings=replace(self._store.load(), database_updated=today))
        return DatabaseUpdate.UPDATED if changed else DatabaseUpdate.UNCHANGED

    def hardware_setup(self) -> HardwareSetup:
        """
        Detect the hardware and save it, then get the bundled lists and what is in use: chosen, else detected.

        :return: hardware and resolution to show and to choose from
        """
        system: SystemHardware = self._system
        saved: UserSettings = self._store.load()
        detected: UserSettings = replace(
            saved, detected_cpu=system.cpu_name, detected_gpus=system.gpus, detected_resolution=system.resolution
        )
        if detected != saved:
            self._store.save(settings=detected)
        gpu: Gpu | None = self._default_gpu
        if saved.chosen_gpu is not None:
            # A chosen card that is installed is taken as detected: that one knows its video memory.
            gpu = next((item for item in system.gpus if item == saved.chosen_gpu), saved.chosen_gpu)
        detected_ids: set[str] = {item.device_id for item in system.gpus}
        return HardwareSetup(
            system=system,
            amd_cpus=self._data.cpu_list.amd,
            intel_cpus=self._data.cpu_list.intel,
            gpus=tuple(item for item in self._data.gpu_list.gpus if item.device_id not in detected_ids),
            resolutions=tuple(item for item in SCREEN_RESOLUTIONS if item != system.resolution),
            choice=HardwareChoice(cpu_name=saved.chosen_cpu or system.cpu_name, gpu=gpu),
            resolution=saved.chosen_resolution or system.resolution or DEFAULT_RESOLUTION,
        )

    def check_hardware(self, *, choice: HardwareChoice) -> HardwareCheck:
        """
        Ask NVIDIA whether it supports the system with a CPU and a GPU.

        :param choice: CPU and GPU to check
        :return: READY with the hardware, or why presets can't be requested
        """
        if choice.gpu is None:
            return HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        if choice.cpu_name is None:
            return HardwareCheck(state=HardwareState.NO_CPU)
        hardware: Hardware = Hardware(
            cpu_name=choice.cpu_name,
            gpu_name=choice.gpu.name,
            gpu_device_id=choice.gpu.device_id,
            memory_gb=self._system.memory_gb,
            os_version=self._system.os_version,
        )
        compatibility: Compatibility = self._api.check_compatibility(hardware=hardware)
        if compatibility.ok:
            return HardwareCheck(state=HardwareState.READY, hardware=hardware)
        logger.warning("NVIDIA rejected the hardware: {}", compatibility.failed)
        return HardwareCheck(state=HardwareState.REJECTED, failed=compatibility.failed)

    def choose_hardware(self, *, choice: HardwareChoice) -> HardwareCheck:
        """
        Check the CPU and GPU the user chose and save as chosen the one changed, if NVIDIA accepts it.

        A component the user didn't change, or one NVIDIA rejects, keeps what was saved before.

        :param choice: CPU and GPU to check
        :return: READY with the hardware, or why presets can't be requested
        """
        check: HardwareCheck = self.check_hardware(choice=choice)
        saved: UserSettings = self._store.load()
        settings: UserSettings = replace(
            saved,
            chosen_cpu=self._to_save(
                chosen=choice.cpu_name,
                in_use=saved.chosen_cpu or self._system.cpu_name,
                accepted=self._accepted(check=check, component=self._CPU),
                saved=saved.chosen_cpu,
            ),
            chosen_gpu=self._to_save(
                chosen=choice.gpu,
                in_use=saved.chosen_gpu or self._default_gpu,
                accepted=self._accepted(check=check, component=self._GPU),
                saved=saved.chosen_gpu,
            ),
        )
        if settings != saved:
            self._store.save(settings=settings)
        return check

    def save_resolution(self, *, resolution: str) -> None:
        """
        Save the chosen screen resolution, keeping the other settings.

        :param resolution: resolution as NVIDIA writes it, e.g. "2560x1600"
        :return: None
        """
        self._store.save(settings=replace(self._store.load(), chosen_resolution=resolution))

    def saved_language(self) -> str | None:
        """
        Read the saved UI language.

        :return: language code, or None when none was saved
        """
        return self._store.load().language

    def save_language(self, *, language: str) -> None:
        """
        Save the UI language, keeping the other settings.

        :param language: language code, e.g. "ru"
        :return: None
        """
        self._store.save(settings=replace(self._store.load(), language=language))

    def saved_theme(self) -> ThemeMode:
        """
        Read the saved theme.

        :return: theme mode, AUTO when none was saved
        """
        return self._store.load().theme

    def save_theme(self, *, theme: ThemeMode) -> None:
        """
        Save the theme, keeping the other settings.

        :param theme: theme mode
        :return: None
        """
        self._store.save(settings=replace(self._store.load(), theme=theme))

    def saved_auto_update(self) -> bool:
        """
        Read whether the database is updated automatically.

        :return: True when it is, also when nothing was saved
        """
        return self._store.load().auto_update

    def save_auto_update(self, *, enabled: bool) -> None:
        """
        Save whether the database is updated automatically, keeping the other settings.

        :param enabled: True to update it
        :return: None
        """
        self._store.save(settings=replace(self._store.load(), auto_update=enabled))

    def game_presets(self, *, game_id: str, hardware: Hardware) -> GamePresets:
        """
        Request the presets NVIDIA recommends for a game.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param hardware: hardware from a READY check
        :return: profile, presets file and the resolutions; no resolutions when NVIDIA has no recommendation
        """
        return self._api.game_presets(game_id=game_id, hardware=hardware)

    def game_settings(self, *, game_id: str, presets: GamePresets) -> GameSettings:
        """
        Get all presets of a game with its translations, downloading them unless they are the cached ones.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param presets: presets of the game from game_presets()
        :return: presets and translations
        """
        key: tuple[str, str, RemoteFile] = (game_id, presets.profile, presets.presets_file)
        if self._files is None or self._files.key != key:
            self._files = _GameFiles(
                key=key,
                settings=GameSettings(
                    presets=self._api.presets_file(file=presets.presets_file),
                    translations=self._api.translations(
                        file=self._api.translation_file(game_id=game_id, profile=presets.profile)
                    ),
                ),
            )
        return self._files.settings

    @cached_property
    def _system(self) -> SystemHardware:
        """
        Detect the hardware once per run.

        :return: detected hardware
        """
        return SystemHardware(
            cpu_name=self._detector.cpu_name(),
            gpus=self._detector.nvidia_gpus(ranks=self._data.ranks),
            memory_gb=self._detector.memory_gb(),
            os_version=self._detector.os_version(),
            resolution=self._detector.screen_resolution(),
        )

    @property
    def _default_gpu(self) -> Gpu | None:
        """
        Get the GPU used when none is chosen: the most powerful detected one.

        :return: the GPU, None when no NVIDIA GPU is detected
        """
        return self._system.gpus[0] if self._system.gpus else None

    @staticmethod
    def _accepted(*, check: HardwareCheck, component: str) -> bool:
        """
        Tell whether NVIDIA accepted a component.

        :param check: result of the check
        :param component: component name as NVIDIA names it, e.g. "cpu"
        :return: True when the check passed, or failed naming other components only
        """
        if check.state is HardwareState.READY:
            return True
        return check.state is HardwareState.REJECTED and bool(check.failed) and component not in check.failed

    @staticmethod
    def _to_save[T](*, chosen: T | None, in_use: T | None, accepted: bool, saved: T | None) -> T | None:
        """
        Pick what to save as the chosen component.

        :param chosen: the component in the user's choice
        :param in_use: the component in use before: the chosen one saved, else the detected one
        :param accepted: whether NVIDIA accepted the chosen component
        :param saved: the chosen component saved before
        :return: the chosen one when the user changed it and NVIDIA accepted it, otherwise the one saved before
        """
        return chosen if chosen != in_use and accepted else saved
