"""Fakes and samples shared by the presenter tests: a window, runners, a debouncer and the data shown."""

from pathlib import Path
from typing import Callable, Sequence
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
from app.ui.presenter import Presenter
from app.ui.views import ChoiceView, HardwareView, InstalledGameView, SettingRow, SettingsView, StatusLevel
from app.ui.worker import Runners

__all__: tuple[str, ...] = (
    "AMD_CPU",
    "BG3_EXE",
    "BUNDLED_RESOLUTIONS",
    "COVER",
    "CPU",
    "DESKTOP_GPU",
    "FIT_HINT",
    "FOLDERS",
    "FakeDebouncer",
    "FakeHardware",
    "FakeRunner",
    "FakeView",
    "GAMES",
    "INSTALLED",
    "INTEL_CPU",
    "LAPTOP_GPU",
    "LAPTOP_VIEW",
    "PRESETS",
    "PRESETS_FILE",
    "PresenterTests",
    "SCREEN",
    "SETTINGS",
    "SETUP",
    "SHOWN",
)

LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0", memory_gb=8.0)
DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
CPU: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
AMD_CPU: str = "AMD Ryzen 7 7800X3D 8-Core Processor"
INTEL_CPU: str = "Intel(R) Core(TM) i7-14700K"
SCREEN: str = "1920x1080"
BUNDLED_RESOLUTIONS: tuple[str, ...] = ("3840x2160", "2560x1600", "2560x1440")
FIT_HINT: str = "Same shape as your screen (16:9): fills it with no black bars or stretching."
# A laptop with its GPU and screen detected, the RTX 4090 in the bundled list and no bundled CPUs.
SETUP: HardwareSetup = HardwareSetup(
    system=SystemHardware(cpu_name=CPU, gpus=(LAPTOP_GPU,), memory_gb=16, os_version="10.0", resolution=SCREEN),
    amd_cpus=(),
    intel_cpus=(),
    gpus=(DESKTOP_GPU,),
    resolutions=BUNDLED_RESOLUTIONS,
    choice=HardwareChoice(cpu_name=CPU, gpu=LAPTOP_GPU),
    resolution=SCREEN,
)
LAPTOP_VIEW: HardwareView = HardwareView(
    cpu=CPU, gpu="NVIDIA GeForce RTX 4060 Laptop GPU", resolution=SCREEN, memory="16 GB", video_memory="8 GB"
)
GAMES: tuple[Game, ...] = (
    Game(game_id="baldurs_gate_3", name="Baldur's Gate 3", cover_url="https://img.example.test/bg3.jpg"),
    Game(game_id="mordhau", name="MORDHAU"),
)
FOLDERS: tuple[str, ...] = ("C:\\Program Files", "D:\\Games")
BG3_EXE: Path = Path("D:/Games/Baldurs Gate 3/bin/bg3.exe")
INSTALLED: tuple[InstalledGame, ...] = (InstalledGame(game=GAMES[0], executable=BG3_EXE),)
COVER: Path = Path("cover.jpg")
PRESETS_FILE: RemoteFile = RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1)
# No preset for 2560x1600: the one of 2560x1440 stands in; 4K is too much for the hardware.
PRESETS: GamePresets = GamePresets(
    profile="regular",
    version="1",
    presets_file=PRESETS_FILE,
    resolutions=(
        ResolutionPreset(resolution="1920x1080", preset_index=2, rate=40, below_min_spec=False),
        ResolutionPreset(resolution="3840x2160", preset_index=1, rate=40, below_min_spec=True),
        ResolutionPreset(resolution="2560x1440", preset_index=3, rate=35, below_min_spec=False),
    ),
)
SETTINGS: GameSettings = GameSettings(
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
SHOWN: SettingsView = SettingsView(
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


class FakeHardware:
    """Hardware the service mock reports."""

    @staticmethod
    def with_gpu(*, gpu: Gpu, cpu_name: str = CPU) -> Hardware:
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
    def ready(cls, *, gpu: Gpu, cpu_name: str = CPU) -> HardwareCheck:
        """
        Build a READY check result.

        :param gpu: the GPU in use
        :param cpu_name: the CPU in use
        :return: check result
        """
        return HardwareCheck(state=HardwareState.READY, hardware=cls.with_gpu(gpu=gpu, cpu_name=cpu_name))


class FakeView:  # pylint: disable=too-many-instance-attributes
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
        self.no_recommendation: bool = False
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
        self.no_recommendation = False

    def clear_settings(self, *, loading: bool) -> None:
        """
        Record that no settings are shown.

        :param loading: whether settings are requested
        :return: None
        """
        self.settings = None
        self.settings_loading = loading
        self.no_recommendation = False

    def show_no_recommendation(self) -> None:
        """
        Record the notice that there is no recommendation.

        :return: None
        """
        self.settings = None
        self.settings_loading = False
        self.no_recommendation = True


class FakeRunner:
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


class FakeDebouncer:
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


class PresenterTests:
    """Fixtures of the presenter tests: a started presenter over a mocked service with the laptop GPU ready."""

    @pytest.fixture(name="view")
    def _view(self) -> FakeView:
        """
        Create the fake window.

        :return: fake window
        """
        return FakeView()

    @pytest.fixture(name="runner")
    def _runner(self) -> FakeRunner:
        """
        Create the runner.

        :return: runner running tasks at once
        """
        return FakeRunner()

    @pytest.fixture(name="finder")
    def _finder(self) -> FakeRunner:
        """
        Create the runner of the search for installed games.

        :return: runner running tasks at once
        """
        return FakeRunner()

    @pytest.fixture(name="debouncer")
    def _debouncer(self) -> FakeDebouncer:
        """
        Create the debouncer.

        :return: debouncer running actions at once
        """
        return FakeDebouncer()

    @pytest.fixture(name="service")
    def _service(self) -> MagicMock:
        """
        Mock the service: two games, one installed, the all games tab saved, the laptop accepted, presets and box art.

        :return: mock with the interface of PresetService
        """
        service: MagicMock = create_autospec(spec=PresetService, instance=True)
        service.games.return_value = GAMES
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.ALL)
        service.hardware_setup.return_value = SETUP
        service.check_hardware.return_value = FakeHardware.ready(gpu=LAPTOP_GPU)
        service.game_presets.return_value = PRESETS
        service.game_settings.return_value = SETTINGS
        service.update_database_if_due.return_value = DatabaseUpdate.SKIPPED
        service.game_folders.return_value = FOLDERS
        service.find_games.return_value = INSTALLED
        service.cover.return_value = COVER
        return service

    @pytest.fixture(name="updater")
    def _updater(self, runner: FakeRunner) -> FakeRunner:
        """
        Run the database update in the runner of the requests, unless a test class gives it a runner of its own.

        :param runner: runner of the requests
        :return: runner of the database update
        """
        return runner

    @pytest.fixture(name="saver")
    def _saver(self, runner: FakeRunner) -> FakeRunner:
        """
        Run the settings saves in the runner of the requests, unless a test class gives them a runner of their own.

        :param runner: runner of the requests
        :return: runner of the settings saves
        """
        return runner

    @pytest.fixture(name="presenter")
    def _presenter(  # pylint: disable=too-many-arguments
        self,
        view: FakeView,
        service: MagicMock,
        debouncer: FakeDebouncer,
        locale_dir: Path,
        runners: Runners,
    ) -> Presenter:
        """
        Create the presenter in English with automatic database updates on; tests start it themselves.

        :param view: fake window
        :param service: service mock
        :param debouncer: debouncer
        :param locale_dir: compiled catalogs
        :param runners: the runners
        :return: presenter under test
        """
        return Presenter(
            view=view,
            service=service,
            runners=runners,
            debouncer=debouncer,
            translator=Translator(language="en", locale_dir=locale_dir),
            theme=ThemeMode.AUTO,
            auto_update=True,
            locale_dir=locale_dir,
        )

    @pytest.fixture(name="runners")
    def _runners(self, runner: FakeRunner, finder: FakeRunner, updater: FakeRunner, saver: FakeRunner) -> Runners:
        """
        Group the runners the presenter gets.

        :param runner: runner of the requests
        :param finder: runner of the search for installed games
        :param updater: runner of the database update
        :param saver: runner of the settings saves
        :return: the runners
        """
        return Runners(requests=runner, finder=finder, updater=updater, saver=saver)

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
        presenter.games.select_game(index=1)
