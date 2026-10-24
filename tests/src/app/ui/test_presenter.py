"""Tests of the main window logic on a fake window, a runner that runs tasks in place and a debouncer run by hand."""

# pylint: disable=too-many-lines

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Sequence
from unittest.mock import MagicMock, create_autospec

import pytest

from app.core.models import (
    DatabaseUpdate,
    Game,
    GameChoice,
    GamePresets,
    GamesTab,
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
)
from app.core.service import PresetService
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.presenter import Presenter
from app.ui.views import (
    ChoiceGroup,
    ChoiceView,
    HardwareView,
    InstalledGameView,
    SettingRow,
    SettingsView,
    StatusLevel,
)

__all__: tuple = ()

_LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0", memory_gb=8.0)
_DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
_CPU: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
_AMD_CPU: str = "AMD Ryzen 7 7800X3D 8-Core Processor"
_INTEL_CPU: str = "Intel(R) Core(TM) i7-14700K"
_SCREEN: str = "1920x1080"
_BUNDLED_RESOLUTIONS: tuple[str, ...] = ("3840x2160", "2560x1600", "2560x1440")
_FIT_HINT: str = "Same shape as your screen (16:9): fills it with no black bars or stretching."
# A laptop with its GPU and screen detected, the RTX 4090 in the bundled list and no bundled CPUs.
_SETUP: HardwareSetup = HardwareSetup(
    system=SystemHardware(cpu_name=_CPU, gpus=(_LAPTOP_GPU,), memory_gb=16, os_version="10.0", resolution=_SCREEN),
    amd_cpus=(),
    intel_cpus=(),
    gpus=(_DESKTOP_GPU,),
    resolutions=_BUNDLED_RESOLUTIONS,
    choice=HardwareChoice(cpu_name=_CPU, gpu=_LAPTOP_GPU),
    resolution=_SCREEN,
)
_LAPTOP_VIEW: HardwareView = HardwareView(
    cpu=_CPU, gpu="NVIDIA GeForce RTX 4060 Laptop GPU", resolution=_SCREEN, memory="16 GB", video_memory="8 GB"
)
_GAMES: tuple[Game, ...] = (
    Game(game_id="baldurs_gate_3", name="Baldur's Gate 3", cover_url="https://img.example.test/bg3.jpg"),
    Game(game_id="mordhau", name="MORDHAU"),
)
_FOLDERS: tuple[str, ...] = ("C:\\Program Files", "D:\\Games")
_BG3_EXE: Path = Path("D:/Games/Baldurs Gate 3/bin/bg3.exe")
_INSTALLED: tuple[InstalledGame, ...] = (InstalledGame(game=_GAMES[0], executable=_BG3_EXE),)
_COVER: Path = Path("cover.jpg")
_PRESETS_FILE: RemoteFile = RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1)
# No preset for 2560x1600: the one of 2560x1440 stands in; 4K is too much for the hardware.
_PRESETS: GamePresets = GamePresets(
    profile="regular",
    version="1",
    presets_file=_PRESETS_FILE,
    resolutions=(
        ResolutionPreset(resolution="1920x1080", preset_index=2, rate=40, below_min_spec=False),
        ResolutionPreset(resolution="3840x2160", preset_index=1, rate=40, below_min_spec=True),
        ResolutionPreset(resolution="2560x1440", preset_index=3, rate=35, below_min_spec=False),
    ),
)
_SETTINGS: GameSettings = GameSettings(
    presets=PresetsFile(
        settings=(Setting(name="Shadows", type="ENUM"), Setting(name="Scale", type="FLOAT")),
        presets=(("Low", "1.000"), ("Medium", "1.000"), ("High", "1.000")),
    ),
    translations=Translations(
        languages={
            "ru_RU": {
                "Shadows": SettingTranslation(
                    name="Тени", values={"Low": "Низкое", "Medium": "Среднее", "High": "Высокое"}
                ),
                "Scale": SettingTranslation(name="Масштаб", values={}),
            }
        }
    ),
)
# The recommended preset of MORDHAU at the detected screen.
_SHOWN: SettingsView = SettingsView(
    title="MORDHAU",
    position="2 / 3",
    caption="optimal preset",
    rows=(
        SettingRow(name="Shadows", value="Medium", changed=False),
        SettingRow(name="Scale", value="1.000", changed=False),
    ),
    count=3,
    index=2,
    recommended=2,
    optimal=True,
)


class _Hardware:
    """Hardware the service mock reports."""

    @staticmethod
    def with_gpu(*, gpu: Gpu, cpu_name: str = _CPU) -> Hardware:
        """
        Build hardware with a GPU.

        :param gpu: the GPU
        :param cpu_name: the CPU
        :return: hardware
        """
        return Hardware(
            cpu_name=cpu_name,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=16,
            os_version="10.0",
        )

    @classmethod
    def ready(cls, *, gpu: Gpu, cpu_name: str = _CPU) -> HardwareCheck:
        """
        Build a READY check result.

        :param gpu: the GPU in use
        :param cpu_name: the CPU in use
        :return: check result
        """
        return HardwareCheck(state=HardwareState.READY, hardware=cls.with_gpu(gpu=gpu, cpu_name=cpu_name))


