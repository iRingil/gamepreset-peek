"""Tests of the service the UI calls."""

from unittest.mock import MagicMock

import pytest

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
    Setting,
    SettingTranslation,
    Translations,
    UserSettings,
)
from app.core.service import PresetService
from app.core.user_settings import UserSettingsStore

__all__: tuple = ()

_LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0")
_DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
_LISTED_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507")
_ACCEPTED: Compatibility = Compatibility(ok=True, failed=())
_GPU_REJECTED: Compatibility = Compatibility(ok=False, failed=("gpu",))


class _Hardware:
    """Hardware the service builds from the detection mock of conftest."""

    @staticmethod
    def with_gpu(*, gpu: Gpu) -> Hardware:
        """
        Build the hardware of the detected system with a GPU.

        :param gpu: the GPU
        :return: hardware sent to NVIDIA
        """
        return Hardware(
            cpu_name="13th Gen Intel(R) Core(TM) i9-13900HX",
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=16,
            os_version="10.0",
        )


class TestGames:
    """Tests of PresetService.games."""

    def test_named_and_sorted(self, ops: MagicMock, service: PresetService) -> None:
        """
        Names the catalog games, a missing one after its slug, and sorts them by name ignoring case.

        :param ops: NVIDIA endpoints mock
        :param service: service under test
        :return: None
        """
        # Arrange
        ops.games.return_value = ("baldurs_gate_3", "mordhau", "nba_2k27")
        # Act
        games: tuple[Game, ...] = service.games()
        # Assert
        assert games == (
            Game(game_id="baldurs_gate_3", name="Baldur's Gate 3"),
            Game(game_id="mordhau", name="MORDHAU"),
            Game(game_id="nba_2k27", name="Nba 2k27"),
        )


class TestCheckHardware:
    """Tests of PresetService.check_hardware."""

    def test_saved_gpu(
        self, ops: MagicMock, detector: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Checks the saved GPU without looking for the installed ones.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(gpu=_LISTED_GPU))
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.READY, hardware=_Hardware.with_gpu(gpu=_LISTED_GPU))
        detector.nvidia_gpus.assert_not_called()

    def test_no_nvidia_gpu(self, ops: MagicMock, service: PresetService) -> None:
        """
        Reports a system without an NVIDIA GPU and asks NVIDIA nothing.

        :param ops: NVIDIA endpoints mock
        :param service: service under test
        :return: None
        """
        # Arrange & Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        ops.check_compatibility.assert_not_called()

    def test_several_detected(self, ops: MagicMock, detector: MagicMock, service: PresetService) -> None:
        """
        Offers the detected GPUs in the detector's order, the most powerful first, before asking NVIDIA.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_DESKTOP_GPU, _LAPTOP_GPU)
        # Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.CHOOSE_DETECTED_GPU, gpus=(_DESKTOP_GPU, _LAPTOP_GPU))
        ops.check_compatibility.assert_not_called()

    def test_one_detected_accepted(self, ops: MagicMock, detector: MagicMock, service: PresetService) -> None:
        """
        Gives the detected system as ready hardware when NVIDIA accepts it.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.READY, hardware=_Hardware.with_gpu(gpu=_LAPTOP_GPU))
        ops.check_compatibility.assert_called_once_with(hardware=_Hardware.with_gpu(gpu=_LAPTOP_GPU))

    def test_gpu_rejected(self, ops: MagicMock, detector: MagicMock, service: PresetService) -> None:
        """
        Offers the bundled GPU list when NVIDIA rejects only the GPU.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = _GPU_REJECTED
        # Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.CHOOSE_LISTED_GPU, gpus=(_LISTED_GPU,))

    @pytest.mark.parametrize(
        argnames="failed",
        argvalues=[("cpu",), ("cpu", "gpu"), ()],
        ids=["cpu", "cpu and gpu", "nothing named"],
    )
    def test_rejected(
        self, ops: MagicMock, detector: MagicMock, service: PresetService, failed: tuple[str, ...]
    ) -> None:
        """
        Reports a rejection no GPU choice can fix.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :param failed: components NVIDIA rejects
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = Compatibility(ok=False, failed=failed)
        # Act
        check: HardwareCheck = service.check_hardware()
        # Assert
        assert check == HardwareCheck(state=HardwareState.REJECTED, failed=failed)

    def test_system_detected_once(self, ops: MagicMock, detector: MagicMock, service: PresetService) -> None:
        """
        Detects the CPU, memory and Windows version once however often the hardware is checked.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        service.check_hardware()
        service.check_hardware()
        # Assert
        assert (detector.cpu_name.call_count, detector.memory_gb.call_count, detector.os_version.call_count) == (
            1,
            1,
            1,
        )


class TestChooseGpu:
    """Tests of PresetService.choose_gpu and forget_gpu."""

    def test_accepted_saved(self, ops: MagicMock, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves an accepted GPU and keeps the saved language.

        :param ops: NVIDIA endpoints mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="ru"))
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.choose_gpu(gpu=_DESKTOP_GPU)
        # Assert
        assert check == HardwareCheck(state=HardwareState.READY, hardware=_Hardware.with_gpu(gpu=_DESKTOP_GPU))
        assert store.load() == UserSettings(language="ru", gpu=_DESKTOP_GPU)

    def test_rejected_not_saved(self, ops: MagicMock, store: UserSettingsStore, service: PresetService) -> None:
        """
        Offers the bundled GPU list for a rejected GPU and saves nothing.

        :param ops: NVIDIA endpoints mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        ops.check_compatibility.return_value = _GPU_REJECTED
        # Act
        check: HardwareCheck = service.choose_gpu(gpu=_DESKTOP_GPU)
        # Assert
        assert check == HardwareCheck(state=HardwareState.CHOOSE_LISTED_GPU, gpus=(_LISTED_GPU,))
        assert store.load() == UserSettings()

    def test_forget(
        self, ops: MagicMock, detector: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Drops the saved GPU, keeps the language and checks the detected GPU instead.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="de", gpu=_LISTED_GPU))
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.forget_gpu()
        # Assert
        assert check == HardwareCheck(state=HardwareState.READY, hardware=_Hardware.with_gpu(gpu=_LAPTOP_GPU))
        assert store.load() == UserSettings(language="de")


