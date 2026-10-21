"""Orchestration of the NVIDIA data for the UI: games, the hardware to request presets with, settings of a preset."""

from dataclasses import dataclass, replace
from functools import cached_property

from loguru import logger

from app.core.game_names import GameNames
from app.core.hardware import GpuList, GpuRanks, HardwareDetector
from app.core.models import (
    Compatibility,
    Game,
    GamePresets,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareState,
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Translations,
)
from app.core.ops_api import OpsApi
from app.core.user_settings import UserSettingsStore

__all__: tuple[str, ...] = ("PresetService",)


@dataclass(frozen=True, slots=True)
class _System:
    """The hardware NVIDIA needs besides the GPU, detected once per run."""

    cpu_name: str
    memory_gb: int
    os_version: str


@dataclass(frozen=True, slots=True)
class _GameFiles:
    """Downloaded presets and translations of a game, with the key they were requested by."""

    key: tuple[str, str, RemoteFile]
    presets: PresetsFile
    translations: Translations


class PresetService:
    """Answers the UI by chaining NVIDIA requests, the bundled data, hardware detection and the saved settings.

    Every method may block on the network or the registry: the UI calls them from a worker thread, one at a time,
    so the files of the last game shown are cached without a lock."""

    _GPU: str = "gpu"

    def __init__(
        self,
        *,
        api: OpsApi,
        names: GameNames,
        gpu_list: GpuList,
        ranks: GpuRanks,
        detector: HardwareDetector,
        store: UserSettingsStore,
    ) -> None:
        """
        Use the given data sources.

        :param api: NVIDIA endpoints client
        :param names: display names of games
        :param gpu_list: GPUs offered when NVIDIA rejects the user's one
        :param ranks: performance ranks to order detected GPUs by
        :param detector: hardware detection
        :param store: saved user settings
        """
        self._api: OpsApi = api
        self._names: GameNames = names
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

    def check_hardware(self) -> HardwareCheck:
        """
        Find the hardware to request presets with: the saved GPU, otherwise the detected NVIDIA one.

        :return: ready hardware, or the choice the user has to make, or why presets can't be requested
        """
        saved: Gpu | None = self._store.load().gpu
        if saved is not None:
            logger.info("Using the saved GPU {}", saved)
            return self._check(gpu=saved)
        detected: tuple[Gpu, ...] = self._detector.nvidia_gpus(ranks=self._ranks)
        if not detected:
            return HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        if len(detected) > 1:
            return HardwareCheck(state=HardwareState.CHOOSE_DETECTED_GPU, gpus=detected)
        return self._check(gpu=detected[0])

    def choose_gpu(self, *, gpu: Gpu) -> HardwareCheck:
        """
        Check the GPU the user chose and save it when NVIDIA accepts it.

        :param gpu: a detected GPU or one of the bundled list
        :return: ready hardware, or the choice the user has to make, or why presets can't be requested
        """
        check: HardwareCheck = self._check(gpu=gpu)
        if check.state is HardwareState.READY:
            self._store.save(settings=replace(self._store.load(), gpu=gpu))
        return check

    def forget_gpu(self) -> HardwareCheck:
        """
        Drop the saved GPU and find the hardware again, e.g. after the user changed the graphics card.

        :return: ready hardware, or the choice the user has to make, or why presets can't be requested
        """
        self._store.save(settings=replace(self._store.load(), gpu=None))
        return self.check_hardware()

    def game_presets(self, *, game_id: str, hardware: Hardware) -> GamePresets:
        """
        Request the presets NVIDIA recommends for a game.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param hardware: hardware from a READY check
        :return: profile, presets file and the resolutions; no resolutions when NVIDIA has no recommendation
        """
        return self._api.game_presets(game_id=game_id, hardware=hardware)

    def game_settings(self, *, game_id: str, presets: GamePresets, resolution: ResolutionPreset) -> GameSettings:
        """
        Get the settings NVIDIA recommends for a resolution, downloading the game's files unless cached.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param presets: presets of the game from game_presets()
        :param resolution: one of presets.resolutions
        :return: settings with their values and translations
        """
        files: _GameFiles = self._game_files(game_id=game_id, presets=presets)
        return GameSettings(values=files.presets.values(index=resolution.preset_index), translations=files.translations)

    @cached_property
    def _system(self) -> _System:
        """
        Detect the CPU, memory size and Windows version.

        :return: detected hardware besides the GPU
        """
        return _System(
            cpu_name=self._detector.cpu_name(),
            memory_gb=self._detector.memory_gb(),
            os_version=self._detector.os_version(),
        )

    def _check(self, *, gpu: Gpu) -> HardwareCheck:
        """
        Ask NVIDIA whether it supports the system with a GPU.

        :param gpu: GPU to check
        :return: READY, the bundled GPUs to choose from when only the GPU is rejected, otherwise REJECTED
        """
        hardware: Hardware = Hardware(
            cpu_name=self._system.cpu_name,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=self._system.memory_gb,
            os_version=self._system.os_version,
        )
        compatibility: Compatibility = self._api.check_compatibility(hardware=hardware)
        if compatibility.ok:
            return HardwareCheck(state=HardwareState.READY, hardware=hardware)
        if compatibility.failed == (self._GPU,):
            return HardwareCheck(state=HardwareState.CHOOSE_LISTED_GPU, gpus=self._gpu_list.gpus)
        logger.warning("NVIDIA rejected the hardware: {}", compatibility.failed)
        return HardwareCheck(state=HardwareState.REJECTED, failed=compatibility.failed)

    def _game_files(self, *, game_id: str, presets: GamePresets) -> _GameFiles:
        """
        Get the presets file and translations of a game, downloading them when the last game shown was another one.

        :param game_id: game identifier
        :param presets: presets of the game from game_presets()
        :return: the game's files
        """
        key: tuple[str, str, RemoteFile] = (game_id, presets.profile, presets.presets_file)
        if self._files is None or self._files.key != key:
            self._files = _GameFiles(
                key=key,
                presets=self._api.presets_file(file=presets.presets_file),
                translations=self._api.translations(
                    file=self._api.translation_file(game_id=game_id, profile=presets.profile)
                ),
            )
        return self._files