class _FakeView:  # pylint: disable=too-many-instance-attributes
    """Records what the presenter shows and the choices it offers."""

    def __init__(self) -> None:
        """
        Start with an empty window.
        """
        self.language: str | None = None
        self.theme: ThemeMode | None = None
        self.auto_update: bool | None = None
        self.hardware: HardwareView | None = None
        self.status: str = ""
        self.status_level: StatusLevel = StatusLevel.INFO
        self.tab: GamesTab | None = None
        self.games: list[str] = []
        self.game_selected: int | None = None
        self.finding: bool = False
        self.installed: list[InstalledGameView] = []
        self.installed_selected: int | None = None
        self.folders: list[str] = []
        # "empty", "loading" or "picture"; the picture is None for the placeholder.
        self.cover: str = "empty"
        self.picture: Path | None = None
        self.settings: SettingsView | None = None
        self.settings_loading: bool = False
        self.cpu_offers: list[ChoiceView] = []
        self.gpu_offers: list[ChoiceView] = []
        self.resolution_offers: list[ChoiceView] = []
        self.warnings: list[str] = []

    def apply_language(self, *, translator: Translator) -> None:
        """
        Record the language.

        :param translator: translator of the UI language
        :return: None
        """
        self.language = translator.language

    def apply_theme(self, *, mode: ThemeMode) -> None:
        """
        Record the theme.

        :param mode: theme mode
        :return: None
        """
        self.theme = mode

    def show_auto_update(self, *, enabled: bool) -> None:
        """
        Record the database update switch.

        :param enabled: whether the database is updated automatically
        :return: None
        """
        self.auto_update = enabled

    def show_hardware(self, *, hardware: HardwareView) -> None:
        """
        Record the hardware block.

        :param hardware: what is shown
        :return: None
        """
        self.hardware = hardware

    def offer_cpus(self, *, choice: ChoiceView) -> None:
        """
        Record a CPU choice offered.

        :param choice: CPUs to choose from
        :return: None
        """
        self.cpu_offers.append(choice)

    def offer_gpus(self, *, choice: ChoiceView) -> None:
        """
        Record a GPU choice offered.

        :param choice: GPUs to choose from
        :return: None
        """
        self.gpu_offers.append(choice)

    def offer_resolutions(self, *, choice: ChoiceView) -> None:
        """
        Record a resolution choice offered.

        :param choice: resolutions to choose from
        :return: None
        """
        self.resolution_offers.append(choice)

    def show_status(self, *, text: str, level: StatusLevel) -> None:
        """
        Record the status line.

        :param text: the line
        :param level: how serious the line is
        :return: None
        """
        self.status = text
        self.status_level = level

    def warn(self, *, text: str) -> None:
        """
        Record a warning dialog.

        :param text: the warning
        :return: None
        """
        self.warnings.append(text)

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Record the game list.

        :param names: game names
        :param selected: position of the chosen game
        :return: None
        """
        self.games = list(names)
        self.game_selected = selected

    def show_finding(self) -> None:
        """
        Record that installed games are searched for.

        :return: None
        """
        self.finding = True

    def show_installed_games(self, *, games: Sequence[InstalledGameView], selected: int | None) -> None:
        """
        Record the installed games.

        :param games: installed games
        :param selected: position of the chosen game
        :return: None
        """
        self.finding = False
        self.installed = list(games)
        self.installed_selected = selected

    def show_tab(self, *, tab: GamesTab) -> None:
        """
        Record the game tab in front.

        :param tab: the tab
        :return: None
        """
        self.tab = tab

    def show_folders(self, *, folders: Sequence[str]) -> None:
        """
        Record the game folders.

        :param folders: folders shown
        :return: None
        """
        self.folders = list(folders)

    def show_cover(self, *, picture: Path | None) -> None:
        """
        Record the box art shown.

        :param picture: the picture, None for the placeholder
        :return: None
        """
        self.cover = "picture"
        self.picture = picture

    def clear_cover(self, *, loading: bool) -> None:
        """
        Record the cover skeleton.

        :param loading: whether the picture is on its way
        :return: None
        """
        self.cover = "loading" if loading else "empty"
        self.picture = None

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Record the settings shown.

        :param settings: what is shown
        :return: None
        """
        self.settings = settings
        self.settings_loading = False

    def clear_settings(self, *, loading: bool) -> None:
        """
        Record that no settings are shown.

        :param loading: whether settings are requested
        :return: None
        """
        self.settings = None
        self.settings_loading = loading


class _Runner:
    """Runs tasks at once, or keeps them until run_all() when deferred."""

    def __init__(self) -> None:
        """
        Run tasks at once until deferred is set.
        """
        self.deferred: bool = False
        self._jobs: list[Callable[[], None]] = []

    def submit[T](
        self, *, task: Callable[[], T], on_done: Callable[[T], None], on_error: Callable[[Exception], None]
    ) -> None:
        """
        Run a task and its callback, or keep them for later.

        :param task: the task
        :param on_done: called with the result
        :param on_error: called with the error
        :return: None
        """

        def job() -> None:
            """
            Run the task and the matching callback.

            :return: None
            """
            try:
                result: T = task()
            except Exception as error:  # pylint: disable=broad-exception-caught
                on_error(error)
                return
            on_done(result)

        if self.deferred:
            self._jobs.append(job)
        else:
            job()

    def run_all(self) -> None:
        """
        Run the kept tasks in the order they were submitted.

        :return: None
        """
        while self._jobs:
            self._jobs.pop(0)()


class _Debouncer:
    """Runs actions at once, or keeps the last one of each key until fire() when held."""

    def __init__(self) -> None:
        """
        Run actions at once until held is set.
        """
        self.held: bool = False
        self.pending: dict[str, Callable[[], None]] = {}

    def call(self, *, key: str, delay_ms: int, action: Callable[[], None]) -> None:
        """
        Run an action, or keep it in place of the one waiting under the key.

        :param key: what the action is for
        :param delay_ms: pause asked for, ignored
        :param action: the action
        :return: None
        """
        assert delay_ms > 0
        if self.held:
            self.pending[key] = action
        else:
            action()

    def fire(self) -> None:
        """
        Run the actions kept.

        :return: None
        """
        actions: list[Callable[[], None]] = list(self.pending.values())
        self.pending.clear()
        for action in actions:
            action()


