"""Tests of the main window logic on a fake window, a runner that runs tasks in place and a debouncer run by hand."""

# pylint: disable=too-many-lines

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from app.core.models import (
    DatabaseUpdate,
    Game,
    GameChoice,
    GamePresets,
    GamesTab,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
    InstalledGame,
    SystemHardware,
    ThemeMode,
)
from app.ui.presenter import Presenter
from app.ui.views import ChoiceGroup, ChoiceView, HardwareView, SettingRow, SettingsView, StatusLevel
from presenter_fakes import (
    AMD_CPU,
    BG3_EXE,
    BUNDLED_RESOLUTIONS,
    CPU,
    DESKTOP_GPU,
    FIT_HINT,
    FakeDebouncer,
    FakeHardware,
    FakeRunner,
    FakeView,
    GAMES,
    INSTALLED,
    INTEL_CPU,
    LAPTOP_GPU,
    LAPTOP_VIEW,
    PRESETS,
    PRESETS_FILE,
    PresenterTests,
    SCREEN,
    SETUP,
    SHOWN,
)

__all__: tuple = ()


class TestStart(PresenterTests):
    """Tests of Presenter.start and the hardware flow."""

    def test_games_and_hardware(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
            LAPTOP_VIEW,
            "",
        )
        assert (view.tab, view.game_selected, view.cover) == (GamesTab.ALL, 0, "picture")
        assert view.settings is not None and view.settings.title == "Baldur's Gate 3"
        service.check_hardware.assert_called_once_with(choice=HardwareChoice(cpu_name=CPU, gpu=LAPTOP_GPU))
        service.update_database_if_due.assert_called_once_with()

    def test_hardware_loading(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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

    def test_nothing_detected(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Invites a choice in place of both the CPU and the GPU, explaining in one status line.

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
            gpus=(DESKTOP_GPU,),
            resolutions=BUNDLED_RESOLUTIONS,
            choice=HardwareChoice(cpu_name=None, gpu=None),
            resolution="1920x1080",
        )
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.MISSING, failed=("cpu", "gpu"))
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
        assert (view.status, view.status_level) == (
            "Could not detect the processor or an NVIDIA graphics card. Choose both from the lists.",
            StatusLevel.ERROR,
        )

    def test_setup_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        assert view.status == "Could not detect the hardware: unexpected error, see the logs"
        assert view.status_level is StatusLevel.ERROR
        service.check_hardware.assert_not_called()

    def test_first_check_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Reports a failed first hardware check and requests no presets with the unchecked hardware.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.side_effect = requests.ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.games.select_game(index=1)
        # Assert
        assert (view.status, view.hardware) == (
            "Could not get data from NVIDIA: no connection, check your internet",
            LAPTOP_VIEW,
        )
        service.game_presets.assert_not_called()

    @pytest.mark.parametrize(
        argnames=("check", "expected"),
        argvalues=[
            (
                HardwareCheck(state=HardwareState.MISSING, failed=("gpu",)),
                "No NVIDIA graphics card found. Choose yours from the list: the app works with NVIDIA cards only.",
            ),
            (
                HardwareCheck(state=HardwareState.MISSING, failed=("cpu",)),
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
        self, presenter: Presenter, view: FakeView, service: MagicMock, check: HardwareCheck, expected: str
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
        self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner
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


class TestGame(PresenterTests):
    """Tests of Presenter.select_game."""

    def test_no_hardware(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Repeats why there are no recommendations when a game is chosen without accepted hardware.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.MISSING, failed=("gpu",))
        presenter.start()
        view.status = ""
        # Act
        presenter.games.select_game(index=1)
        # Assert
        assert (
            view.status
            == "No NVIDIA graphics card found. Choose yours from the list: the app works with NVIDIA cards only."
        )
        service.game_presets.assert_not_called()

    def test_settings_shown(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        presenter.games.select_game(index=1)
        # Assert
        service.game_presets.assert_called_once_with(game_id="mordhau", hardware=FakeHardware.with_gpu(gpu=LAPTOP_GPU))
        service.game_settings.assert_called_once_with(game_id="mordhau", presets=PRESETS)
        assert (view.settings, view.status) == (SHOWN, "")

    def test_requests_wait_for_the_selection_to_rest(
        self, presenter: Presenter, view: FakeView, service: MagicMock, debouncer: FakeDebouncer
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
        presenter.games.select_game(index=1)
        presenter.games.select_game(index=0)
        presenter.games.select_game(index=1)
        waiting: tuple[str, int] = (view.status, service.game_presets.call_count)
        debouncer.fire()
        # Assert
        assert waiting == ("Loading…", 0)
        service.game_presets.assert_called_once_with(game_id="mordhau", hardware=FakeHardware.with_gpu(gpu=LAPTOP_GPU))

    def test_pending_request_dropped_without_hardware(
        self, presenter: Presenter, service: MagicMock, debouncer: FakeDebouncer
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
        presenter.games.select_game(index=1)
        presenter.open_gpu_choice()
        presenter.choose_gpu(position=1)
        # Act
        debouncer.fire()
        # Assert
        service.game_presets.assert_not_called()

    def test_no_recommendations(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Shows the big notice and says why in the status line when NVIDIA has no recommendation for the game.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.return_value = GamePresets(
            profile="regular", version="1", presets_file=PRESETS_FILE, resolutions=()
        )
        presenter.start()
        # Act
        presenter.games.select_game(index=0)
        # Assert
        assert (view.settings, view.no_recommendation, view.status) == (
            None,
            True,
            "No recommendations (there are none, or your hardware is too weak for this resolution and game)",
        )
        assert view.status_level is StatusLevel.WARNING
        service.game_settings.assert_not_called()

    def test_presets_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Reports a failed presets request.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.side_effect = requests.ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.games.select_game(index=1)
        # Assert
        assert (view.status, view.settings) == (
            "Could not get data from NVIDIA: no connection, check your internet",
            None,
        )

    def test_stale_answer_dropped(
        self, presenter: Presenter, view: FakeView, service: MagicMock, runner: FakeRunner
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
        presenter.games.select_game(index=1)
        presenter.games.select_game(index=0)
        # Act
        runner.run_all()
        # Assert
        assert shown == ["Baldur's Gate 3"]
        assert service.game_settings.call_args.kwargs["game_id"] == "baldurs_gate_3"

    def test_game_change_clears(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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
        presenter.games.select_game(index=0)
        # Assert
        assert (view.settings, view.status) == (None, "Loading…")
        assert view.status_level is StatusLevel.INFO


class TestSettings(PresenterTests):
    """Tests of the settings shown, Presenter.move_slider and back_to_optimal."""

    def test_slider_and_back_to_optimal(self, presenter: Presenter, view: FakeView) -> None:
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
                SettingRow(
                    name="Shadows", value="High", changed=True, hint="Differs from the recommended preset (Medium)"
                ),
                SettingRow(name="Scale", value="1.000", changed=False),
            ),
            count=3,
            index=3,
            recommended=2,
            optimal=False,
        )
        assert view.settings is not None and (view.settings.index, view.settings.optimal) == (2, True)

    @pytest.mark.parametrize(argnames="index", argvalues=[0, 4], ids=["below", "above"])
    def test_slider_out_of_range(self, presenter: Presenter, view: FakeView, index: int) -> None:
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

    def test_slider_without_settings(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Ignores the slider and the request for the recommended preset while no settings are shown.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_settings.side_effect = requests.ConnectionError("timeout")
        self.show_settings(presenter=presenter)
        # Act
        presenter.move_slider(index=1)
        presenter.back_to_optimal()
        # Assert
        assert view.settings is None

    def test_settings_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Reports a failed settings request.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_settings.side_effect = requests.ConnectionError("timeout")
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert (view.status, view.settings) == (
            "Could not get data from NVIDIA: no connection, check your internet",
            None,
        )


class TestResolution(PresenterTests):
    """Tests of Presenter.open_resolution_choice and choose_resolution."""

    def test_resolutions_offered(
        self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner
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
                detected=(SCREEN,),
                groups=(ChoiceGroup(title="", items=BUNDLED_RESOLUTIONS),),
                selected=0,
                fitting=frozenset({1, 3}),
                fit_mark="16:9",
                fit_hint=FIT_HINT,
            )
        ]

    def test_game_resolutions_offered(self, presenter: Presenter, view: FakeView) -> None:
        """
        Offers the detected screen above the game's resolutions, the largest first, marking shape and demanding ones.

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
                detected=(SCREEN,),
                groups=(ChoiceGroup(title="", items=("3840x2160", "2560x1440")),),
                selected=0,
                fitting=frozenset({1, 2}),
                fit_mark="16:9",
                fit_hint=FIT_HINT,
                warned=frozenset({1}),
                warn_hint="Too demanding for this PC: even the lowest settings may stutter at this resolution.",
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
        service.game_presets.return_value = replace(PRESETS, resolutions=PRESETS.resolutions[:1])
        presenter.games.select_game(index=0)
        # Act
        presenter.choose_resolution(position=2)
        # Assert
        service.save_resolution.assert_called_once_with(resolution="2560x1440")

    def test_no_screen_detected(
        self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner
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
            SETUP, system=replace(SETUP.system, resolution=None), resolution="2560x1600"
        )
        presenter.start()
        # Act
        presenter.open_resolution_choice()
        # Assert
        assert view.resolution_offers == [
            ChoiceView(detected=(), groups=(ChoiceGroup(title="", items=BUNDLED_RESOLUTIONS),), selected=1)
        ]

    def test_nothing_offered_before_detection(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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

    def test_chosen_saved_and_applied(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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

    def test_closest_smaller_resolution(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Shows the preset of the closest smaller resolution when the game has none for the one in use, and says so.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(SETUP, resolution="2560x1600")
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert view.settings is not None and view.settings.index == 3
        assert view.status == "No preset for 2560x1600: showing the one for 2560x1440."
        assert view.status_level is StatusLevel.WARNING

    def test_smallest_when_all_larger(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Shows the preset of the smallest resolution when every one of the game is larger than the one in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.game_presets.return_value = replace(PRESETS, resolutions=PRESETS.resolutions[1:])
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert view.settings is not None and view.settings.index == 3
        assert view.status == "No preset for 1920x1080: showing the one for 2560x1440."

    def test_below_min_spec_noted(self, presenter: Presenter, view: FakeView) -> None:
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
        self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner
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
        self, presenter: Presenter, view: FakeView, service: MagicMock, runner: FakeRunner, fails: bool
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
            service.game_settings.side_effect = requests.ConnectionError("timeout")
        presenter.open_resolution_choice()
        runner.deferred = True
        presenter.choose_resolution(position=1)
        presenter.choose_resolution(position=2)
        # Act
        runner.run_all()
        # Assert
        if fails:
            assert (view.settings, view.status) == (
                None,
                "Could not get data from NVIDIA: no connection, check your internet",
            )
        else:
            assert view.settings is not None and (view.settings.index, view.status) == (3, "")


class TestLanguage(PresenterTests):
    """Tests of Presenter.change_language."""

    def test_switch(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Saves the language and re-renders every text shown: setting names and values, the status note.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(SETUP, resolution="2560x1600")
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


class TestTheme(PresenterTests):
    """Tests of Presenter.change_theme."""

    def test_switch(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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


class TestAutoUpdate(PresenterTests):
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


class TestDatabaseUpdate(PresenterTests):
    """Tests of the database update run at the start."""

    # noinspection PyMethodOverriding
    @pytest.fixture(name="updater")
    def _updater(self) -> FakeRunner:
        """
        Give the database update a runner of its own.

        :return: runner of the database update
        """
        return FakeRunner()

    _RENAMED: tuple[Game, ...] = (
        Game(game_id="baldurs_gate_3", name="Baldur's Gate III"),
        Game(game_id="mordhau", name="Mordhau II"),
    )
    _RENAMED_INSTALLED: tuple[InstalledGame, ...] = (InstalledGame(game=_RENAMED[0], executable=BG3_EXE),)

    @pytest.mark.parametrize(
        argnames="result",
        argvalues=[DatabaseUpdate.SKIPPED, DatabaseUpdate.UNCHANGED],
        ids=["skipped", "unchanged"],
    )
    def test_nothing_refreshed(
        self, presenter: Presenter, view: FakeView, service: MagicMock, result: DatabaseUpdate
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

    def test_games_and_lists_refreshed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Shows the games of a new database and searches again, keeping the chosen game, and offers its CPU list.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.games.side_effect = [GAMES, self._RENAMED]
        service.find_games.side_effect = [INSTALLED, self._RENAMED_INSTALLED]
        service.hardware_setup.side_effect = [SETUP, replace(SETUP, amd_cpus=(AMD_CPU,))]
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
        assert view.cpu_offers[0].groups[0].items == (AMD_CPU,)
        assert view.hardware == LAPTOP_VIEW

    def test_chosen_game_gone(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Chooses the first game when the new database doesn't list the chosen one any more.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.games.side_effect = [GAMES, self._RENAMED[:1]]
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
        service.choose_hardware.return_value = FakeHardware.ready(gpu=DESKTOP_GPU)
        # Act
        presenter.open_gpu_choice()
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
            service.check_hardware.side_effect = requests.ConnectionError("timeout")
        # Act
        presenter.start()
        # Assert
        service.update_database_if_due.assert_called_once_with()

    def test_failed_update(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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

    def test_refresh_without_setup(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        service.games.side_effect = [GAMES, self._RENAMED]
        # Act
        presenter.start()
        # Assert
        assert (service.hardware_setup.call_count, view.games) == (1, ["Baldur's Gate III", "Mordhau II"])

    def test_own_runner(self, presenter: Presenter, view: FakeView, service: MagicMock, updater: FakeRunner) -> None:
        """
        Downloads in a runner of its own: the presets of a game chosen meanwhile don't wait for the download.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :param updater: runner of the database update
        :return: None
        """
        # Arrange
        updater.deferred = True
        # Act
        self.show_settings(presenter=presenter)
        # Assert
        assert (view.settings, service.update_database_if_due.call_count) == (SHOWN, 0)
        updater.run_all()
        service.update_database_if_due.assert_called_once_with()


class TestSaves(PresenterTests):
    """Tests of the settings saves: a runner of their own and a failure in the status line."""

    # noinspection PyMethodOverriding
    @pytest.fixture(name="saver")
    def _saver(self) -> FakeRunner:
        """
        Give the settings saves a runner of their own.

        :return: runner of the settings saves
        """
        return FakeRunner()

    def test_failed_save_reported(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Reports a failed settings save in the status line.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.save_theme.side_effect = OSError("disk full")
        presenter.start()
        # Act
        presenter.change_theme(mode=ThemeMode.DARK)
        # Assert
        assert (view.status, view.status_level, view.theme) == (
            "Could not save the settings: unexpected error, see the logs",
            StatusLevel.ERROR,
            ThemeMode.DARK,
        )

    def test_not_held_by_requests(self, presenter: Presenter, service: MagicMock, runner: FakeRunner) -> None:
        """
        Saves in a runner of its own: a save doesn't wait for the requests still running.

        :param presenter: presenter under test
        :param service: service mock
        :param runner: runner of the requests
        :return: None
        """
        # Arrange
        self.start(presenter=presenter, service=service)
        runner.deferred = True
        presenter.games.select_game(index=1)
        # Act
        presenter.change_theme(mode=ThemeMode.DARK)
        # Assert
        service.save_theme.assert_called_once_with(theme=ThemeMode.DARK)
        service.game_presets.assert_not_called()


class TestHardwareChoice(PresenterTests):
    """Tests of Presenter.open_cpu_choice, open_gpu_choice, choose_cpu and choose_gpu."""

    def test_pick_from_offered_list(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Picks from the CPUs offered when the choice opened, though a new database changed the list meanwhile.

        :param presenter: presenter under test
        :param service: service mock
        :return: None
        """
        # Arrange
        newer: str = "AMD Ryzen 5 9600X 6-Core Processor"
        service.hardware_setup.side_effect = [
            replace(SETUP, amd_cpus=(AMD_CPU,)),
            replace(SETUP, amd_cpus=(newer, AMD_CPU)),
        ]
        presenter.start()
        presenter.open_cpu_choice()
        service.update_database_if_due.return_value = DatabaseUpdate.UPDATED
        presenter.change_auto_update(enabled=False)
        presenter.change_auto_update(enabled=True)
        # Act
        presenter.choose_cpu(position=1)
        # Assert
        assert service.choose_hardware.call_args.kwargs["choice"].cpu_name == AMD_CPU

    def test_pick_without_choice_ignored(self, presenter: Presenter, service: MagicMock) -> None:
        """
        Ignores a pick when no choice was offered.

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

    def test_gpus_offered(self, presenter: Presenter, view: FakeView) -> None:
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

    def test_cpus_offered(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Offers the detected CPU above vendor tabs of the bundled ones, the one in use selected.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(
            SETUP,
            amd_cpus=(AMD_CPU,),
            intel_cpus=(INTEL_CPU,),
            choice=HardwareChoice(cpu_name=INTEL_CPU, gpu=LAPTOP_GPU),
        )
        presenter.start()
        # Act
        presenter.open_cpu_choice()
        # Assert
        assert view.cpu_offers == [
            ChoiceView(
                detected=(CPU,),
                groups=(ChoiceGroup(title="AMD", items=(AMD_CPU,)), ChoiceGroup(title="Intel", items=(INTEL_CPU,))),
                selected=2,
            )
        ]

    def test_no_bundled_cpus(self, presenter: Presenter, view: FakeView) -> None:
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
        assert view.cpu_offers == [ChoiceView(detected=(CPU,), groups=(), selected=0)]

    def test_nothing_offered_before_detection(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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

    def test_new_gpu_reloads_presets(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Uses the GPU NVIDIA accepts and requests the presets of the game shown again for it, at once.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.choose_hardware.return_value = FakeHardware.ready(gpu=DESKTOP_GPU)
        self.show_settings(presenter=presenter)
        # Act
        presenter.open_gpu_choice()
        presenter.choose_gpu(position=1)
        # Assert
        service.choose_hardware.assert_called_once_with(choice=HardwareChoice(cpu_name=CPU, gpu=DESKTOP_GPU))
        last_call: Any = service.game_presets.call_args
        assert last_call.kwargs == {"game_id": "mordhau", "hardware": FakeHardware.with_gpu(gpu=DESKTOP_GPU)}
        assert view.hardware == HardwareView(
            cpu=CPU, gpu="NVIDIA GeForce RTX 4090", resolution=SCREEN, memory="16 GB", video_memory="unknown"
        )
        assert view.settings == SHOWN

    def test_new_cpu_accepted(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Uses a chosen CPU NVIDIA accepts, clearing the hardware problem shown before.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.hardware_setup.return_value = replace(SETUP, amd_cpus=(AMD_CPU,))
        service.check_hardware.return_value = HardwareCheck(state=HardwareState.REJECTED, failed=("cpu",))
        service.choose_hardware.return_value = FakeHardware.ready(gpu=LAPTOP_GPU, cpu_name=AMD_CPU)
        presenter.start()
        # Act
        presenter.open_cpu_choice()
        presenter.choose_cpu(position=1)
        presenter.games.select_game(index=1)
        # Assert
        assert (view.hardware is not None and view.hardware.cpu, view.status) == (AMD_CPU, "")
        assert service.game_presets.call_args.kwargs["hardware"] == FakeHardware.with_gpu(
            gpu=LAPTOP_GPU, cpu_name=AMD_CPU
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
        presenter.open_gpu_choice()
        presenter.choose_gpu(position=0)
        # Assert
        service.choose_hardware.assert_not_called()

    def test_rejected_gpu(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        presenter.open_gpu_choice()
        presenter.choose_gpu(position=1)
        presenter.games.select_game(index=1)
        # Assert
        assert view.hardware is not None and view.hardware.gpu == "NVIDIA GeForce RTX 4090"
        assert view.status == "NVIDIA does not know your graphics card. Choose the closest one from the list."
        assert view.status_level is StatusLevel.ERROR
        service.game_presets.assert_not_called()

    def test_check_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Reports a failed check of a new GPU and goes back to the hardware in use.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.choose_hardware.side_effect = requests.ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.open_gpu_choice()
        presenter.choose_gpu(position=1)
        # Assert
        assert (view.hardware, view.status) == (
            LAPTOP_VIEW,
            "Could not get data from NVIDIA: no connection, check your internet",
        )
        assert view.status_level is StatusLevel.ERROR


class TestSettingsSkeleton(PresenterTests):
    """Tests of the settings skeleton: moving while settings are requested, still otherwise."""

    def test_loading(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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
        presenter.games.select_game(index=1)
        # Assert
        assert (view.settings, view.settings_loading) == (None, True)

    @pytest.mark.parametrize(
        argnames="case",
        argvalues=["no hardware", "no recommendation", "failed"],
        ids=["no hardware", "no recommendation", "failed"],
    )
    def test_still(self, presenter: Presenter, view: FakeView, service: MagicMock, case: str) -> None:
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
            service.check_hardware.return_value = HardwareCheck(state=HardwareState.MISSING, failed=("gpu",))
        elif case == "no recommendation":
            service.game_presets.return_value = replace(PRESETS, resolutions=())
        else:
            service.game_settings.side_effect = requests.ConnectionError("timeout")
        presenter.start()
        # Act
        presenter.games.select_game(index=1)
        # Assert
        assert (view.settings, view.settings_loading) == (None, False)
