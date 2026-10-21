"""Tests of the main window logic on a fake window and a runner that runs tasks in place."""

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
    HardwareState,
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Setting,
    SettingTranslation,
    ThemeMode,
    Translations,
)
from app.core.service import PresetService
from app.i18n.translator import Translator
from app.ui.presenter import Presenter, SettingRow, SettingsView

__all__: tuple = ()

_LAPTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0")
_DESKTOP_GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684")
_GAMES: tuple[Game, ...] = (
    Game(game_id="baldurs_gate_3", name="Baldur's Gate 3"),
    Game(game_id="mordhau", name="MORDHAU"),
)
_PRESETS_FILE: RemoteFile = RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1)
_PRESETS: GamePresets = GamePresets(
    profile="regular",
    version="1",
    presets_file=_PRESETS_FILE,
    resolutions=(
        ResolutionPreset(resolution="1920x1080", preset_index=2, rate=40, below_min_spec=False),
        ResolutionPreset(resolution="3840x2160", preset_index=1, rate=40, below_min_spec=True),
        ResolutionPreset(resolution="2560x1440", preset_index=2, rate=35, below_min_spec=False),
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


class _Hardware:
    """Hardware the service mock reports."""

    @staticmethod
    def with_gpu(*, gpu: Gpu) -> Hardware:
        """
        Build hardware with a GPU.

        :param gpu: the GPU
        :return: hardware
        """
        return Hardware(
            cpu_name="13th Gen Intel(R) Core(TM) i9-13900HX",
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=16,
            os_version="10.0",
        )

    @classmethod
    def ready(cls, *, gpu: Gpu) -> HardwareCheck:
        """
        Build a READY check result.

        :param gpu: the GPU in use
        :return: check result
        """
        return HardwareCheck(state=HardwareState.READY, hardware=cls.with_gpu(gpu=gpu))


class _FakeView:  # pylint: disable=too-many-instance-attributes
    """Records what the presenter shows; ask_gpu answers from a prepared list."""

    def __init__(self) -> None:
        """
        Start with an empty window.
        """
        self.language: str | None = None
        self.theme: ThemeMode | None = None
        self.themes: tuple[list[str], int] | None = None
        self.hardware: str = ""
        self.status: str = ""
        self.load_games: bool = False
        self.games: list[str] = []
        self.game_selected: int | None = None
        self.resolutions: list[str] = []
        self.settings_button: bool = False
        self.settings: SettingsView | None = None
        self.asks: list[tuple[str, list[str], int | None]] = []
        self.answers: list[int | None] = []

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

    def show_hardware(self, *, text: str) -> None:
        """
        Record the hardware line.

        :param text: the line
        :return: None
        """
        self.hardware = text

    def show_status(self, *, text: str) -> None:
        """
        Record the status line.

        :param text: the line
        :return: None
        """
        self.status = text

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

    def show_resolutions(self, *, items: Sequence[str]) -> None:
        """
        Record the resolution list.

        :param items: resolution captions
        :return: None
        """
        self.resolutions = list(items)

    def show_settings_button(self, *, visible: bool) -> None:
        """
        Record the "Show settings" button state.

        :param visible: whether it is shown
        :return: None
        """
        self.settings_button = visible

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

    def ask_gpu(self, *, message: str, names: Sequence[str], selected: int | None) -> int | None:
        """
        Record the question and give the next prepared answer.

        :param message: why the user has to choose
        :param names: GPU names
        :param selected: preselected position
        :return: the prepared answer
        """
        self.asks.append((message, list(names), selected))
        return self.answers.pop(0)


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

    @pytest.fixture(name="service")
    def _service(self) -> MagicMock:
        """
        Mock the service: two games, the laptop GPU accepted, presets and settings of any game.

        :return: mock with the interface of PresetService
        """
        service: MagicMock = create_autospec(spec=PresetService, instance=True)
        service.games.return_value = _GAMES
        service.check_hardware.return_value = _Hardware.ready(gpu=_LAPTOP_GPU)
        service.game_presets.return_value = _PRESETS
        service.game_settings.return_value = _SETTINGS
        return service

    @pytest.fixture(name="presenter")
    def _presenter(self, view: _FakeView, runner: _Runner, service: MagicMock, locale_dir: Path) -> Presenter:
        """
        Create the presenter in English; tests start it themselves.

        :param view: fake window
        :param runner: runner
        :param service: service mock
        :param locale_dir: compiled catalogs
        :return: presenter under test
        """
        return Presenter(
            view=view,
            service=service,
            runner=runner,
            translator=Translator(language="en", locale_dir=locale_dir),
            theme=ThemeMode.AUTO,
            locale_dir=locale_dir,
        )

    @staticmethod
    def show_settings(*, presenter: Presenter, resolution: int = 2) -> None:
        """
        Start, pick MORDHAU and a resolution and show its settings.

        :param presenter: presenter under test
        :param resolution: position of the resolution in the sorted list
        :return: None
        """
        presenter.start()
        presenter.select_game(index=1)
        presenter.select_resolution(index=resolution)
        presenter.show_settings()


class TestStart(_PresenterTests):
    """Tests of Presenter.start, load_games and the hardware flow."""

    def test_games_and_gpu(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Shows the games and the GPU in use, in the initial language.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange & Act
        presenter.start()
        # Assert
        assert (view.theme, view.themes) == (ThemeMode.AUTO, (["Auto", "Light", "Dark"], 0))
        assert (view.language, view.games, view.hardware, view.status, view.load_games) == (
            "en",
            ["Baldur's Gate 3", "MORDHAU"],
            "Graphics card: NVIDIA GeForce RTX 4060 Laptop GPU",
            "",
            False,
        )

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
                "No NVIDIA graphics card found. NVIDIA recommends settings for NVIDIA graphics cards only.",
            ),
            (
                HardwareCheck(state=HardwareState.REJECTED, failed=("cpu", "bios")),
                "NVIDIA does not support this computer: processor, bios.",
            ),
        ],
        ids=["no nvidia gpu", "rejected"],
    )
    def test_no_hardware(
        self, presenter: Presenter, view: _FakeView, service: MagicMock, check: HardwareCheck, expected: str
    ) -> None:
        """
        Explains why there is no GPU to request presets with; unknown component names are shown as NVIDIA sends them.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param check: hardware check result
        :param expected: hardware line
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = check
        # Act
        presenter.start()
        # Assert
        assert view.hardware == expected

    def test_detected_gpu_chosen(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Asks which detected GPU to use, the first preselected, and checks the choice.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(
            state=HardwareState.CHOOSE_DETECTED_GPU, gpus=(_DESKTOP_GPU, _LAPTOP_GPU)
        )
        service.choose_gpu.return_value = _Hardware.ready(gpu=_LAPTOP_GPU)
        view.answers = [1]
        # Act
        presenter.start()
        # Assert
        assert view.asks == [
            (
                "Several NVIDIA graphics cards found. Choose the one you play on.",
                ["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 4060 Laptop GPU"],
                0,
            )
        ]
        service.choose_gpu.assert_called_once_with(gpu=_LAPTOP_GPU)
        assert view.hardware == "Graphics card: NVIDIA GeForce RTX 4060 Laptop GPU"

    def test_listed_gpu_cancelled(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Offers the bundled list with nothing preselected; a cancel leaves no GPU in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.CHOOSE_LISTED_GPU, gpus=(_DESKTOP_GPU,))
        view.answers = [None]
        # Act
        presenter.start()
        # Assert
        assert view.asks[0][2] is None
        assert view.hardware == "No graphics card chosen."
        service.choose_gpu.assert_not_called()


class TestGame(_PresenterTests):
    """Tests of Presenter.select_game."""

    def test_no_hardware(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Asks for a GPU first when there is none in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.NO_NVIDIA_GPU)
        presenter.start()
        # Act
        presenter.select_game(index=0)
        # Assert
        assert view.status == "Choose a graphics card first."
        service.game_presets.assert_not_called()

    def test_resolutions(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the resolutions of the game, the largest first, marking those below the minimum requirements.

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
        assert view.resolutions == ["3840x2160 (below minimum requirements)", "2560x1440", "1920x1080"]
        assert (view.status, view.settings_button) == ("", False)

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
        assert (view.resolutions, view.status) == ([], "No recommendations")

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
        presets: dict[str, GamePresets] = {
            "baldurs_gate_3": GamePresets(
                profile="regular",
                version="1",
                presets_file=_PRESETS_FILE,
                resolutions=(ResolutionPreset(resolution="1280x720", preset_index=1, rate=40, below_min_spec=False),),
            ),
            "mordhau": _PRESETS,
        }
        shown: list[list[str]] = []

        def record(*, items: Sequence[str]) -> None:
            """
            Record every resolution list shown.

            :param items: resolution captions
            :return: None
            """
            shown.append(list(items))

        service.game_presets.side_effect = lambda **kwargs: presets[kwargs["game_id"]]
        presenter.start()
        runner.deferred = True
        view.show_resolutions = record  # type: ignore[method-assign]
        presenter.select_game(index=0)
        presenter.select_game(index=1)
        # Act
        runner.run_all()
        # Assert
        assert ["1280x720"] not in shown
        assert shown[-1] == ["3840x2160 (below minimum requirements)", "2560x1440", "1920x1080"]


class TestSettings(_PresenterTests):
    """Tests of Presenter.select_resolution, show_settings, move_slider and back_to_optimal."""

    def test_resolution_selected(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Offers the "Show settings" button for a chosen resolution.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.select_game(index=1)
        # Act
        presenter.select_resolution(index=0)
        # Assert
        assert (view.settings_button, view.settings) == (True, None)

    def test_recommended_preset(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Shows the recommended preset of the resolution with the slider on it and hides the button.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange & Act
        self.show_settings(presenter=presenter)
        # Assert
        service.game_settings.assert_called_once_with(game_id="mordhau", presets=_PRESETS)
        assert view.settings == SettingsView(
            title="MORDHAU",
            subtitle="1920x1080, target 40 FPS",
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
        assert (view.settings_button, view.status) == (False, "")

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
            subtitle="1920x1080, target 40 FPS",
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

    def test_settings_failed(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Reports a failed settings request and brings the button back for a retry.

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
        assert (view.status, view.settings_button, view.settings) == (
            "Could not get data from NVIDIA: timeout",
            True,
            None,
        )

    def test_game_change_clears(self, presenter: Presenter, view: _FakeView) -> None:
        """
        Clears the settings when another game is chosen.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.select_game(index=0)
        # Assert
        assert (view.settings, view.settings_button) == (None, False)