class _PresenterTests:
    """Fixtures of the presenter tests: a started presenter over a mocked service with the laptop GPU ready."""

    @pytest.fixture(name="view")
    def _view(self) -> _FakeView:
        """
        Create the fake window.

        :return: fake window
        """
        return _FakeView()

    @pytest.fixture(name="runner")
    def _runner(self) -> _Runner:
        """
        Create the runner.

        :return: runner running tasks at once
        """
        return _Runner()

    @pytest.fixture(name="finder")
    def _finder(self) -> _Runner:
        """
        Create the runner of the search for installed games.

        :return: runner running tasks at once
        """
        return _Runner()

    @pytest.fixture(name="debouncer")
    def _debouncer(self) -> _Debouncer:
        """
        Create the debouncer.

        :return: debouncer running actions at once
        """
        return _Debouncer()

    @pytest.fixture(name="service")
    def _service(self) -> MagicMock:
        """
        Mock the service: two games, one installed, the all games tab saved, the laptop accepted, presets and box art.

        :return: mock with the interface of PresetService
        """
        service: MagicMock = create_autospec(spec=PresetService, instance=True)
        service.games.return_value = _GAMES
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.ALL)
        service.hardware_setup.return_value = _SETUP
        service.check_hardware.return_value = _Hardware.ready(gpu=_LAPTOP_GPU)
        service.game_presets.return_value = _PRESETS
        service.game_settings.return_value = _SETTINGS
        service.update_database_if_due.return_value = DatabaseUpdate.SKIPPED
        service.game_folders.return_value = _FOLDERS
        service.find_games.return_value = _INSTALLED
        service.cover.return_value = _COVER
        return service

    @pytest.fixture(name="presenter")
    def _presenter(  # pylint: disable=too-many-arguments
        self,
        view: _FakeView,
        runner: _Runner,
        finder: _Runner,
        debouncer: _Debouncer,
        service: MagicMock,
        locale_dir: Path,
    ) -> Presenter:
        """
        Create the presenter in English with automatic database updates on; tests start it themselves.

        :param view: fake window
        :param runner: runner
        :param finder: runner of the search for installed games
        :param debouncer: debouncer
        :param service: service mock
        :param locale_dir: compiled catalogs
        :return: presenter under test
        """
        return Presenter(
            view=view,
            service=service,
            runner=runner,
            finder=finder,
            debouncer=debouncer,
            translator=Translator(language="en", locale_dir=locale_dir),
            theme=ThemeMode.AUTO,
            auto_update=True,
            locale_dir=locale_dir,
        )

    @staticmethod
    def start(*, presenter: Presenter, service: MagicMock) -> None:
        """
        Start, then forget the requests made for the game chosen at the start.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        presenter.start()
        service.game_presets.reset_mock()
        service.game_settings.reset_mock()
        service.cover.reset_mock()

    @staticmethod
    def show_settings(*, presenter: Presenter) -> None:
        """
        Start and pick MORDHAU, which shows its settings for the detected screen.

        :param presenter: presenter under test
        :return: None
        """
        presenter.start()
        presenter.select_game(index=1)


class TestStart(_PresenterTests):
    """Tests of Presenter.start and the hardware flow."""

    def test_games_and_hardware(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the games, the first one chosen, and the detected hardware in the initial language; warns of nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange & Act
        presenter.start()
        # Assert
        assert (view.theme, view.auto_update) == (ThemeMode.AUTO, True)
        assert (view.language, view.games, view.hardware, view.status) == (
            "en",
            ["Baldur's Gate 3", "MORDHAU"],
            _LAPTOP_VIEW,
            "",
        )
        assert (view.tab, view.game_selected, view.cover) == (GamesTab.ALL, 0, "picture")
        assert view.settings is not None and view.settings.title == "Baldur's Gate 3"
        service.check_hardware.assert_called_once_with(choice=HardwareChoice(cpu_name=_CPU, gpu=_LAPTOP_GPU))
        service.update_database_if_due.assert_called_once_with()
        assert not view.warnings

    def test_hardware_loading(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Shows the hardware as loading until it is detected.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        runner.deferred = True
        # Act
        presenter.start()
        # Assert
        assert view.hardware == HardwareView(
            cpu="Loading…", gpu="Loading…", resolution="Loading…", memory="", video_memory=""
        )

    def test_nothing_detected(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Warns that only NVIDIA GPUs and AMD or Intel CPUs are supported and invites a choice in place of both.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = HardwareSetup(
            system=SystemHardware(cpu_name=None, gpus=(), memory_gb=8, os_version="10.0", resolution=None),
            amd_cpus=(),
            intel_cpus=(),
            gpus=(_DESKTOP_GPU,),
            resolutions=_BUNDLED_RESOLUTIONS,
            choice=HardwareChoice(cpu_name=None, gpu=None),
            resolution="1920x1080",
        )
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        # Act
        presenter.start()
        # Assert
        assert view.hardware == HardwareView(
            cpu="Choose a processor",
            gpu="Choose a graphics card",
            resolution="1920x1080",
            memory="8 GB",
            video_memory="unknown",
        )
        assert view.warnings == [UiText.UNSUPPORTED_HARDWARE.value]

    @pytest.mark.parametrize(
        argnames="choice",
        argvalues=[HardwareChoice(cpu_name=None, gpu=_LAPTOP_GPU), HardwareChoice(cpu_name=_CPU, gpu=None)],
        ids=["no cpu", "no gpu"],
    )
    def test_one_missing_warned(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, choice: HardwareChoice
    ) -> None:
        """
        Warns once when only the CPU or only the GPU is neither chosen nor detected.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param choice: CPU and GPU in use at the start
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(_SETUP, choice=choice)
        # Act
        presenter.start()
        # Assert
        assert view.warnings == [UiText.UNSUPPORTED_HARDWARE.value]

    def test_setup_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed hardware detection and asks NVIDIA nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.side_effect = OSError("no registry")
        # Act
        presenter.start()
        # Assert
        assert view.status == "Could not detect the hardware: no registry"
        assert view.status_level is StatusLevel.ERROR
        service.check_hardware.assert_not_called()

    def test_first_check_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed first hardware check and requests no presets with the unchecked hardware.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.side_effect = ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.select_game(index=1)
        # Assert
        assert (view.status, view.hardware) == ("Could not get data from NVIDIA: timeout", _LAPTOP_VIEW)
        service.game_presets.assert_not_called()

    @pytest.mark.parametrize(
        argnames=("check", "expected"),
        argvalues=[
            (
                HardwareCheck(state=HardwareState.NO_NVIDIA_GPU),
                "No NVIDIA graphics card found. This app recommends settings for NVIDIA graphics cards only.",
            ),
            (
                HardwareCheck(state=HardwareState.NO_CPU),
                "Could not detect the processor. Choose yours from the list.",
            ),
            (
                HardwareCheck(state=HardwareState.REJECTED, failed=("cpu",)),
                "NVIDIA does not know your processor. Choose it from the list.",
            ),
            (
                HardwareCheck(state=HardwareState.REJECTED, failed=("gpu",)),
                "NVIDIA does not know your graphics card. Choose the closest one from the list.",
            ),
            (
                HardwareCheck(state=HardwareState.REJECTED, failed=("cpu", "bios")),
                "NVIDIA does not support this computer: processor, bios.",
            ),
        ],
        ids=["no nvidia gpu", "no cpu", "cpu rejected", "gpu rejected", "several rejected"],
    )
    def test_no_hardware(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, check: HardwareCheck, expected: str
    ) -> None:
        """
        Explains in the status line why there are no recommendations; unknown component names are shown as they come.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param check: hardware check result
        :param expected: status line
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = check
        # Act
        presenter.start()
        # Assert
        assert view.status == expected

    def test_problem_outlives_search(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner
    ) -> None:
        """
        Keeps the hardware problem in the status line when the installed games arrive after it.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("gpu",))
        finder.deferred = True
        presenter.start()
        # Act
        finder.run_all()
        # Assert
        assert view.status == "NVIDIA does not know your graphics card. Choose the closest one from the list."


