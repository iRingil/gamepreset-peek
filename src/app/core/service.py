"""Orchestration of the NVIDIA data for the UI: games, the hardware to request presets with, settings of a preset."""

from dataclasses import dataclass, replace
from functools import cached_property

from loguru import logger

from app.core.game_names import GameNames
from app.core.hardware import CpuList, GpuList, GpuRanks, HardwareDetector
from app.core.models import (
    Compatibility,
    Game,
    GamePresets,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
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

    Every method may block on the network or the registry: the UI calls them from a worker thread, one at a time,
    so the files of the last game shown are cached without a lock."""

    _CPU: str = "cpu"
    _GPU: str = "gpu"

    def __init__(
        self,
        *,
        api: OpsApi,
        names: GameNames,
        cpu_list: CpuList,
        gpu_list: GpuList,
        ranks: GpuRanks,
        detector: HardwareDetector,
        store: UserSettingsStore,
    ) -> None:
        """
        Use the given data sources.

        :param api: NVIDIA endpoints client
        :param names: display names of games
        :param cpu_list: CPUs the user can choose from
        :param gpu_list: GPUs the user can choose from
        :param ranks: performance ranks to order detected GPUs by
        :param detector: hardware detection
        :param store: saved user settings
        """
        self._api: OpsApi = api
        self._names: GameNames = names
        self._cpu_list: CpuList = cpu_list
        self._gpu_list: GpuList = gpu_list
        self._ranks: GpuRanks = ranks
        self._detector: HardwareDetector = detector
        self._store: UserSettingsStore = store
        self._files: _GameFiles | None = None

    def games(self) -> tuple[Game, ...]:
        """
        Request the catalog and name its games.

        :return: games sorted by display name, case-insensitive
        """
        return tuple(
            sorted(
                (Game(game_id=game_id, name=self._names.name(game_id=game_id)) for game_id in self._api.games()),
                key=lambda game: game.name.casefold(),
            )
        )

    def hardware_setup(self) -> HardwareSetup:
        """
        Get the detected hardware, the bundled lists and the CPU and GPU to start with: saved ones, else detected ones.

        :return: hardware to show and to choose from
        """
        system: SystemHardware = self._system
        saved: UserSettings = self._store.load()
        gpu: Gpu | None = system.gpus[0] if system.gpus else None
        if saved.gpu is not None:
            # A saved card that is installed is taken as detected: that one knows its video memory.
            gpu = next((item for item in system.gpus if item == saved.gpu), saved.gpu)
        detected_ids: set[str] = {item.device_id for item in system.gpus}
        return HardwareSetup(
            system=system,
            amd_cpus=self._cpu_list.amd,
            intel_cpus=self._cpu_list.intel,
            gpus=tuple(item for item in self._gpu_list.gpus if item.device_id not in detected_ids),
            choice=HardwareChoice(cpu_name=saved.cpu_name or system.cpu_name, gpu=gpu),
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
        Check the CPU and GPU the user chose and save each one NVIDIA accepts; a detected one in use is saved as none.

        The default is detected again on the next start then. A component NVIDIA rejects keeps the one saved before.

        :param choice: CPU and GPU to check
        :return: READY with the hardware, or why presets can't be requested
        """
        check: HardwareCheck = self.check_hardware(choice=choice)
        saved: UserSettings = self._store.load()
        settings: UserSettings = replace(
            saved,
            cpu_name=self._to_save(
                chosen=choice.cpu_name,
                default=self._system.cpu_name,
                accepted=self._accepted(check=check, component=self._CPU),
                saved=saved.cpu_name,
            ),
            gpu=self._to_save(
                chosen=choice.gpu,
                default=self._system.gpus[0] if self._system.gpus else None,
                accepted=self._accepted(check=check, component=self._GPU),
                saved=saved.gpu,
            ),
        )
        if settings != saved:
            self._store.save(settings=settings)
        return check

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
            gpus=self._detector.nvidia_gpus(ranks=self._ranks),
            memory_gb=self._detector.memory_gb(),
            os_version=self._detector.os_version(),
        )

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
    def _to_save[T](*, chosen: T | None, default: T | None, accepted: bool, saved: T | None) -> T | None:
        """
        Pick what to save of a component.

        :param chosen: the component the user chose
        :param default: the component used when none is saved, i.e. the detected one
        :param accepted: whether NVIDIA accepted the chosen component
        :param saved: the component saved before
        :return: None for the default, the chosen one when accepted, otherwise the one saved before
        """
        if chosen == default:
            return None
        return chosen if accepted else saved