class TestLanguage(_PresenterTests):
    """Tests of Presenter.change_language."""

    def test_switch(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Saves the language and re-renders every text shown, setting names and values included.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        # Act
        presenter.change_language(language="ru")
        # Assert
        service.save_language.assert_called_once_with(language="ru")
        assert (presenter.language, view.language, view.hardware, view.resolutions[0]) == (
            "ru",
            "ru",
            "Видеокарта: NVIDIA GeForce RTX 4060 Laptop GPU",
            "3840x2160 (ниже минимальных требований)",
        )
        assert view.settings is not None
        assert (view.settings.rows, view.settings.subtitle, view.settings.caption) == (
            (
                SettingRow(name="Тени", value="Среднее", changed=False),
                SettingRow(name="Масштаб", value="1.000", changed=False),
            ),
            "1920x1080, цель 40 FPS",
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


class TestChangeGpu(_PresenterTests):
    """Tests of Presenter.change_gpu."""

    def test_current_preselected(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Offers every GPU with the one in use preselected; a cancel keeps it.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.all_gpus.return_value = (_DESKTOP_GPU, _LAPTOP_GPU)
        view.answers = [None]
        presenter.start()
        # Act
        presenter.change_gpu()
        # Assert
        assert view.asks == [
            (
                "Choose the graphics card to get recommended settings for.",
                ["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 4060 Laptop GPU"],
                1,
            )
        ]
        assert view.hardware == "Graphics card: NVIDIA GeForce RTX 4060 Laptop GPU"

    def test_new_gpu_reloads_presets(self, presenter: Presenter, view: _FakeView, service: MagicMock) -> None:
        """
        Uses the chosen GPU and requests the presets of the game shown again for it.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.all_gpus.return_value = (_DESKTOP_GPU, _LAPTOP_GPU)
        service.choose_gpu.return_value = _Hardware.ready(gpu=_DESKTOP_GPU)
        view.answers = [0]
        self.show_settings(presenter=presenter)
        # Act
        presenter.change_gpu()
        # Assert
        service.choose_gpu.assert_called_once_with(gpu=_DESKTOP_GPU)
        last_call: Any = service.game_presets.call_args
        assert last_call.kwargs == {"game_id": "mordhau", "hardware": _Hardware.with_gpu(gpu=_DESKTOP_GPU)}
        assert (view.hardware, view.settings, view.settings_button) == (
            "Graphics card: NVIDIA GeForce RTX 4090",
            None,
            False,
        )
