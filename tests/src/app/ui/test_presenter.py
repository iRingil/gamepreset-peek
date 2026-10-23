"""Tests of the main window logic on a fake window, a runner that runs tasks in place and a debouncer run by hand."""

# pylint: disable=too-many-lines

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Sequence
from unittest.mock import MagicMock, create_autospec

import pytest

from app.core.models import (
    Game,
    GamePresets,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
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
from app.ui.presenter import ChoiceGroup, ChoiceView, HardwareView, Presenter, SettingRow, SettingsView

__all__: tuple = ()

_LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0", memory_gb=8.0)
_DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
_CPU: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
_AMD_CPU: str = "AMD Ryzen 7 7800X3D 8-Core Processor"
_INTEL_CPU: str = "Intel(R) Core(TM) i7-14700K"
_SCREEN: str = "1920x1080"
_BUNDLED_RESOLUTIONS: tuple[str, ...] = ("3840x2160", "2560x1600", "2560x1440")
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
    Game(game_id="baldurs_gate_3", name="Baldur's Gate 3"),
    Game(game_id="mordhau", name="MORDHAU"),
)
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
        self.themes: tuple[list[str], int] | None = None
        self.hardware: HardwareView | None = None
        self.status: str = ""
        self.load_games: bool = False
        self.games: list[str] = []
        self.game_selected: int | None = None
        self.settings: SettingsView | None = None
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

    def show_themes(self, *, names: Sequence[str], selected: int) -> None:
        """
        Record the theme choice.

        :param names: theme names
        :param selected: position of the theme in use
        :return: None
        """
        self.themes = (list(names), selected)

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

    def show_status(self, *, text: str) -> None:
        """
        Record the status line.

        :param text: the line
        :return: None
        """
        self.status = text

    def warn(self, *, text: str) -> None:
        """
        Record a warning dialog.

        :param text: the warning
        :return: None
        """
        self.warnings.append(text)

    def show_load_games(self, *, visible: bool) -> None:
        """
        Record the "Load games" button state.

        :param visible: whether it is shown
        :return: None
        """
        self.load_games = visible

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Record the game list.

        :param names: game names
        :param selected: position of the chosen game
        :return: None
        """
        self.games = list(names)
        self.game_selected = selected

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Record the settings shown.

        :param settings: what is shown
        :return: None
        """
        self.settings = settings

    def clear_settings(self) -> None:
        """
        Record that no settings are shown.

        :return: None
        """
        self.settings = None


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
        Mock the service: two games, the laptop accepted, presets and settings of any game.

        :return: mock with the interface of PresetService
        """
        service: MagicMock = create_autospec(spec=PresetService, instance=True)
        service.games.return_value = _GAMES
        service.hardware_setup.return_value = _SETUP
        service.check_hardware.return_value = _Hardware.ready(gpu=_LAPTOP_GPU)
        service.game_presets.return_value = _PRESETS
        service.game_settings.return_value = _SETTINGS
        return service

    @pytest.fixture(name="presenter")
    def _presenter(
        self, view: _FakeView, runner: _Runner, debouncer: _Debouncer, service: MagicMock, locale_dir: Path
    ) -> Presenter:
        """
        Create the presenter in English; tests start it themselves.

        :param view: fake window
        :param runner: runner
        :param debouncer: debouncer
        :param service: service mock
        :param locale_dir: compiled catalogs
        :return: presenter under test
        """
        return Presenter(
            view=view,
            service=service,
            runner=runner,
            debouncer=debouncer,
            translator=Translator(language="en", locale_dir=locale_dir),
            theme=ThemeMode.AUTO,
            locale_dir=locale_dir,
        )

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
    """Tests of Presenter.start, load_games and the hardware flow."""

    def test_games_and_hardware(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the games and the detected hardware, in the initial language, checks the hardware, warns of nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange & Act
        presenter.start()
        # Assert
        assert (view.theme, view.themes) == (ThemeMode.AUTO, (["Auto", "Light", "Dark"], 0))
        assert (view.language, view.games, view.hardware, view.status, view.load_games) == (
            "en",
            ["Baldur's Gate 3", "MORDHAU"],
            _LAPTOP_VIEW,
            "",
            False,
        )
        service.check_hardware.assert_called_once_with(choice=HardwareChoice(cpu_name=_CPU, gpu=_LAPTOP_GPU))
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

    def test_games_failed_then_reloaded(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed game list with the "Load games" button, which requests it again.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.games.side_effect = [ConnectionError("down"), _GAMES]
        presenter.start()
        failed: tuple[str, bool] = (view.status, view.load_games)
        # Act
        presenter.load_games()
        # Assert
        assert failed == ("Could not load the game list: down", True)
        assert (view.games, view.status, view.load_games) == (["Baldur's Gate 3", "MORDHAU"], "", False)

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

    def test_problem_outlives_game_list(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Keeps the hardware problem in the status line when the game list arrives after it.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("gpu",))
        service.games.side_effect = [ConnectionError("down"), _GAMES]
        presenter.start()
        # Act
        presenter.load_games()
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
        presenter.select_game(index=0)
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
        presenter.start()
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
        presenter.start()
        debouncer.held = True
        # Act
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
        presenter.start()
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
        assert (view.settings, view.status) == (None, "No recommendations")
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
        presenter.select_game(index=0)
        presenter.select_game(index=1)
        # Act
        runner.run_all()
        # Assert
        assert shown == ["MORDHAU"]
        assert service.game_settings.call_args.kwargs["game_id"] == "mordhau"

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

    def test_resolutions_offered(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Offers the detected screen above the bundled resolutions, the one in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.open_resolution_choice()
        # Assert
        assert view.resolution_offers == [
            ChoiceView(detected=(_SCREEN,), groups=(ChoiceGroup(title="", items=_BUNDLED_RESOLUTIONS),), selected=0)
        ]

    def test_no_screen_detected(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Offers only the bundled resolutions when no screen is detected, the one in use selected among them.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
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
        # Act
        presenter.choose_resolution(position=3)
        # Assert
        service.save_resolution.assert_called_once_with(resolution="2560x1440")
        assert view.hardware is not None and view.hardware.resolution == "2560x1440"
        assert view.settings is not None and (view.settings.index, view.status) == (3, "")

    def test_closest_smaller_resolution(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Shows the preset of the closest smaller resolution when the game has none for the one in use, and says so.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.choose_resolution(position=2)
        # Assert
        assert view.settings is not None and view.settings.index == 3
        assert view.status == "No preset for 2560x1600: showing the one for 2560x1440."

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
        # Act
        presenter.choose_resolution(position=1)
        # Assert
        assert view.settings is not None and view.settings.index == 1
        assert view.status == "Too demanding for this PC: even the lowest settings may stutter at this resolution."

    def test_same_resolution(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Saves and requests nothing when the resolution in use is picked again.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.choose_resolution(position=0)
        # Assert
        service.save_resolution.assert_not_called()
        assert service.game_settings.call_count == 1

    def test_chosen_without_game(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Saves and shows a resolution picked before any game is chosen, requesting nothing.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
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
        runner.deferred = True
        presenter.choose_resolution(position=2)
        presenter.choose_resolution(position=3)
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
        self.show_settings(presenter=presenter)
        presenter.choose_resolution(position=2)
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
        # Act
        presenter.search_games(text="")
        presenter.select_game(index=1)
        # Assert
        assert (view.games, view.game_selected) == (["Baldur's Gate 3", "MORDHAU"], 1)
        assert service.game_presets.call_count == 1
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
        presenter.change_theme(index=2)
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
        presenter.change_theme(index=0)
        # Assert
        service.save_theme.assert_not_called()

    def test_names_translated(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Translates the theme names with the UI language, keeping the theme in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.change_theme(index=1)
        # Act
        presenter.change_language(language="ru")
        # Assert
        assert view.themes == (["Авто", "Светлая", "Тёмная"], 1)


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
        presenter.start()
        # Act
        presenter.choose_gpu(position=1)
        presenter.select_game(index=1)
        # Assert
        assert view.hardware is not None and view.hardware.gpu == "NVIDIA GeForce RTX 4090"
        assert view.status == "NVIDIA does not know your graphics card. Choose the closest one from the list."
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
