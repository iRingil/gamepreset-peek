"""Tests of the service the UI calls."""

from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.database import AppData
from app.core.game_catalog import GameCatalog
from app.core.hardware import CpuList, GpuList, GpuRanks
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
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Setting,
    SettingTranslation,
    SystemHardware,
    ThemeMode,
    Translations,
    UserSettings,
)
from app.config import DEFAULT_GAME_FOLDERS, SCREEN_RESOLUTIONS
from app.core.service import PresetService
from app.core.user_settings import UserSettingsStore

__all__: tuple = ()

_LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0")
_DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
_LISTED_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507")
_DETECTED_CPU: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
_LISTED_CPU: str = "AMD Ryzen 7 7800X3D 8-Core Processor"
_ACCEPTED: Compatibility = Compatibility(ok=True, failed=())


class _Hardware:
    """Hardware the service builds from the detection mock of conftest."""

    @staticmethod
    def with_gpu(*, gpu: Gpu, cpu_name: str = _DETECTED_CPU) -> Hardware:
        """
        Build the hardware of the detected system with a GPU.

        :param gpu: the GPU
        :param cpu_name: the CPU
        :return: hardware sent to NVIDIA
        """
        return Hardware(
            cpu_name=cpu_name,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=16,
            os_version="10.0",
        )


class TestGames:
    """Tests of PresetService.games."""

    def test_from_database(self, ops: MagicMock, service: PresetService) -> None:
        """
        Gives the games of the database sorted by name, asking NVIDIA nothing.

        :param ops: NVIDIA endpoints mock
        :param service: service under test
        :return: None
        """
        # Arrange & Act
        games: tuple[Game, ...] = service.games()
        # Assert
        assert games == (
            Game(game_id="baldurs_gate_3", name="Baldur's Gate 3"),
            Game(game_id="mordhau", name="MORDHAU"),
        )
        assert not ops.mock_calls


