"""Tests of the game tabs: installed games with their folders, and all games."""

import sys
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QWidget

from app.core.models import GamesTab
from app.i18n.translator import Translator
from app.ui.games_panel import GamesPanel
from app.ui.views import InstalledGameView

__all__: tuple = ()


class TestGamesPanel:
    """Tests of GamesPanel."""

    @pytest.fixture(name="callbacks")
    def _callbacks(self) -> dict[str, MagicMock]:
        """
        Record what the panel passes on.

        :return: a mock per callback
        """
        return {
            name: MagicMock()
            for name in (
                "on_select_installed",
                "on_select",
                "on_search",
                "on_find",
                "on_add_folder",
                "on_change_folder",
                "on_remove_folder",
                "on_tab",
            )
        }

    @pytest.fixture(name="panel")
    def _panel(self, qt_app: QApplication, locale_dir: Path, callbacks: dict[str, MagicMock]) -> Iterator[GamesPanel]:
        """
        Show the panel in English.

        :param qt_app: Qt application
        :param locale_dir: compiled catalogs
        :param callbacks: callback mocks
        :return: the panel
        """
        panel: GamesPanel = GamesPanel(**callbacks)
        panel.apply_language(translator=Translator(language="en", locale_dir=locale_dir))
        panel.show()
        qt_app.processEvents()
        yield panel
        panel.close()

    def test_texts(self, panel: GamesPanel) -> None:
        """
        Names the folder buttons in tooltips and the new search on its button, explained in its tooltip.

        :param panel: the panel
        :return: None
        """
        # Arrange & Act
        texts: tuple[str, ...] = (
            panel.installed.add.toolTip(),
            panel.installed.remove.toolTip(),
            panel.installed.change.toolTip(),
            panel.installed.find_again.text(),
            panel.installed.find_again.toolTip(),
        )
        # Assert
        assert texts == (
            "Add a folder",
            "Remove the folder",
            "Change the folder",
            "Search again",
            "Search the folders in the list for installed games again",
        )
        assert panel.all.search.placeholderText() == "Search"

    def test_tabs(self, panel: GamesPanel, callbacks: dict[str, MagicMock]) -> None:
        """
        Brings the tab asked for to the front and reports each tab the front changes to.

        :param panel: the panel
        :param callbacks: callback mocks
        :return: None
        """
        # Arrange
        shown: list[QWidget | None] = []
        # Act
        panel.show_tab(tab=GamesTab.ALL)
        shown.append(panel.currentWidget())
        panel.show_tab(tab=GamesTab.INSTALLED)
        shown.append(panel.currentWidget())
        # Assert
        assert shown == [panel.all, panel.installed]
        assert [call.args for call in callbacks["on_tab"].call_args_list] == [(GamesTab.ALL,), (GamesTab.INSTALLED,)]

    def test_executable_icons(self, panel: GamesPanel) -> None:
        """
        Shows each installed game with the icon of its executable, drawn once per file.

        :param panel: the panel
        :return: None
        """
        # Arrange
        executable: Path = Path(sys.executable)
        games: list[InstalledGameView] = [InstalledGameView(name="Python", executable=executable)]
        # Act
        panel.installed.show_games(games=games, selected=0)
        first: QIcon = panel.installed.list.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole)
        panel.installed.show_games(games=games, selected=None)
        second: QIcon = panel.installed.list.model().index(0, 0).data(Qt.ItemDataRole.DecorationRole)
        # Assert
        assert not first.isNull()
        assert first.cacheKey() == second.cacheKey()

    def test_none_found(self, panel: GamesPanel) -> None:
        """
        Invites the user to add a folder when no installed game is found.

        :param panel: the panel
        :return: None
        """
        # Arrange
        panel.installed.show_finding()
        # Act
        panel.installed.show_games(games=[], selected=None)
        shown: QWidget | None = panel.installed.pages.currentWidget()
        # Assert
        assert isinstance(shown, QLabel)
        assert shown.text() == "No games found. Add the folder your games are installed in."
        assert not panel.installed.skeleton.active

    def test_folder_buttons(self, panel: GamesPanel) -> None:
        """
        Allows changing and removing a folder only while one is selected, keeping the selection on a refill.

        :param panel: the panel
        :return: None
        """
        # Arrange
        panel.installed.show_folders(folders=[])
        empty: tuple[bool, bool] = (panel.installed.remove.isEnabled(), panel.installed.change.isEnabled())
        # Act
        panel.installed.show_folders(folders=["C:\\Games", "D:\\Games", "E:\\Games"])
        panel.installed.folder_list.setCurrentRow(2)
        panel.installed.show_folders(folders=["C:\\Games", "D:\\Games"])
        # Assert
        assert empty == (False, False)
        assert (
            panel.installed.folder_list.currentRow(),
            panel.installed.remove.isEnabled(),
            panel.installed.change.isEnabled(),
        ) == (1, True, True)

    def test_dialog_cancelled(
        self, panel: GamesPanel, callbacks: dict[str, MagicMock], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Passes nothing on when the folder dialog is closed without a pick.

        :param panel: the panel
        :param callbacks: callback mocks
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        dialog: MagicMock = MagicMock(return_value="")
        monkeypatch.setattr(target=QFileDialog, name="getExistingDirectory", value=dialog)
        panel.installed.show_folders(folders=["C:\\Games"])
        # Act
        panel.installed.add.click()
        panel.installed.change.click()
        # Assert
        assert dialog.call_count == 2
        assert dialog.call_args.args[1:] == ("Choose a folder with games", "C:\\Games")
        callbacks["on_add_folder"].assert_not_called()
        callbacks["on_change_folder"].assert_not_called()