class TestGame(_PresenterTests):
    """Tests of Presenter.select_game."""

    def test_no_hardware(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Repeats why there are no recommendations when a game is chosen without accepted hardware.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        presenter.start()
        view.status = ""
        # Act
        presenter.select_game(index=1)
        # Assert
        assert view.status == (
            "No NVIDIA graphics card found. This app recommends settings for NVIDIA graphics cards only."
        )
        service.game_presets.assert_not_called()

    def test_settings_shown(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Requests the presets of the game and shows the recommended preset of the screen in use at once.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.start(presenter=presenter, service=service)
        # Act
        presenter.select_game(index=1)
        # Assert
        service.game_presets.assert_called_once_with(game_id="mordhau", hardware=_Hardware.with_gpu(gpu=_LAPTOP_GPU))
        service.game_settings.assert_called_once_with(game_id="mordhau", presets=_PRESETS)
        assert (view.settings, view.status) == (_SHOWN, "")

    def test_requests_wait_for_the_selection_to_rest(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, debouncer: _Debouncer
    ) -> None:
        """
        Requests the presets of the game the selection rests on only, showing it loading meanwhile.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param debouncer: debouncer
        :return: None
        """
        # Arrange
        self.start(presenter=presenter, service=service)
        debouncer.held = True
        # Act
        presenter.select_game(index=1)
        presenter.select_game(index=0)
        presenter.select_game(index=1)
        waiting: tuple[str, int] = (view.status, service.game_presets.call_count)
        debouncer.fire()
        # Assert
        assert waiting == ("Loading…", 0)
        service.game_presets.assert_called_once_with(game_id="mordhau", hardware=_Hardware.with_gpu(gpu=_LAPTOP_GPU))

    def test_pending_request_dropped_without_hardware(
        self, presenter: Presenter, service: MagicMock, debouncer: _Debouncer
    ) -> None:
        """
        Requests nothing when the hardware is lost while the selection is still resting on a game.

        :param presenter: presenter under test
        :param service: service mock
        :param debouncer: debouncer
        :return: None
        """
        # Arrange
        service.choose_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("gpu",))
        self.start(presenter=presenter, service=service)
        debouncer.held = True
        presenter.select_game(index=1)
        presenter.choose_gpu(position=1)
        # Act
        debouncer.fire()
        # Assert
        service.game_presets.assert_not_called()

    def test_no_recommendations(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Says so when NVIDIA has no recommendation for the game.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.return_value = GamePresets(
            profile="regular", version="1", presets_file=_PRESETS_FILE, resolutions=()
        )
        presenter.start()
        # Act
        presenter.select_game(index=0)
        # Assert
        assert (view.settings, view.status) == (
            None,
            "No recommendations (there are none, or your hardware is too weak for this resolution and game)",
        )
        assert view.status_level is StatusLevel.WARNING
        service.game_settings.assert_not_called()

    def test_presets_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed presets request.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.side_effect = ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.select_game(index=1)
        # Assert
        assert (view.status, view.settings) == ("Could not get data from NVIDIA: timeout", None)

    def test_stale_answer_dropped(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, runner: _Runner
    ) -> None:
        """
        Drops the presets of a game the user left before they arrived.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param runner: runner
        :return: None
        """
        # Arrange
        shown: list[str] = []

        def record(*, settings: SettingsView) -> None:
            """
            Record the title of every settings view shown.

            :param settings: what is shown
            :return: None
            """
            shown.append(settings.title)

        presenter.start()
        runner.deferred = True
        view.show_settings = record  # type: ignore[method-assign]
        presenter.select_game(index=1)
        presenter.select_game(index=0)
        # Act
        runner.run_all()
        # Assert
        assert shown == ["Baldur's Gate 3"]
        assert service.game_settings.call_args.kwargs["game_id"] == "baldurs_gate_3"

    def test_game_change_clears(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Clears the settings as soon as another game is chosen.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        runner.deferred = True
        # Act
        presenter.select_game(index=0)
        # Assert
        assert (view.settings, view.status) == (None, "Loading…")
        assert view.status_level is StatusLevel.INFO


class TestSettings(_PresenterTests):
    """Tests of the settings shown, Presenter.move_slider and back_to_optimal."""

    def test_slider_and_back_to_optimal(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Shows another preset, marking what differs from the recommended one, and returns to it on request.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.move_slider(index=3)
        moved: SettingsView | None = view.settings
        presenter.back_to_optimal()
        # Assert
        assert moved == SettingsView(
            title="MORDHAU",
            position="3 / 3",
            caption="preset",
            rows=(
                SettingRow(name="Shadows", value="High", changed=True),
                SettingRow(name="Scale", value="1.000", changed=False),
            ),
            count=3,
            index=3,
            recommended=2,
            optimal=False,
        )
        assert view.settings is not None and (view.settings.index, view.settings.optimal) == (2, True)

    @pytest.mark.parametrize(argnames="index", argvalues=[0, 4], ids=["below", "above"])
    def test_slider_out_of_range(self, presenter: Presenter, view: _FakeView, index: int) -> None:
        """
        Ignores a slider position outside the presets.

        :param presenter: presenter under test
        :param view: fake window
        :param index: slider position
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.move_slider(index=index)
        # Assert
        assert view.settings is not None and view.settings.index == 2

    def test_slider_without_settings(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Ignores the slider and the request for the recommended preset while no settings are shown.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_settings.side_effect = ConnectionError("timeout")
        self.show_settings(presenter=presenter)
        # Act
        presenter.move_slider(index=1)
        presenter.back_to_optimal()
        # Assert
        assert view.settings is None

    def test_settings_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed settings request.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_settings.side_effect = ConnectionError("timeout")
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert (view.status, view.settings) == ("Could not get data from NVIDIA: timeout", None)


class TestResolution(_PresenterTests):
    """Tests of Presenter.open_resolution_choice and choose_resolution."""

    def test_resolutions_offered(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner
    ) -> None:
        """
        Offers the detected screen above the bundled resolutions while no game's presets are known, marking its shape.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        finder.deferred = True
        presenter.start()
        # Act
        presenter.open_resolution_choice()
        # Assert
        assert view.resolution_offers == [
            ChoiceView(
                detected=(_SCREEN,),
                groups=(ChoiceGroup(title="", items=_BUNDLED_RESOLUTIONS),),
                selected=0,
                fitting=frozenset({1, 3}),
                fit_mark="16:9",
                fit_hint=_FIT_HINT,
            )
        ]

    def test_game_resolutions_offered(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Offers the detected screen above the game's own resolutions, the largest first, without repeating it.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.open_resolution_choice()
        # Assert
        assert view.resolution_offers == [
            ChoiceView(
                detected=(_SCREEN,),
                groups=(ChoiceGroup(title="", items=("3840x2160", "2560x1440")),),
                selected=0,
                fitting=frozenset({1, 2}),
                fit_mark="16:9",
                fit_hint=_FIT_HINT,
            )
        ]

    def test_pick_from_offered_list(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Takes a pick from the list offered, even when the game's presets arrived after it was opened.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.open_resolution_choice()
        service.game_presets.return_value = replace(_PRESETS, resolutions=_PRESETS.resolutions[:1])
        presenter.select_game(index=0)
        # Act
        presenter.choose_resolution(position=2)
        # Assert
        service.save_resolution.assert_called_once_with(resolution="2560x1440")

    def test_no_screen_detected(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner
    ) -> None:
        """
        Offers only the bundled resolutions, none marked, when no screen is detected, the one in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        finder.deferred = True
        service.hardware_setup.return_value = replace(
            _SETUP, system=replace(_SETUP.system, resolution=None), resolution="2560x1600"
        )
        presenter.start()
        # Act
        presenter.open_resolution_choice()
        # Assert
        assert view.resolution_offers == [
            ChoiceView(detected=(), groups=(ChoiceGroup(title="", items=_BUNDLED_RESOLUTIONS),), selected=1)
        ]

    def test_nothing_offered_before_detection(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Offers nothing and takes no pick while the hardware is not detected yet.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        runner.deferred = True
        presenter.start()
        # Act
        presenter.open_resolution_choice()
        presenter.choose_resolution(position=1)
        # Assert
        assert (view.resolution_offers, view.hardware is not None and view.hardware.resolution) == ([], "Loading…")

    def test_chosen_saved_and_applied(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Saves the resolution picked, shows it and the settings of the game for it.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.open_resolution_choice()
        # Act
        presenter.choose_resolution(position=2)
        # Assert
        service.save_resolution.assert_called_once_with(resolution="2560x1440")
        assert view.hardware is not None and view.hardware.resolution == "2560x1440"
        assert view.settings is not None and (view.settings.index, view.status) == (3, "")

    def test_closest_smaller_resolution(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the preset of the closest smaller resolution when the game has none for the one in use, and says so.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(_SETUP, resolution="2560x1600")
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert view.settings is not None and view.settings.index == 3
        assert view.status == "No preset for 2560x1600: showing the one for 2560x1440."
        assert view.status_level is StatusLevel.WARNING

    def test_smallest_when_all_larger(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the preset of the smallest resolution when every one of the game is larger than the one in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.return_value = replace(_PRESETS, resolutions=_PRESETS.resolutions[1:])
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert view.settings is not None and view.settings.index == 3
        assert view.status == "No preset for 1920x1080: showing the one for 2560x1440."

    def test_below_min_spec_noted(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Warns that the hardware is too weak for the resolution in use.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.open_resolution_choice()
        # Act
        presenter.choose_resolution(position=1)
        # Assert
        assert view.settings is not None and view.settings.index == 1
        assert view.status == "Too demanding for this PC: even the lowest settings may stutter at this resolution."
        assert view.status_level is StatusLevel.WARNING

    def test_same_resolution(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Saves and requests nothing when the resolution in use is picked again.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.open_resolution_choice()
        service.game_settings.reset_mock()
        # Act
        presenter.choose_resolution(position=0)
        # Assert
        service.save_resolution.assert_not_called()
        service.game_settings.assert_not_called()

    def test_chosen_without_game(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner
    ) -> None:
        """
        Saves and shows a resolution picked before any game is chosen, requesting nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        finder.deferred = True
        presenter.start()
        presenter.open_resolution_choice()
        # Act
        presenter.choose_resolution(position=1)
        # Assert
        service.save_resolution.assert_called_once_with(resolution="3840x2160")
        assert view.hardware is not None and view.hardware.resolution == "3840x2160"
        service.game_settings.assert_not_called()

    @pytest.mark.parametrize(argnames="fails", argvalues=[False, True], ids=["answer", "error"])
    def test_stale_settings_dropped(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, runner: _Runner, fails: bool
    ) -> None:
        """
        Drops the settings, or the error, of a resolution the user left before they arrived.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param runner: runner
        :param fails: True when the requests fail
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        if fails:
            service.game_settings.side_effect = ConnectionError("timeout")
        presenter.open_resolution_choice()
        runner.deferred = True
        presenter.choose_resolution(position=1)
        presenter.choose_resolution(position=2)
        # Act
        runner.run_all()
        # Assert
        if fails:
            assert (view.settings, view.status) == (None, "Could not get data from NVIDIA: timeout")
        else:
            assert view.settings is not None and (view.settings.index, view.status) == (3, "")


class TestLanguage(_PresenterTests):
    """Tests of Presenter.change_language."""

    def test_switch(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Saves the language and re-renders every text shown: setting names and values, the status note.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(_SETUP, resolution="2560x1600")
        self.show_settings(presenter=presenter)
        # Act
        presenter.change_language(language="ru")
        # Assert
        service.save_language.assert_called_once_with(language="ru")
        assert (presenter.language, view.language, view.status) == (
            "ru",
            "ru",
            "Нет пресета для 2560x1600: показан пресет для 2560x1440.",
        )
        assert view.settings is not None
        assert (view.settings.rows, view.settings.caption) == (
            (
                SettingRow(name="Тени", value="Высокое", changed=False),
                SettingRow(name="Масштаб", value="1.000", changed=False),
            ),
            "оптимальный пресет",
        )

    def test_same_language(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Does nothing when the language doesn't change.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_language(language="en")
        # Assert
        service.save_language.assert_not_called()


class TestSearch(_PresenterTests):
    """Tests of Presenter.search_games."""

    def test_filtered_ignoring_case(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Shows only the games whose name contains the text, ignoring case.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.search_games(text=" mord ")
        # Assert
        assert (view.games, view.game_selected) == (["MORDHAU"], None)

    def test_filter_waits_for_the_typing_to_rest(
        self, presenter: Presenter, view: _FakeView, debouncer: _Debouncer
    ) -> None:
        """
        Filters the list by the text typed last only.

        :param presenter: presenter under test
        :param view: fake window
        :param debouncer: debouncer
        :return: None
        """
        # Arrange
        presenter.start()
        debouncer.held = True
        # Act
        presenter.search_games(text="m")
        presenter.search_games(text="mo")
        typing: list[str] = list(view.games)
        debouncer.fire()
        # Assert
        assert (typing, view.games) == (["Baldur's Gate 3", "MORDHAU"], ["MORDHAU"])

    def test_select_in_filtered_list(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Takes a position in the filtered list as the game shown there.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.search_games(text="MORD")
        # Act
        presenter.select_game(index=0)
        # Assert
        assert service.game_presets.call_args.kwargs["game_id"] == "mordhau"

    def test_chosen_game_kept(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Keeps the chosen game selected when the search is cleared, without requesting its presets again.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.search_games(text="mord")
        service.game_presets.reset_mock()
        # Act
        presenter.search_games(text="")
        presenter.select_game(index=1)
        # Assert
        assert (view.games, view.game_selected) == (["Baldur's Gate 3", "MORDHAU"], 1)
        service.game_presets.assert_not_called()
        assert view.settings is not None


class TestTheme(_PresenterTests):
    """Tests of Presenter.change_theme."""

    def test_switch(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Applies and saves the chosen theme.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_theme(mode=ThemeMode.DARK)
        # Assert
        assert view.theme is ThemeMode.DARK
        service.save_theme.assert_called_once_with(theme=ThemeMode.DARK)

    def test_same_theme(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Does nothing when the theme doesn't change.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_theme(mode=ThemeMode.AUTO)
        # Assert
        service.save_theme.assert_not_called()


class TestAutoUpdate(_PresenterTests):
    """Tests of Presenter.change_auto_update."""

    def test_switched_off(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Saves the switch; switching off runs no update.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_auto_update(enabled=False)
        # Assert
        service.save_auto_update.assert_called_once_with(enabled=False)
        assert service.update_database_if_due.call_count == 1

    def test_switched_on_updates(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Saves the switch and runs an update when switched on.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.change_auto_update(enabled=False)
        # Act
        presenter.change_auto_update(enabled=True)
        # Assert
        service.save_auto_update.assert_called_with(enabled=True)
        assert service.update_database_if_due.call_count == 2

    def test_same_state(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Does nothing when the switch doesn't change.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_auto_update(enabled=True)
        # Assert
        service.save_auto_update.assert_not_called()
        assert service.update_database_if_due.call_count == 1


class TestDatabaseUpdate(_PresenterTests):
    """Tests of the database update run at the start."""

    _RENAMED: tuple[Game, ...] = (
        Game(game_id="baldurs_gate_3", name="Baldur's Gate III"),
        Game(game_id="mordhau", name="Mordhau II"),
    )
    _RENAMED_INSTALLED: tuple[InstalledGame, ...] = (InstalledGame(game=_RENAMED[0], executable=_BG3_EXE),)

    @pytest.mark.parametrize(
        argnames="result",
        argvalues=[DatabaseUpdate.SKIPPED, DatabaseUpdate.UNCHANGED],
        ids=["skipped", "unchanged"],
    )
    def test_nothing_refreshed(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, result: DatabaseUpdate
    ) -> None:
        """
        Keeps the games and lists shown when the database didn't change.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param result: outcome of the update
        :return: None
        """
        # Arrange
        service.update_database_if_due.return_value = result
        # Act
        presenter.start()
        # Assert
        assert (service.games.call_count, service.find_games.call_count) == (1, 1)
        assert (service.hardware_setup.call_count, view.games) == (1, ["Baldur's Gate 3", "MORDHAU"])

    def test_games_and_lists_refreshed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the games of a new database and searches again, keeping the chosen game, and offers its CPU list.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.games.side_effect = [_GAMES, self._RENAMED]
        service.find_games.side_effect = [_INSTALLED, self._RENAMED_INSTALLED]
        service.hardware_setup.side_effect = [_SETUP, replace(_SETUP, amd_cpus=(_AMD_CPU,))]
        self.show_settings(presenter=presenter)
        service.update_database_if_due.return_value = DatabaseUpdate.UPDATED
        presenter.change_auto_update(enabled=False)
        # Act
        presenter.change_auto_update(enabled=True)
        presenter.open_cpu_choice()
        # Assert
        assert (view.games, view.game_selected) == (["Baldur's Gate III", "Mordhau II"], 1)
        assert [game.name for game in view.installed] == ["Baldur's Gate III"]
        assert view.settings is not None
        assert view.cpu_offers[0].groups[0].items == (_AMD_CPU,)
        assert view.hardware == _LAPTOP_VIEW

    def test_chosen_game_gone(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Chooses the first game when the new database doesn't list the chosen one any more.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.games.side_effect = [_GAMES, self._RENAMED[:1]]
        self.show_settings(presenter=presenter)
        service.update_database_if_due.return_value = DatabaseUpdate.UPDATED
        presenter.change_auto_update(enabled=False)
        # Act
        presenter.change_auto_update(enabled=True)
        # Assert
        assert (view.games, view.game_selected) == (["Baldur's Gate III"], 0)
        assert view.settings is not None and view.settings.title == "Baldur's Gate III"
        assert service.save_game_choice.call_args.kwargs["choice"].catalog_game_id == "baldurs_gate_3"

    def test_once_per_start(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Runs the update after the first hardware answer only, not after later hardware choices.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        service.choose_hardware.return_value = _Hardware.ready(gpu=_DESKTOP_GPU)
        # Act
        presenter.choose_gpu(position=1)
        # Assert
        assert service.update_database_if_due.call_count == 1

    @pytest.mark.parametrize(argnames="failure", argvalues=["setup", "check"], ids=["setup fails", "check fails"])
    def test_after_hardware_failure(self, presenter: Presenter, service: MagicMock, failure: str) -> None:
        """
        Runs the update also when the hardware detection or its check fails.

        :param presenter: presenter under test
        :param service: service mock
        :param failure: which call fails
        :return: None
        """
        # Arrange
        if failure == "setup":
            service.hardware_setup.side_effect = OSError("no registry")
        else:
            service.check_hardware.side_effect = ConnectionError("timeout")
        # Act
        presenter.start()
        # Assert
        service.update_database_if_due.assert_called_once_with()

    def test_failed_update(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Changes nothing shown when the update fails.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.update_database_if_due.side_effect = ConnectionError("offline")
        # Act
        presenter.start()
        # Assert
        assert (view.games, view.status) == (["Baldur's Gate 3", "MORDHAU"], "")

    def test_refresh_without_setup(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the new games but asks for no lists when the hardware detection failed.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.side_effect = OSError("no registry")
        service.update_database_if_due.return_value = DatabaseUpdate.UPDATED
        service.games.side_effect = [_GAMES, self._RENAMED]
        # Act
        presenter.start()
        # Assert
        assert (service.hardware_setup.call_count, view.games) == (1, ["Baldur's Gate III", "Mordhau II"])


class TestHardwareChoice(_PresenterTests):
    """Tests of Presenter.open_cpu_choice, open_gpu_choice, choose_cpu and choose_gpu."""

    def test_gpus_offered(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Offers the detected GPUs above the bundled ones, the one in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.open_gpu_choice()
        # Assert
        assert view.gpu_offers == [
            ChoiceView(
                detected=("NVIDIA GeForce RTX 4060 Laptop GPU",),
                groups=(ChoiceGroup(title="", items=("NVIDIA GeForce RTX 4090",)),),
                selected=0,
            )
        ]

    def test_cpus_offered(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Offers the detected CPU above vendor tabs of the bundled ones, the one in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(
            _SETUP,
            amd_cpus=(_AMD_CPU,),
            intel_cpus=(_INTEL_CPU,),
            choice=HardwareChoice(cpu_name=_INTEL_CPU, gpu=_LAPTOP_GPU),
        )
        presenter.start()
        # Act
        presenter.open_cpu_choice()
        # Assert
        assert view.cpu_offers == [
            ChoiceView(
                detected=(_CPU,),
                groups=(ChoiceGroup(title="AMD", items=(_AMD_CPU,)), ChoiceGroup(title="Intel", items=(_INTEL_CPU,))),
                selected=2,
            )
        ]

    def test_no_bundled_cpus(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Offers only the detected CPU while there is no bundled CPU list.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.open_cpu_choice()
        # Assert
        assert view.cpu_offers == [ChoiceView(detected=(_CPU,), groups=(), selected=0)]

    def test_nothing_offered_before_detection(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Offers nothing while the hardware is not detected yet.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        runner.deferred = True
        presenter.start()
        # Act
        presenter.open_cpu_choice()
        presenter.open_gpu_choice()
        # Assert
        assert (view.cpu_offers, view.gpu_offers) == ([], [])

    def test_new_gpu_reloads_presets(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Uses the GPU NVIDIA accepts and requests the presets of the game shown again for it, at once.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.choose_hardware.return_value = _Hardware.ready(gpu=_DESKTOP_GPU)
        self.show_settings(presenter=presenter)
        # Act
        presenter.choose_gpu(position=1)
        # Assert
        service.choose_hardware.assert_called_once_with(choice=HardwareChoice(cpu_name=_CPU, gpu=_DESKTOP_GPU))
        last_call: Any = service.game_presets.call_args
        assert last_call.kwargs == {"game_id": "mordhau", "hardware": _Hardware.with_gpu(gpu=_DESKTOP_GPU)}
        assert view.hardware == HardwareView(
            cpu=_CPU, gpu="NVIDIA GeForce RTX 4090", resolution=_SCREEN, memory="16 GB", video_memory="unknown"
        )
        assert view.settings == _SHOWN

    def test_new_cpu_accepted(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Uses a chosen CPU NVIDIA accepts, clearing the hardware problem shown before.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(_SETUP, amd_cpus=(_AMD_CPU,))
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("cpu",))
        service.choose_hardware.return_value = _Hardware.ready(gpu=_LAPTOP_GPU, cpu_name=_AMD_CPU)
        presenter.start()
        # Act
        presenter.choose_cpu(position=1)
        presenter.select_game(index=1)
        # Assert
        assert (view.hardware is not None and view.hardware.cpu, view.status) == (_AMD_CPU, "")
        assert service.game_presets.call_args.kwargs["hardware"] == _Hardware.with_gpu(
            gpu=_LAPTOP_GPU, cpu_name=_AMD_CPU
        )

    def test_same_gpu(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Asks NVIDIA nothing when the GPU in use is picked again.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.choose_gpu(position=0)
        # Assert
        service.choose_hardware.assert_not_called()

    def test_rejected_gpu(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the GPU picked with the reason NVIDIA rejects it, and stops using the hardware.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.choose_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("gpu",))
        self.start(presenter=presenter, service=service)
        # Act
        presenter.choose_gpu(position=1)
        presenter.select_game(index=1)
        # Assert
        assert view.hardware is not None and view.hardware.gpu == "NVIDIA GeForce RTX 4090"
        assert view.status == "NVIDIA does not know your graphics card. Choose the closest one from the list."
        assert view.status_level is StatusLevel.ERROR
        service.game_presets.assert_not_called()

    def test_check_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed check of a new GPU and goes back to the hardware in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.choose_hardware.side_effect = ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.choose_gpu(position=1)
        # Assert
        assert (view.hardware, view.status) == (_LAPTOP_VIEW, "Could not get data from NVIDIA: timeout")
        assert view.status_level is StatusLevel.ERROR


class TestInstalledGames(_PresenterTests):
    """Tests of the search for installed games, Presenter.find_games and select_installed_game."""

    def test_found_at_start(self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner) -> None:
        """
        Shows the skeleton, then the folders and the games found in them with their executables.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        finder.deferred = True
        presenter.start()
        searching: tuple[bool, list[str]] = (view.finding, view.folders)
        # Act
        finder.run_all()
        # Assert
        assert searching == (True, list(_FOLDERS))
        assert (view.finding, view.installed, view.installed_selected) == (
            False,
            [InstalledGameView(name="Baldur's Gate 3", executable=_BG3_EXE)],
            0,
        )
        service.find_games.assert_called_once_with(folders=_FOLDERS)

    def test_folders_unreadable(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Searches without folders when the saved ones can't be read.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_folders.side_effect = OSError("locked")
        # Act
        presenter.start()
        # Assert
        assert view.folders == []
        service.find_games.assert_called_once_with(folders=())

    def test_search_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed search and shows no installed games.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.side_effect = OSError("denied")
        # Act
        presenter.start()
        # Assert
        assert (view.status, view.installed, view.finding) == ("Could not search for games: denied", [], False)

    def test_asked_again_while_searching(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, finder: _Runner
    ) -> None:
        """
        Searches once more after the running search when asked during it, showing only the last result.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param finder: runner of the search for installed games
        :return: None
        """
        # Arrange
        service.find_games.side_effect = [(), _INSTALLED]
        finder.deferred = True
        presenter.start()
        presenter.find_games()
        presenter.find_games()
        # Act
        finder.run_all()
        # Assert
        assert service.find_games.call_count == 2
        assert [game.name for game in view.installed] == ["Baldur's Gate 3"]

    def test_installed_game_chosen(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the settings of an installed game chosen in the installed games tab.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.return_value = (*_INSTALLED, InstalledGame(game=_GAMES[1], executable=_BG3_EXE))
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        presenter.start()
        # Act
        presenter.select_installed_game(index=1)
        # Assert
        assert service.game_presets.call_args.kwargs["game_id"] == "mordhau"
        assert view.settings is not None and view.settings.title == "MORDHAU"

    def test_game_per_tab(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Keeps a game of its own in each tab and shows the one of the tab in use.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.select_game(index=1)
        # Act
        presenter.select_tab(tab=GamesTab.INSTALLED)
        installed: str | None = None if view.settings is None else view.settings.title
        presenter.select_tab(tab=GamesTab.ALL)
        # Assert
        assert (installed, view.settings) == ("Baldur's Gate 3", _SHOWN)

    def test_choice_kept_after_search(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Keeps the chosen game selected among the installed games found by a new search.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.select_game(index=0)
        # Act
        presenter.find_games()
        # Assert
        assert (view.installed_selected, service.find_games.call_count) == (0, 2)


class TestGameChoice(_PresenterTests):
    """Tests of the saved game tab and the game chosen in each tab."""

    def test_first_games_saved(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Chooses and saves the first game of each list when nothing is saved, showing the installed one.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.saved_game_choice.return_value = GameChoice()
        # Act
        presenter.start()
        # Assert
        assert view.tab is GamesTab.INSTALLED
        assert (view.game_selected, view.installed_selected) == (0, 0)
        assert view.settings is not None and view.settings.title == "Baldur's Gate 3"
        service.save_game_choice.assert_called_with(
            choice=GameChoice(
                tab=GamesTab.INSTALLED, installed_game_id="baldurs_gate_3", catalog_game_id="baldurs_gate_3"
            )
        )

    def test_saved_games_restored(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Starts in the saved tab with the saved games selected, saving nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.saved_game_choice.return_value = GameChoice(
            tab=GamesTab.ALL, installed_game_id="baldurs_gate_3", catalog_game_id="mordhau"
        )
        # Act
        presenter.start()
        # Assert
        assert (view.tab, view.game_selected, view.installed_selected, view.settings) == (GamesTab.ALL, 1, 0, _SHOWN)
        service.save_game_choice.assert_not_called()

    def test_changes_saved(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Saves the tab and the games as the user changes them.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        service.save_game_choice.reset_mock()
        # Act
        presenter.select_game(index=1)
        presenter.select_tab(tab=GamesTab.INSTALLED)
        presenter.select_installed_game(index=0)
        # Assert
        assert [call.kwargs["choice"] for call in service.save_game_choice.call_args_list] == [
            GameChoice(tab=GamesTab.ALL, installed_game_id="baldurs_gate_3", catalog_game_id="mordhau"),
            GameChoice(tab=GamesTab.INSTALLED, installed_game_id="baldurs_gate_3", catalog_game_id="mordhau"),
        ]

    def test_no_installed_games(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows no game in the installed games tab when none is found, keeping the saved one for a later search.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.return_value = ()
        service.saved_game_choice.return_value = GameChoice(
            tab=GamesTab.INSTALLED, installed_game_id="mordhau", catalog_game_id="baldurs_gate_3"
        )
        # Act
        presenter.start()
        # Assert
        assert (view.cover, view.settings, view.settings_loading, view.status) == ("empty", None, False, "")
        service.game_presets.assert_not_called()
        service.save_game_choice.assert_not_called()

    def test_installed_games_gone(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Clears the game shown in the installed games tab when a new search finds no games.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.side_effect = [_INSTALLED, ()]
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        presenter.start()
        # Act
        presenter.find_games()
        # Assert
        assert (view.cover, view.settings, view.settings_loading, view.status) == ("empty", None, False, "")
        assert service.save_game_choice.call_args.kwargs["choice"].installed_game_id == "baldurs_gate_3"

    def test_installed_game_gone(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Moves to the first installed game when the chosen one is no longer found, showing it in its tab.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.side_effect = [(InstalledGame(game=_GAMES[1], executable=_BG3_EXE),), _INSTALLED]
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED, installed_game_id="mordhau")
        presenter.start()
        # Act
        presenter.find_games()
        # Assert
        assert view.installed_selected == 0
        assert view.settings is not None and view.settings.title == "Baldur's Gate 3"
        assert service.save_game_choice.call_args.kwargs["choice"].installed_game_id == "baldurs_gate_3"


class TestFolders(_PresenterTests):
    """Tests of Presenter.add_folder, change_folder and remove_folder."""

    def test_added(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Adds a picked folder in Windows form at the end, saves the list and searches again.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.add_folder(folder="E:/SteamLibrary")
        # Assert
        expected: tuple[str, ...] = (*_FOLDERS, "E:\\SteamLibrary")
        assert view.folders == list(expected)
        service.save_game_folders.assert_called_once_with(folders=expected)
        assert service.find_games.call_args.kwargs == {"folders": expected}

    @pytest.mark.parametrize(argnames="folder", argvalues=["d:/games", ""], ids=["listed already", "nothing picked"])
    def test_not_added(self, presenter: Presenter, view: _FakeView, service: MagicMock, folder: str) -> None:
        """
        Changes nothing for a folder listed already, in any case, or for an empty pick.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param folder: folder picked
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.add_folder(folder=folder)
        # Assert
        assert view.folders == list(_FOLDERS)
        service.save_game_folders.assert_not_called()
        assert service.find_games.call_count == 1

    @pytest.mark.parametrize(
        argnames=("position", "folder", "expected"),
        argvalues=[
            (1, "E:/Games", ("C:\\Program Files", "E:\\Games")),
            (1, "d:/games", ("C:\\Program Files", "d:\\games")),
            (1, "D:/Games", _FOLDERS),
            (0, "D:/Games", _FOLDERS),
            (2, "E:/Games", _FOLDERS),
            (-1, "E:/Games", _FOLDERS),
        ],
        ids=[
            "replaced",
            "same folder in other case",
            "same folder",
            "another listed folder",
            "after the end",
            "negative",
        ],
    )
    def test_changed(  # pylint: disable=too-many-arguments
        self,
        presenter: Presenter,
        view: _FakeView,
        service: MagicMock,
        position: int,
        folder: str,
        expected: tuple[str, ...],
    ) -> None:
        """
        Puts a picked folder in place of a listed one unless another position lists it; a bad position does nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param position: position of the folder replaced
        :param folder: folder picked
        :param expected: folders afterward
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.change_folder(position=position, folder=folder)
        # Assert
        assert view.folders == list(expected)
        assert service.save_game_folders.call_count == int(expected != _FOLDERS)

    @pytest.mark.parametrize(
        argnames=("position", "expected"),
        argvalues=[(0, ("D:\\Games",)), (2, _FOLDERS), (-1, _FOLDERS)],
        ids=["removed", "after the end", "negative"],
    )
    def test_removed(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, position: int, expected: tuple[str, ...]
    ) -> None:
        """
        Removes a listed folder, saves the list and searches again; a bad position does nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param position: position of the folder removed
        :param expected: folders afterward
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.remove_folder(position=position)
        # Assert
        assert view.folders == list(expected)
        assert service.find_games.call_count == 1 + int(expected != _FOLDERS)


class TestCover(_PresenterTests):
    """Tests of the box art of the chosen game."""

    def test_shown(self, presenter: Presenter, view: _FakeView, service: MagicMock, debouncer: _Debouncer) -> None:
        """
        Shows the cover skeleton while the choice rests, then the picture.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param debouncer: debouncer
        :return: None
        """
        # Arrange
        debouncer.held = True
        presenter.start()
        waiting: str = view.cover
        # Act
        debouncer.fire()
        # Assert
        assert (waiting, view.cover, view.picture) == ("loading", "picture", _COVER)
        service.cover.assert_called_once_with(game=_GAMES[0])

    def test_no_box_art(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the placeholder at once for a game without box art.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.start(presenter=presenter, service=service)
        # Act
        presenter.select_game(index=1)
        # Assert
        assert (view.cover, view.picture) == ("picture", None)
        service.cover.assert_not_called()

    def test_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the placeholder when the picture can't be had.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.cover.side_effect = ConnectionError("offline")
        presenter.start()
        # Act
        presenter.select_game(index=0)
        # Assert
        assert (view.cover, view.picture) == ("picture", None)

    def test_stale_dropped(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Drops the picture of a game the user left before it arrived.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        presenter.start()
        runner.deferred = True
        presenter.select_game(index=0)
        presenter.select_game(index=1)
        # Act
        runner.run_all()
        # Assert
        assert (view.cover, view.picture) == ("picture", None)


class TestSettingsSkeleton(_PresenterTests):
    """Tests of the settings skeleton: moving while settings are requested, still otherwise."""

    def test_loading(self, presenter: Presenter, view: _FakeView, runner: _Runner) -> None:
        """
        Moves the skeleton while the settings of a chosen game are requested.

        :param presenter: presenter under test
        :param view: fake window
        :param runner: runner
        :return: None
        """
        # Arrange
        presenter.start()
        runner.deferred = True
        # Act
        presenter.select_game(index=1)
        # Assert
        assert (view.settings, view.settings_loading) == (None, True)

    @pytest.mark.parametrize(
        argnames="case",
        argvalues=["no hardware", "no recommendation", "failed"],
        ids=["no hardware", "no recommendation", "failed"],
    )
    def test_still(self, presenter: Presenter, view: _FakeView, service: MagicMock, case: str) -> None:
        """
        Stops the skeleton when no settings are coming: no hardware, no recommendation or a failed request.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param case: why no settings come
        :return: None
        """
        # Arrange
        if case == "no hardware":
            service.check_hardware.return_value = HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        elif case == "no recommendation":
            service.game_presets.return_value = replace(_PRESETS, resolutions=())
        else:
            service.game_settings.side_effect = ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.select_game(index=1)
        # Assert
        assert (view.settings, view.settings_loading) == (None, False)