class TestGameFolders:
    """Tests of PresetService.game_folders and save_game_folders."""

    def test_defaults_first(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Starts from the default folders, keeps the existing ones and saves the list.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        existing: tuple[str, ...] = tuple(folder for folder in DEFAULT_GAME_FOLDERS if Path(folder).is_dir())
        # Act
        folders: tuple[str, ...] = service.game_folders()
        # Assert
        assert folders == existing
        assert store.load().game_folders == existing

    def test_missing_dropped(self, tmp_path: Path, store: UserSettingsStore, service: PresetService) -> None:
        """
        Drops a saved folder missing on the computer and saves the shorter list, keeping the order.

        :param tmp_path: temporary directory
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        first: Path = tmp_path / "Games"
        second: Path = tmp_path / "More"
        first.mkdir()
        second.mkdir()
        store.save(settings=UserSettings(language="ru", game_folders=(str(second), str(tmp_path / "gone"), str(first))))
        # Act
        folders: tuple[str, ...] = service.game_folders()
        # Assert
        assert folders == (str(second), str(first))
        assert store.load() == UserSettings(language="ru", game_folders=folders)

    def test_unchanged_not_saved(self, tmp_path: Path, store: UserSettingsStore, service: PresetService) -> None:
        """
        Leaves the settings file alone when every saved folder exists, an empty list included.

        :param tmp_path: temporary directory
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(game_folders=()))
        written: int = (tmp_path / "settings.json").stat().st_mtime_ns
        # Act
        folders: tuple[str, ...] = service.game_folders()
        # Assert
        assert folders == ()
        assert (tmp_path / "settings.json").stat().st_mtime_ns == written

    def test_save(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the folders in the user's order, keeping the other settings.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="de"))
        # Act
        service.save_game_folders(folders=[r"D:\Games", r"C:\Games"])
        # Assert
        assert store.load() == UserSettings(language="de", game_folders=(r"D:\Games", r"C:\Games"))


class TestFindGames:
    """Tests of PresetService.find_games."""

    def test_catalog_and_folders(self, finder: MagicMock, data: AppData, service: PresetService) -> None:
        """
        Searches the folders with the catalog in use.

        :param finder: game search mock
        :param data: database contents
        :param service: service under test
        :return: None
        """
        # Arrange
        found: tuple[InstalledGame, ...] = (
            InstalledGame(game=Game(game_id="mordhau", name="MORDHAU"), executable=Path("D:/Games/Mordhau.exe")),
        )
        finder.find.return_value = found
        # Act
        games: tuple[InstalledGame, ...] = service.find_games(folders=[r"D:\Games"])
        # Assert
        assert games == found
        finder.find.assert_called_once_with(catalog=data.catalog, folders=[Path("D:/Games")])


class TestCover:
    """Tests of PresetService.cover."""

    def test_cached_picture(self, covers: MagicMock, service: PresetService) -> None:
        """
        Gets the picture of a game's box art URL from the cache.

        :param covers: box art cache mock
        :param service: service under test
        :return: None
        """
        # Arrange
        covers.get.return_value = Path("cover.jpg")
        game: Game = Game(game_id="baldurs_gate_3", name="Baldur's Gate 3", cover_url="https://img.example.test/a.jpg")
        # Act
        picture: Path | None = service.cover(game=game)
        # Assert
        assert picture == Path("cover.jpg")
        covers.get.assert_called_once_with(url="https://img.example.test/a.jpg")

    def test_no_box_art(self, covers: MagicMock, service: PresetService) -> None:
        """
        Gives no picture for a game without box art.

        :param covers: box art cache mock
        :param service: service under test
        :return: None
        """
        # Arrange & Act
        picture: Path | None = service.cover(game=Game(game_id="mordhau", name="MORDHAU"))
        # Assert
        assert picture is None
        covers.get.assert_not_called()


class TestDatabaseUpdate:
    """Tests of PresetService.update_database_if_due."""

    @pytest.mark.parametrize(
        argnames=("settings", "result"),
        argvalues=[
            (UserSettings(auto_update=False), DatabaseUpdate.SKIPPED),
            (UserSettings(database_updated=date(2026, 10, 16)), DatabaseUpdate.SKIPPED),
            (UserSettings(database_updated=date(2026, 10, 30)), DatabaseUpdate.SKIPPED),
            (UserSettings(database_updated=date(2026, 10, 15)), DatabaseUpdate.UNCHANGED),
            (UserSettings(), DatabaseUpdate.UNCHANGED),
        ],
        ids=["switched off", "7 days ago", "in the future", "8 days ago", "never updated"],
    )
    def test_due(
        self,
        database: MagicMock,
        store: UserSettingsStore,
        service: PresetService,
        settings: UserSettings,
        result: DatabaseUpdate,
    ) -> None:
        """
        Downloads only when updates are on and the last one is more than 7 days old or missing; records the day.

        :param database: database mock
        :param store: settings store
        :param service: service under test
        :param settings: saved settings
        :param result: expected outcome
        :return: None
        """
        # Arrange
        store.save(settings=settings)
        # Act
        outcome: DatabaseUpdate = service.update_database_if_due()
        # Assert
        assert outcome is result
        if result is DatabaseUpdate.SKIPPED:
            database.download.assert_not_called()
            assert store.load() == settings
        else:
            database.download.assert_called_once_with()
            assert store.load() == replace(settings, database_updated=date(2026, 10, 23))

    def test_new_database_loaded(
        self, database: MagicMock, store: UserSettingsStore, service: PresetService, ops: MagicMock
    ) -> None:
        """
        Reads the lists again from a new database, keeping the other settings when recording the day.

        :param database: database mock
        :param store: settings store
        :param service: service under test
        :param ops: NVIDIA endpoints mock
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="ru", chosen_gpu=_LISTED_GPU))
        database.download.return_value = True
        database.load.return_value = AppData(
            catalog=GameCatalog(games=(Game(game_id="mordhau", name="Mordhau II"),)),
            cpu_list=CpuList(amd=(), intel=()),
            gpu_list=GpuList(gpus=()),
            ranks=GpuRanks(ranks={}),
        )
        # Act
        outcome: DatabaseUpdate = service.update_database_if_due()
        saved: UserSettings = store.load()
        # Assert
        assert outcome is DatabaseUpdate.UPDATED
        assert saved == UserSettings(language="ru", chosen_gpu=_LISTED_GPU, database_updated=date(2026, 10, 23))
        assert service.games() == (Game(game_id="mordhau", name="Mordhau II"),)
        assert service.hardware_setup().amd_cpus == ()

    def test_failed_download_not_recorded(
        self, database: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Lets a failed download through and records no update, so the next start tries again.

        :param database: database mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        database.download.side_effect = ConnectionError("offline")
        # Act & Assert
        with pytest.raises(ConnectionError):
            service.update_database_if_due()
        assert store.load() == UserSettings()


class TestAutoUpdate:
    """Tests of PresetService.saved_auto_update and save_auto_update."""

    def test_nothing_saved(self, service: PresetService) -> None:
        """
        Updates automatically before anything is saved.

        :param service: service under test
        :return: None
        """
        # Arrange & Act
        enabled: bool = service.saved_auto_update()
        # Assert
        assert enabled is True

    def test_saved_keeping_others(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the switch and keeps the language and the GPU.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="ru", chosen_gpu=_LISTED_GPU))
        # Act
        service.save_auto_update(enabled=False)
        # Assert
        assert service.saved_auto_update() is False
        assert store.load() == UserSettings(language="ru", chosen_gpu=_LISTED_GPU, auto_update=False)


class TestHardwareSetup:
    """Tests of PresetService.hardware_setup."""

    def test_detected(self, detector: MagicMock, service: PresetService) -> None:
        """
        Starts from the detected CPU and the most powerful detected GPU; the bundled GPUs leave out detected ones.

        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        listed_detected: Gpu = Gpu(name="NVIDIA GeForce RTX 3050 OEM", device_id="2507", memory_gb=8.0)
        detector.nvidia_gpus.return_value = (_DESKTOP_GPU, listed_detected)
        # Act
        setup: HardwareSetup = service.hardware_setup()
        # Assert
        assert setup == HardwareSetup(
            system=SystemHardware(
                cpu_name=_DETECTED_CPU,
                gpus=(_DESKTOP_GPU, listed_detected),
                memory_gb=16,
                os_version="10.0",
                resolution="2560x1600",
            ),
            amd_cpus=(_LISTED_CPU,),
            intel_cpus=("Intel(R) Core(TM) i7-14700K",),
            gpus=(),
            resolutions=tuple(item for item in SCREEN_RESOLUTIONS if item != "2560x1600"),
            choice=HardwareChoice(cpu_name=_DETECTED_CPU, gpu=_DESKTOP_GPU),
            resolution="2560x1600",
        )

    def test_nothing_detected(self, detector: MagicMock, service: PresetService) -> None:
        """
        Starts with no CPU and no GPU when none is detected or saved, offering every bundled GPU.

        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.cpu_name.return_value = None
        detector.screen_resolution.return_value = None
        # Act
        setup: HardwareSetup = service.hardware_setup()
        # Assert
        assert (setup.choice, setup.gpus) == (HardwareChoice(cpu_name=None, gpu=None), (_LISTED_GPU,))
        assert (setup.resolutions, setup.resolution) == (SCREEN_RESOLUTIONS, "1920x1080")

    def test_detected_saved(self, detector: MagicMock, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the detected CPU, GPUs and resolution in place of the ones of the last start, keeping the rest.

        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_DESKTOP_GPU, _LAPTOP_GPU)
        store.save(
            settings=UserSettings(
                language="ru",
                detected_cpu=_LISTED_CPU,
                detected_gpus=(_LISTED_GPU,),
                detected_resolution="1920x1080",
                chosen_gpu=_LISTED_GPU,
            )
        )
        # Act
        service.hardware_setup()
        # Assert
        assert store.load() == UserSettings(
            language="ru",
            detected_cpu=_DETECTED_CPU,
            detected_gpus=(_DESKTOP_GPU, _LAPTOP_GPU),
            detected_resolution="2560x1600",
            chosen_gpu=_LISTED_GPU,
        )

    def test_chosen(self, detector: MagicMock, store: UserSettingsStore, service: PresetService) -> None:
        """
        Starts from the chosen CPU, GPU and resolution; a chosen GPU that is installed comes with its video memory.

        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        detected_laptop: Gpu = Gpu(name=_LAPTOP_GPU.name, device_id=_LAPTOP_GPU.device_id, memory_gb=8.0)
        detector.nvidia_gpus.return_value = (_DESKTOP_GPU, detected_laptop)
        store.save(settings=UserSettings(chosen_cpu=_LISTED_CPU, chosen_gpu=_LAPTOP_GPU, chosen_resolution="1920x1080"))
        # Act
        setup: HardwareSetup = service.hardware_setup()
        # Assert
        assert setup.choice == HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LAPTOP_GPU)
        assert setup.choice.gpu is not None and setup.choice.gpu.memory_gb == 8.0
        assert setup.resolution == "1920x1080"

    def test_detected_once(self, ops: MagicMock, detector: MagicMock, service: PresetService) -> None:
        """
        Detects the hardware once however often the setup is asked for and the hardware checked.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param service: service under test
        :return: None
        """
        # Arrange
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        service.hardware_setup()
        service.hardware_setup()
        service.check_hardware(choice=HardwareChoice(cpu_name=_DETECTED_CPU, gpu=_LAPTOP_GPU))
        # Assert
        mocks: tuple[MagicMock, ...] = (
            detector.cpu_name,
            detector.nvidia_gpus,
            detector.memory_gb,
            detector.os_version,
            detector.screen_resolution,
        )
        assert [mock.call_count for mock in mocks] == [1, 1, 1, 1, 1]