class TestGameSettings:
    """Tests of PresetService.game_presets and game_settings."""

    _PRESETS_FILE: RemoteFile = RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1)
    _TRANSLATION_FILE: RemoteFile = RemoteFile(url="https://cdn.example.test/translation", sha256="11", size=1)

    @pytest.fixture(name="presets")
    def _presets(self) -> GamePresets:
        """
        Build the presets answer of a game with two resolutions.

        :return: presets of the game
        """
        return GamePresets(
            profile="regular",
            version="1",
            presets_file=self._PRESETS_FILE,
            resolutions=(
                ResolutionPreset(resolution="1920x1080", preset_index=2, rate=40, below_min_spec=False),
                ResolutionPreset(resolution="3840x2160", preset_index=1, rate=40, below_min_spec=True),
            ),
        )

    @pytest.fixture(name="game_ops")
    def _game_ops(self, ops: MagicMock, presets: GamePresets) -> MagicMock:
        """
        Answer the game requests with two presets of one setting and its Russian translation.

        :param ops: NVIDIA endpoints mock
        :param presets: presets of the game
        :return: the mock with answers set
        """
        ops.game_presets.return_value = presets
        ops.presets_file.return_value = PresetsFile(
            settings=(Setting(name="Shadows", type="ENUM"),), presets=(("Low",), ("High",))
        )
        ops.translation_file.return_value = self._TRANSLATION_FILE
        ops.translations.return_value = Translations(
            languages={"ru_RU": {"Shadows": SettingTranslation(name="Тени", values={"High": "Высокое"})}}
        )
        return ops

    def test_presets_requested(self, game_ops: MagicMock, service: PresetService, presets: GamePresets) -> None:
        """
        Requests the presets of a game for the hardware.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange
        hardware: Hardware = _Hardware.with_gpu(gpu=_LAPTOP_GPU)
        # Act
        result: GamePresets = service.game_presets(game_id="mordhau", hardware=hardware)
        # Assert
        assert result == presets
        game_ops.game_presets.assert_called_once_with(game_id="mordhau", hardware=hardware)

    def test_settings_of_resolution(self, game_ops: MagicMock, service: PresetService, presets: GamePresets) -> None:
        """
        Gives the preset of the resolution with the game's translations.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange & Act
        settings: GameSettings = service.game_settings(
            game_id="mordhau", presets=presets, resolution=presets.resolutions[0]
        )
        # Assert
        assert settings.rows(language="ru_RU") == (("Тени", "Высокое"),)
        game_ops.presets_file.assert_called_once_with(file=self._PRESETS_FILE)
        game_ops.translation_file.assert_called_once_with(game_id="mordhau", profile="regular")
        game_ops.translations.assert_called_once_with(file=self._TRANSLATION_FILE)

    def test_files_cached_for_same_game(
        self, game_ops: MagicMock, service: PresetService, presets: GamePresets
    ) -> None:
        """
        Downloads a game's files once for all its resolutions.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange
        service.game_settings(game_id="mordhau", presets=presets, resolution=presets.resolutions[0])
        # Act
        settings: GameSettings = service.game_settings(
            game_id="mordhau", presets=presets, resolution=presets.resolutions[1]
        )
        # Assert
        assert settings.rows(language="ru_RU") == (("Тени", "Low"),)
        assert (game_ops.presets_file.call_count, game_ops.translations.call_count) == (1, 1)

    def test_files_downloaded_for_other_game(
        self, game_ops: MagicMock, service: PresetService, presets: GamePresets
    ) -> None:
        """
        Downloads the files again when another game is shown.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange
        service.game_settings(game_id="mordhau", presets=presets, resolution=presets.resolutions[0])
        # Act
        service.game_settings(game_id="baldurs_gate_3", presets=presets, resolution=presets.resolutions[0])
        # Assert
        assert (game_ops.presets_file.call_count, game_ops.translations.call_count) == (2, 2)
