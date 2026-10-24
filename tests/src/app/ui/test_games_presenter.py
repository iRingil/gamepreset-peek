"""Tests of the game tabs logic, driven through the presenter that owns it, on the fakes."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.models import GameChoice, GamesTab, InstalledGame
from app.ui.presenter import Presenter
from app.ui.views import InstalledGameView
from presenter_fakes import (
    BG3_EXE,
    COVER,
    FOLDERS,
    FakeDebouncer,
    FakeRunner,
    FakeView,
    GAMES,
    INSTALLED,
    PresenterTests,
    SHOWN,
)

__all__: tuple = ()


class TestSearch(PresenterTests):
    """Tests of GamesPresenter.search_games."""

    def test_filtered_ignoring_case(self, presenter: Presenter, view: FakeView) -> None:
        """
        Shows only the games whose name contains the text, ignoring case.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        # Act
        presenter.games.search_games(text=" mord ")
        # Assert
        assert (view.games, view.game_selected) == (["MORDHAU"], None)

    def test_filter_waits_for_the_typing_to_rest(
        self, presenter: Presenter, view: FakeView, debouncer: FakeDebouncer
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
        presenter.games.search_games(text="m")
        presenter.games.search_games(text="mo")
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
        presenter.games.search_games(text="MORD")
        # Act
        presenter.games.select_game(index=0)
        # Assert
        assert service.game_presets.call_args.kwargs["game_id"] == "mordhau"

    def test_chosen_game_kept(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Keeps the chosen game selected when the search is cleared, without requesting its presets again.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        self.show_settings(presenter=presenter)
        presenter.games.search_games(text="mord")
        service.game_presets.reset_mock()
        # Act
        presenter.games.search_games(text="")
        presenter.games.select_game(index=1)
        # Assert
        assert (view.games, view.game_selected) == (["Baldur's Gate 3", "MORDHAU"], 1)
        service.game_presets.assert_not_called()
        assert view.settings is not None


class TestInstalledGames(PresenterTests):
    """Tests of the search for installed games, GamesPresenter.find_games and select_installed_game."""

    def test_found_at_start(self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner) -> None:
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
        assert searching == (True, list(FOLDERS))
        assert (view.finding, view.installed, view.installed_selected) == (
            False,
            [InstalledGameView(name="Baldur's Gate 3", executable=BG3_EXE)],
            0,
        )
        service.find_games.assert_called_once_with(folders=FOLDERS)

    def test_icons_with_games(self, presenter: Presenter, view: FakeView, finder: FakeRunner, icons: MagicMock) -> None:
        """
        Gets the icon files of the executables in the search and shows them with the games at once.

        :param presenter: presenter under test
        :param view: fake window
        :param finder: runner of the search for installed games
        :param icons: icons of the executables
        :return: None
        """
        # Arrange
        icon: Path = Path("bg3.png")
        icons.get.return_value = icon
        finder.deferred = True
        presenter.start()
        # Act
        finder.run_all()
        # Assert
        assert view.installed == [InstalledGameView(name="Baldur's Gate 3", executable=BG3_EXE, icon=icon)]
        icons.get.assert_called_once_with(executable=BG3_EXE)

    def test_folders_unreadable(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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

    def test_search_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        assert (view.status, view.installed, view.finding) == (
            "Could not search for games: unexpected error, see the logs",
            [],
            False,
        )

    def test_asked_again_while_searching(
        self, presenter: Presenter, view: FakeView, service: MagicMock, finder: FakeRunner
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
        service.find_games.side_effect = [(), INSTALLED]
        finder.deferred = True
        presenter.start()
        presenter.games.find_games()
        presenter.games.find_games()
        # Act
        finder.run_all()
        # Assert
        assert service.find_games.call_count == 2
        assert [game.name for game in view.installed] == ["Baldur's Gate 3"]

    def test_installed_game_chosen(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Shows the settings of an installed game chosen in the installed games tab.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.return_value = (*INSTALLED, InstalledGame(game=GAMES[1], executable=BG3_EXE))
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        presenter.start()
        # Act
        presenter.games.select_installed_game(index=1)
        # Assert
        assert service.game_presets.call_args.kwargs["game_id"] == "mordhau"
        assert view.settings is not None and view.settings.title == "MORDHAU"

    def test_game_per_tab(self, presenter: Presenter, view: FakeView) -> None:
        """
        Keeps a game of its own in each tab and shows the one of the tab in use.

        :param presenter: presenter under test
        :param view: fake window
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.games.select_game(index=1)
        # Act
        presenter.games.select_tab(tab=GamesTab.INSTALLED)
        installed: str | None = None if view.settings is None else view.settings.title
        presenter.games.select_tab(tab=GamesTab.ALL)
        # Assert
        assert (installed, view.settings) == ("Baldur's Gate 3", SHOWN)

    def test_choice_kept_after_search(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Keeps the chosen game selected among the installed games found by a new search.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        presenter.start()
        presenter.games.select_game(index=0)
        # Act
        presenter.games.find_games()
        # Assert
        assert (view.installed_selected, service.find_games.call_count) == (0, 2)


class TestGameChoice(PresenterTests):
    """Tests of the saved game tab and the game chosen in each tab."""

    def test_first_games_saved(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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

    def test_saved_games_restored(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        assert (view.tab, view.game_selected, view.installed_selected, view.settings) == (GamesTab.ALL, 1, 0, SHOWN)
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
        presenter.games.select_game(index=1)
        presenter.games.select_tab(tab=GamesTab.INSTALLED)
        presenter.games.select_installed_game(index=0)
        # Assert
        assert [call.kwargs["choice"] for call in service.save_game_choice.call_args_list] == [
            GameChoice(tab=GamesTab.ALL, installed_game_id="baldurs_gate_3", catalog_game_id="mordhau"),
            GameChoice(tab=GamesTab.INSTALLED, installed_game_id="baldurs_gate_3", catalog_game_id="mordhau"),
        ]

    def test_no_installed_games(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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

    def test_installed_games_gone(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Clears the game shown in the installed games tab when a new search finds no games.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.side_effect = [INSTALLED, ()]
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED)
        presenter.start()
        # Act
        presenter.games.find_games()
        # Assert
        assert (view.cover, view.settings, view.settings_loading, view.status) == ("empty", None, False, "")
        assert service.save_game_choice.call_args.kwargs["choice"].installed_game_id == "baldurs_gate_3"

    def test_installed_game_gone(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
        """
        Moves to the first installed game when the chosen one is no longer found, showing it in its tab.

        :param presenter: presenter under test
        :param view: fake window
        :param service: service mock
        :return: None
        """
        # Arrange
        service.find_games.side_effect = [(InstalledGame(game=GAMES[1], executable=BG3_EXE),), INSTALLED]
        service.saved_game_choice.return_value = GameChoice(tab=GamesTab.INSTALLED, installed_game_id="mordhau")
        presenter.start()
        # Act
        presenter.games.find_games()
        # Assert
        assert view.installed_selected == 0
        assert view.settings is not None and view.settings.title == "Baldur's Gate 3"
        assert service.save_game_choice.call_args.kwargs["choice"].installed_game_id == "baldurs_gate_3"


class TestFolders(PresenterTests):
    """Tests of GamesPresenter.add_folder, change_folder and remove_folder."""

    def test_added(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        presenter.games.add_folder(folder="E:/SteamLibrary")
        # Assert
        expected: tuple[str, ...] = (*FOLDERS, "E:\\SteamLibrary")
        assert view.folders == list(expected)
        service.save_game_folders.assert_called_once_with(folders=expected)
        assert service.find_games.call_args.kwargs == {"folders": expected}

    @pytest.mark.parametrize(argnames="folder", argvalues=["d:/games", ""], ids=["listed already", "nothing picked"])
    def test_not_added(self, presenter: Presenter, view: FakeView, service: MagicMock, folder: str) -> None:
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
        presenter.games.add_folder(folder=folder)
        # Assert
        assert view.folders == list(FOLDERS)
        service.save_game_folders.assert_not_called()
        assert service.find_games.call_count == 1

    @pytest.mark.parametrize(
        argnames=("position", "folder", "expected"),
        argvalues=[
            (1, "E:/Games", ("C:\\Program Files", "E:\\Games")),
            (1, "d:/games", ("C:\\Program Files", "d:\\games")),
            (1, "D:/Games", FOLDERS),
            (0, "D:/Games", FOLDERS),
            (2, "E:/Games", FOLDERS),
            (-1, "E:/Games", FOLDERS),
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
        view: FakeView,
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
        presenter.games.change_folder(position=position, folder=folder)
        # Assert
        assert view.folders == list(expected)
        assert service.save_game_folders.call_count == int(expected != FOLDERS)

    @pytest.mark.parametrize(
        argnames=("position", "expected"),
        argvalues=[(0, ("D:\\Games",)), (2, FOLDERS), (-1, FOLDERS)],
        ids=["removed", "after the end", "negative"],
    )
    def test_removed(
        self, presenter: Presenter, view: FakeView, service: MagicMock, position: int, expected: tuple[str, ...]
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
        presenter.games.remove_folder(position=position)
        # Assert
        assert view.folders == list(expected)
        assert service.find_games.call_count == 1 + int(expected != FOLDERS)


class TestCover(PresenterTests):
    """Tests of the box art of the chosen game."""

    def test_shown(self, presenter: Presenter, view: FakeView, service: MagicMock, debouncer: FakeDebouncer) -> None:
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
        assert (waiting, view.cover, view.picture) == ("loading", "picture", COVER)
        service.cover.assert_called_once_with(game=GAMES[0])

    def test_no_box_art(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        presenter.games.select_game(index=1)
        # Assert
        assert (view.cover, view.picture) == ("picture", None)
        service.cover.assert_not_called()

    def test_failed(self, presenter: Presenter, view: FakeView, service: MagicMock) -> None:
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
        presenter.games.select_game(index=0)
        # Assert
        assert (view.cover, view.picture) == ("picture", None)

    def test_stale_dropped(self, presenter: Presenter, view: FakeView, runner: FakeRunner) -> None:
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
        presenter.games.select_game(index=0)
        presenter.games.select_game(index=1)
        # Act
        runner.run_all()
        # Assert
        assert (view.cover, view.picture) == ("picture", None)