class TestCheckHardware:
    """Tests of PresetService.check_hardware."""

    def test_accepted(self, ops: MagicMock, store: UserSettingsStore, service: PresetService) -> None:
        """
        Gives ready hardware when NVIDIA accepts the CPU and GPU, saving nothing.

        :param ops: NVIDIA endpoints mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.check_hardware(choice=HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LAPTOP_GPU))
        # Assert
        hardware: Hardware = _Hardware.with_gpu(gpu=_LAPTOP_GPU, cpu_name=_LISTED_CPU)
        assert check == HardwareCheck(state=HardwareState.READY, hardware=hardware)
        ops.check_compatibility.assert_called_once_with(hardware=hardware)
        assert store.load() == UserSettings()

    @pytest.mark.parametrize(
        argnames=("choice", "state"),
        argvalues=[
            (HardwareChoice(cpu_name=_DETECTED_CPU, gpu=None), HardwareState.NO_NVIDIA_GPU),
            (HardwareChoice(cpu_name=None, gpu=None), HardwareState.NO_NVIDIA_GPU),
            (HardwareChoice(cpu_name=None, gpu=_LAPTOP_GPU), HardwareState.NO_CPU),
        ],
        ids=["no gpu", "nothing", "no cpu"],
    )
    def test_missing(
        self, ops: MagicMock, service: PresetService, choice: HardwareChoice, state: HardwareState
    ) -> None:
        """
        Reports a missing component, the GPU first, and asks NVIDIA nothing.

        :param ops: NVIDIA endpoints mock
        :param service: service under test
        :param choice: CPU and GPU to check
        :param state: expected state
        :return: None
        """
        # Arrange & Act
        check: HardwareCheck = service.check_hardware(choice=choice)
        # Assert
        assert check == HardwareCheck(state=state)
        ops.check_compatibility.assert_not_called()

    def test_rejected(self, ops: MagicMock, service: PresetService) -> None:
        """
        Reports the components NVIDIA rejects.

        :param ops: NVIDIA endpoints mock
        :param service: service under test
        :return: None
        """
        # Arrange
        ops.check_compatibility.return_value = Compatibility(ok=False, failed=("cpu", "gpu"))
        # Act
        check: HardwareCheck = service.check_hardware(choice=HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LAPTOP_GPU))
        # Assert
        assert check == HardwareCheck(state=HardwareState.REJECTED, failed=("cpu", "gpu"))


class TestChooseHardware:
    """Tests of PresetService.choose_hardware."""

    def test_accepted_saved(
        self, ops: MagicMock, detector: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Saves as chosen an accepted CPU and GPU the user changed, keeping the language.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_DESKTOP_GPU, _LAPTOP_GPU)
        store.save(settings=UserSettings(language="ru"))
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        check: HardwareCheck = service.choose_hardware(choice=HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LAPTOP_GPU))
        # Assert
        assert check.state is HardwareState.READY
        assert store.load() == UserSettings(language="ru", chosen_cpu=_LISTED_CPU, chosen_gpu=_LAPTOP_GPU)

    def test_unchanged_not_saved(
        self, ops: MagicMock, detector: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Saves the GPU the user changed and leaves the detected CPU in use unchosen.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        service.choose_hardware(choice=HardwareChoice(cpu_name=_DETECTED_CPU, gpu=_LISTED_GPU))
        # Assert
        assert store.load() == UserSettings(chosen_gpu=_LISTED_GPU)

    def test_detected_picked_saved(
        self, ops: MagicMock, detector: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Saves the detected GPU as chosen when the user picks it in place of another chosen one.

        :param ops: NVIDIA endpoints mock
        :param detector: hardware detection mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        detector.nvidia_gpus.return_value = (_LAPTOP_GPU,)
        store.save(settings=UserSettings(language="de", chosen_cpu=_LISTED_CPU, chosen_gpu=_LISTED_GPU))
        ops.check_compatibility.return_value = _ACCEPTED
        # Act
        service.choose_hardware(choice=HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LAPTOP_GPU))
        # Assert
        assert store.load() == UserSettings(language="de", chosen_cpu=_LISTED_CPU, chosen_gpu=_LAPTOP_GPU)

    def test_rejected_component_not_saved(
        self, ops: MagicMock, store: UserSettingsStore, service: PresetService
    ) -> None:
        """
        Saves the GPU NVIDIA accepted and keeps the CPU saved before in place of the rejected one.

        :param ops: NVIDIA endpoints mock
        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(chosen_cpu="Intel(R) Core(TM) i7-14700K"))
        ops.check_compatibility.return_value = Compatibility(ok=False, failed=("cpu",))
        # Act
        check: HardwareCheck = service.choose_hardware(choice=HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LISTED_GPU))
        # Assert
        assert check == HardwareCheck(state=HardwareState.REJECTED, failed=("cpu",))
        assert store.load() == UserSettings(chosen_cpu="Intel(R) Core(TM) i7-14700K", chosen_gpu=_LISTED_GPU)

    @pytest.mark.parametrize(
        argnames="choice",
        argvalues=[
            HardwareChoice(cpu_name=_LISTED_CPU, gpu=_LISTED_GPU),
            HardwareChoice(cpu_name=None, gpu=_LISTED_GPU),
        ],
        ids=["nothing named", "no cpu"],
    )
    def test_nothing_saved(
        self, ops: MagicMock, tmp_path: Path, service: PresetService, choice: HardwareChoice
    ) -> None:
        """
        Writes no settings when NVIDIA names no rejected component or can't be asked.

        :param ops: NVIDIA endpoints mock
        :param tmp_path: temporary directory of the settings store
        :param service: service under test
        :param choice: CPU and GPU the user chose
        :return: None
        """
        # Arrange
        ops.check_compatibility.return_value = Compatibility(ok=False, failed=())
        # Act
        service.choose_hardware(choice=choice)
        # Assert
        assert not (tmp_path / "settings.json").exists()


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

    def test_settings_of_game(self, game_ops: MagicMock, service: PresetService, presets: GamePresets) -> None:
        """
        Gives all presets of the game with its translations.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange & Act
        settings: GameSettings = service.game_settings(game_id="mordhau", presets=presets)
        # Assert
        assert (settings.count, settings.rows(index=2, language="ru_RU")) == (2, (("Тени", "Высокое"),))
        game_ops.presets_file.assert_called_once_with(file=self._PRESETS_FILE)
        game_ops.translation_file.assert_called_once_with(game_id="mordhau", profile="regular")
        game_ops.translations.assert_called_once_with(file=self._TRANSLATION_FILE)

    def test_files_cached_for_same_game(
        self, game_ops: MagicMock, service: PresetService, presets: GamePresets
    ) -> None:
        """
        Downloads a game's files once however often its settings are asked for.

        :param game_ops: NVIDIA endpoints mock with game answers
        :param service: service under test
        :param presets: presets of the game
        :return: None
        """
        # Arrange
        first: GameSettings = service.game_settings(game_id="mordhau", presets=presets)
        # Act
        second: GameSettings = service.game_settings(game_id="mordhau", presets=presets)
        # Assert
        assert second is first
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
        service.game_settings(game_id="mordhau", presets=presets)
        # Act
        service.game_settings(game_id="baldurs_gate_3", presets=presets)
        # Assert
        assert (game_ops.presets_file.call_count, game_ops.translations.call_count) == (2, 2)


class TestLanguage:
    """Tests of PresetService.saved_language and save_language."""

    def test_nothing_saved(self, service: PresetService) -> None:
        """
        Gives no language before one is saved.

        :param service: service under test
        :return: None
        """
        # Arrange & Act
        language: str | None = service.saved_language()
        # Assert
        assert language is None

    def test_saved_keeping_gpu(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the language and keeps the saved GPU.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="en", chosen_gpu=_LISTED_GPU))
        # Act
        service.save_language(language="fr")
        # Assert
        assert (service.saved_language(), store.load()) == ("fr", UserSettings(language="fr", chosen_gpu=_LISTED_GPU))


class TestResolution:
    """Tests of PresetService.save_resolution."""

    def test_saved_keeping_others(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the chosen resolution and keeps the language and the GPU.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="ru", chosen_gpu=_LISTED_GPU))
        # Act
        service.save_resolution(resolution="3840x2160")
        # Assert
        assert store.load() == UserSettings(language="ru", chosen_gpu=_LISTED_GPU, chosen_resolution="3840x2160")


class TestTheme:
    """Tests of PresetService.saved_theme and save_theme."""

    def test_nothing_saved(self, service: PresetService) -> None:
        """
        Gives AUTO before a theme is saved.

        :param service: service under test
        :return: None
        """
        # Arrange & Act
        theme: ThemeMode = service.saved_theme()
        # Assert
        assert theme is ThemeMode.AUTO

    def test_saved_keeping_others(self, store: UserSettingsStore, service: PresetService) -> None:
        """
        Saves the theme and keeps the language and the GPU.

        :param store: settings store
        :param service: service under test
        :return: None
        """
        # Arrange
        store.save(settings=UserSettings(language="ru", chosen_gpu=_LISTED_GPU))
        # Act
        service.save_theme(theme=ThemeMode.LIGHT)
        # Assert
        assert store.load() == UserSettings(language="ru", chosen_gpu=_LISTED_GPU, theme=ThemeMode.LIGHT)
