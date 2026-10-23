"""Orchestration of the NVIDIA data for the UI: games, the hardware to request presets with, settings of a preset."""

from dataclasses import dataclass, replace
from functools import cached_property

from loguru import logger

from app.config import DEFAULT_RESOLUTION, SCREEN_RESOLUTIONS
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
            amd_cpus=self._cpu_list.amd,
            intel_cpus=self._cpu_list.intel,
            gpus=tuple(item for item in self._gpu_list.gpus if item.device_id not in detected_ids),
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
