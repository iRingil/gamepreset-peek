"""Tests of the main window: what the presenter's calls show and which presenter calls the user's actions make."""

from dataclasses import replace
from pathlib import Path
from queue import Queue
from typing import Iterator
from unittest.mock import MagicMock, create_autospec

import pytest
from PySide6.QtCore import QModelIndex, QObject
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QWidget,
)

from app.config import LANGUAGE_NAMES
from app.core.models import GamesTab, ThemeMode
from app.i18n.translator import Translator
from app.ui.choice_popup import ChoicePopup
from app.ui.cover_view import CoverView
from app.ui.games_panel import GamesPanel
from app.ui.icons import IconButton
from app.ui.main_window import MainWindow
from app.ui.preset_slider import PresetSlider
from app.ui.presenter import Presenter
from app.ui.settings_menu import SettingsMenu
from app.ui.skeleton import SettingsSkeleton
from app.ui.theme import Theme
from app.ui.views import ChoiceGroup, ChoiceView, HardwareView, InstalledGameView, SettingRow, SettingsView

__all__: tuple = ()

_SETTINGS: SettingsView = SettingsView(
    title="Baldur's Gate 3",
    position="2 / 3",
    caption="optimal preset",
    rows=(
        SettingRow(name="Shadows", value="High", changed=False),
        SettingRow(name="Textures", value="Ultra", changed=True),
    ),
    count=3,
    index=2,
    recommended=2,
    optimal=True,
)


class _Window:
    """A main window wired to a presenter mock, with its parts reached the way a user sees them."""

    def __init__(self, *, translator: Translator, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Build the window in English and attach the presenter mock.

        :param translator: English translator
        :param monkeypatch: pytest monkeypatch, for the presenter methods the window calls through the class
        """
        self.presenter: MagicMock = create_autospec(spec=Presenter, instance=True)
        self.monkeypatch: pytest.MonkeyPatch = monkeypatch
        self.widget: MainWindow = MainWindow(log_lines=Queue())
        self.widget.attach(presenter=self.presenter)
        self.widget.apply_language(translator=translator)

    def spy(self, *, action: str) -> MagicMock:
        """
        Replace a presenter method the window passes on as Presenter.<action>, so its call can be checked.

        :param action: method name
        :return: the replacement, called with the presenter
        """
        method: MagicMock = MagicMock()
        self.monkeypatch.setattr(target=Presenter, name=action, value=method)
        return method

    def panel(self) -> GamesPanel:
        """
        Get the game tabs.

        :return: the tabs
        """
        return self.child(parent=self.widget, kind=GamesPanel)

    def games(self) -> QListView:
        """
        Get the list of all games.

        :return: game list
        """
        return self.panel().all.list

    def button(self, *, text: str) -> QPushButton:
        """
        Find a button by its text.

        :param text: button text
        :return: the button
        """
        return next(button for button in self.widget.findChildren(QPushButton) if button.text() == text)

    def label(self, *, text: str) -> QLabel:
        """
        Find a label by its text.

        :param text: label text
        :return: the label
        """
        return next(label for label in self.widget.findChildren(QLabel) if label.text() == text)

    @staticmethod
    def child[W: QObject](*, parent: QObject, kind: type[W]) -> W:
        """
        Find the first child of a kind, failing the test when there is none.

        :param parent: widget to search in
        :param kind: class of the child
        :return: the child
        """
        found: W | None = parent.findChild(kind)
        assert found is not None, f"no {kind.__name__}"
        return found

    @staticmethod
    def delegate(*, view: QAbstractItemView) -> QStyledItemDelegate:
        """
        Get the item delegate of a view.

        :param view: list or table
        :return: its delegate
        """
        delegate: QAbstractItemDelegate = view.itemDelegate()
        assert isinstance(delegate, QStyledItemDelegate)
        return delegate

    def table(self) -> QTreeWidget:
        """
        Get the settings table.

        :return: the table
        """
        return self.child(parent=self.widget, kind=QTreeWidget)

    def popup(self) -> ChoicePopup | None:
        """
        Get the open CPU, GPU or resolution choice.

        :return: the choice, None when none is open
        """
        return next((popup for popup in self.widget.findChildren(ChoicePopup) if popup.isVisible()), None)


class TestMainWindow:
    """Tests of MainWindow."""

    @pytest.fixture(name="translator")
    def _translator(self, locale_dir: Path) -> Translator:
        """
        Translate into English.

        :param locale_dir: folder of the compiled catalogs
        :return: the translator
        """
        return Translator(language="en", locale_dir=locale_dir)

    @pytest.fixture(name="window")
    def _window(
        self, qt_app: QApplication, translator: Translator, monkeypatch: pytest.MonkeyPatch
    ) -> Iterator[_Window]:
        """
        Show the window.

        :param qt_app: Qt application
        :param translator: English translator
        :param monkeypatch: pytest monkeypatch
        :return: the window
        """
        window: _Window = _Window(translator=translator, monkeypatch=monkeypatch)
        window.widget.show()
        qt_app.processEvents()
        yield window
        window.widget.close()

    def test_texts(self, window: _Window) -> None:
        """
        Shows the fixed texts in the language applied.

        :param window: the window
        :return: None
        """
        # Arrange & Act
        search: QLineEdit = window.child(parent=window.widget, kind=QLineEdit)
        # Assert
        assert [label.text() for label in window.widget.findChildren(QLabel)][:5] == [
            "CPU:",
            "GPU:",
            "Resolution:",
            "RAM:",
            "VRAM:",
        ]
        assert (search.placeholderText(), window.table().headerItem().text(1)) == ("Search", "Value")
        assert window.button(text="Show logs").isVisible()

    def test_hardware(self, window: _Window) -> None:
        """
        Shows the CPU, GPU and resolution as links, escaping their text, and the memory sizes.

        :param window: the window
        :return: None
        """
        # Arrange & Act
        window.widget.show_hardware(
            hardware=HardwareView(
                cpu="AMD <Ryzen>",
                gpu="NVIDIA GeForce RTX 4090",
                resolution="2560x1600",
                memory="32 GB",
                video_memory="24 GB",
            )
        )
        # Assert
        assert window.label(text='<a href="choose">AMD &lt;Ryzen&gt;</a>') is not None
        assert window.label(text='<a href="choose">NVIDIA GeForce RTX 4090</a>') is not None
        assert window.label(text='<a href="choose">2560x1600</a>') is not None
        assert (window.label(text="32 GB").isVisible(), window.label(text="24 GB").isVisible()) == (True, True)

    @pytest.mark.parametrize(
        argnames=("link", "action"),
        argvalues=[(0, "open_cpu_choice"), (1, "open_gpu_choice"), (2, "open_resolution_choice")],
        ids=["cpu", "gpu", "resolution"],
    )
    def test_hardware_links(self, window: _Window, link: int, action: str) -> None:
        """
        Opens the CPU, GPU or resolution choice through the presenter when its link is clicked.

        :param window: the window
        :param link: 0 for the CPU link, 1 for the GPU one, 2 for the resolution one
        :param action: presenter method expected
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action=action)
        window.widget.show_hardware(
            hardware=HardwareView(cpu="CPU", gpu="GPU", resolution="1920x1080", memory="", video_memory="")
        )
        links: list[QLabel] = [label for label in window.widget.findChildren(QLabel) if "href" in label.text()]
        # Act
        links[link].linkActivated.emit("choose")
        # Assert
        method.assert_called_once_with(window.presenter)

    def test_offer_opens_choice(self, window: _Window) -> None:
        """
        Opens a choice with a search hint in the UI language; a pick goes to the presenter as a GPU.

        :param window: the window
        :return: None
        """
        # Arrange
        choice: ChoiceView = ChoiceView(
            detected=("NVIDIA GeForce RTX 4060 Laptop GPU",),
            groups=(ChoiceGroup(title="", items=("NVIDIA GeForce RTX 3050",)),),
            selected=1,
        )
        # Act
        window.widget.offer_gpus(choice=choice)
        popup: ChoicePopup | None = window.popup()
        search: QLineEdit | None = None if popup is None else window.child(parent=popup, kind=QLineEdit)
        if search is not None:
            search.returnPressed.emit()
        # Assert
        assert search is not None and search.placeholderText() == "Search"
        window.presenter.choose_gpu.assert_called_once_with(position=1)

    def test_offer_cpus_picks_cpu(self, window: _Window) -> None:
        """
        Passes a pick of the CPU choice to the presenter as a CPU.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.offer_cpus(choice=ChoiceView(detected=("AMD Ryzen 7 7800X3D",), groups=(), selected=0))
        popup: ChoicePopup | None = window.popup()
        assert popup is not None
        view: QListView = window.child(parent=popup, kind=QListView)
        # Act
        view.activated.emit(view.model().index(0, 0))
        # Assert
        window.presenter.choose_cpu.assert_called_once_with(position=0)

    def test_offer_resolutions_picks_resolution(self, window: _Window) -> None:
        """
        Passes a pick of the resolution choice to the presenter as a resolution.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.offer_resolutions(
            choice=ChoiceView(
                detected=("1920x1080",), groups=(ChoiceGroup(title="", items=("3840x2160",)),), selected=0
            )
        )
        popup: ChoicePopup | None = window.popup()
        assert popup is not None
        view: QListView = window.child(parent=popup, kind=QListView)
        # Act
        view.activated.emit(view.model().index(0, 0))
        # Assert
        window.presenter.choose_resolution.assert_called_once_with(position=0)

    def test_empty_offer(self, window: _Window) -> None:
        """
        Opens nothing for a choice without items.

        :param window: the window
        :return: None
        """
        # Arrange & Act
        window.widget.offer_cpus(
            choice=ChoiceView(detected=(), groups=(ChoiceGroup(title="AMD", items=()),), selected=None)
        )
        # Assert
        assert window.popup() is None

    def test_games(self, window: _Window) -> None:
        """
        Fills the game list with the chosen game selected and passes the user's selection and search on.

        :param window: the window
        :return: None
        """
        # Arrange
        games: QListView = window.games()
        window.widget.show_games(names=["Baldur's Gate 3", "MORDHAU"], selected=0)
        window.presenter.reset_mock()
        # Act
        games.setCurrentIndex(games.model().index(1, 0))
        window.child(parent=window.widget, kind=QLineEdit).setText("mord")
        # Assert
        assert games.model().rowCount() == 2
        window.presenter.select_game.assert_called_once_with(index=1)
        window.presenter.search_games.assert_called_once_with(text="mord")

    def test_installed_games(self, window: _Window, tmp_path: Path) -> None:
        """
        Shows the skeleton while searching, then the installed games; a choice and a new search go to the presenter.

        :param window: the window
        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action="find_games")
        panel: GamesPanel = window.panel()
        window.widget.show_finding()
        searching: bool = panel.installed.pages.currentWidget() is panel.installed.skeleton
        # Act
        window.widget.show_installed_games(
            games=[InstalledGameView(name="Mordhau", executable=tmp_path / "Mordhau.exe")], selected=None
        )
        panel.installed.list.setCurrentIndex(panel.installed.list.model().index(0, 0))
        panel.installed.find_again.click()
        # Assert
        assert (searching, panel.installed.pages.currentWidget() is panel.installed.list) == (True, True)
        assert [panel.tabText(0), panel.tabText(1)] == ["My games", "All games"]
        window.presenter.select_installed_game.assert_called_once_with(index=0)
        method.assert_called_once_with(window.presenter)

    def test_tab_and_folders(self, window: _Window, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Brings a game tab to the front, shows the folders and passes tab and folder changes to the presenter.

        :param window: the window
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=QFileDialog, name="getExistingDirectory", value=MagicMock(return_value="E:/Games"))
        panel: GamesPanel = window.panel()
        window.widget.show_folders(folders=["C:\\Games", "D:\\Games"])
        window.presenter.reset_mock()
        # Act
        window.widget.show_tab(tab=GamesTab.ALL)
        shown: QWidget | None = panel.currentWidget()
        panel.setCurrentWidget(panel.installed)
        panel.installed.folder_list.setCurrentRow(1)
        panel.installed.add.click()
        panel.installed.change.click()
        panel.installed.remove.click()
        # Assert
        assert shown is panel.all
        assert [call.kwargs for call in window.presenter.select_tab.call_args_list] == [
            {"tab": GamesTab.ALL},
            {"tab": GamesTab.INSTALLED},
        ]
        assert panel.installed.folder_list.count() == 2
        window.presenter.add_folder.assert_called_once_with(folder="E:/Games")
        window.presenter.change_folder.assert_called_once_with(position=1, folder="E:/Games")
        window.presenter.remove_folder.assert_called_once_with(position=1)

    def test_cover(self, window: _Window) -> None:
        """
        Shows the cover skeleton, moving while the picture loads, then the placeholder for a game without one.

        :param window: the window
        :return: None
        """
        # Arrange
        cover: CoverView = window.child(parent=window.widget, kind=CoverView)
        window.widget.clear_cover(loading=True)
        loading: bool = cover.active
        # Act
        window.widget.show_cover(picture=None)
        # Assert
        assert (loading, cover.active, cover.placeholder) == (True, False, True)

    def test_settings(self, window: _Window) -> None:
        """
        Shows the preset with the slider on it and the changed values emphasized; a slider move goes to the presenter.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.show_settings(settings=_SETTINGS)
        slider: PresetSlider = window.child(parent=window.widget, kind=PresetSlider)
        table: QTreeWidget = window.table()
        option: QStyleOptionViewItem = QStyleOptionViewItem()
        changed: QModelIndex = table.model().index(1, 1)
        # Act
        window.delegate(view=table).initStyleOption(option, changed)
        slider.setValue(3)
        # Assert
        assert (slider.minimum(), slider.maximum(), slider.recommended, table.topLevelItemCount()) == (1, 3, 2, 2)
        assert (window.label(text="2 / 3").isVisible(), window.button(text="Optimal").isEnabled()) == (
            True,
            False,
        )
        assert option.font.bold() and option.palette.color(QPalette.ColorRole.Text) == option.palette.color(
            QPalette.ColorRole.Accent
        )
        window.presenter.move_slider.assert_called_once_with(index=3)

    def test_unchanged_value_plain(self, window: _Window) -> None:
        """
        Draws a value equal to the recommended one in the plain font.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.show_settings(settings=_SETTINGS)
        table: QTreeWidget = window.table()
        option: QStyleOptionViewItem = QStyleOptionViewItem()
        option.font = QFont()
        # Act
        window.delegate(view=table).initStyleOption(option, table.model().index(0, 1))
        # Assert
        assert not option.font.bold()

    @pytest.mark.parametrize(argnames="loading", argvalues=[True, False], ids=["loading", "nothing to wait for"])
    def test_settings_cleared(self, window: _Window, loading: bool) -> None:
        """
        Shows the skeleton in place of the table, the slider and the title, moving only while settings load.

        :param window: the window
        :param loading: whether settings are requested
        :return: None
        """
        # Arrange
        window.widget.show_settings(settings=_SETTINGS)
        skeleton: SettingsSkeleton = window.child(parent=window.widget, kind=SettingsSkeleton)
        # Act
        window.widget.clear_settings(loading=loading)
        # Assert
        assert (window.table().isVisible(), window.child(parent=window.widget, kind=QSlider).isVisible()) == (
            False,
            False,
        )
        assert (skeleton.isVisible(), skeleton.active) == (True, loading)
        assert all(label.text() != "Baldur's Gate 3" for label in window.widget.findChildren(QLabel))

    def test_back_to_optimal(self, window: _Window) -> None:
        """
        Asks the presenter for the recommended preset when the user wants it back.

        :param window: the window
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action="back_to_optimal")
        window.widget.show_settings(settings=replace(_SETTINGS, index=3, optimal=False))
        # Act
        window.button(text="Optimal").click()
        # Assert
        method.assert_called_once_with(window.presenter)

    def test_settings_menu(self, window: _Window, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Opens the settings menu with the theme, language and update switch in use; picks go to the presenter.

        :param window: the window
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=Theme, name="apply", value=MagicMock())
        window.widget.apply_theme(mode=ThemeMode.DARK)
        window.widget.show_auto_update(enabled=False)
        gear: IconButton = window.child(parent=window.widget, kind=IconButton)
        # Act
        gear.click()
        menu: SettingsMenu = window.child(parent=window.widget, kind=SettingsMenu)
        themes: list[IconButton] = menu.findChildren(IconButton)
        languages: QComboBox = window.child(parent=menu, kind=QComboBox)
        update: QCheckBox = window.child(parent=menu, kind=QCheckBox)
        shown: tuple[bool, list[bool], str, bool] = (
            menu.isVisible(),
            [button.isChecked() for button in themes],
            languages.currentText(),
            update.isChecked(),
        )
        themes[2].click()
        update.click()
        languages.activated.emit(list(LANGUAGE_NAMES).index("ru"))
        # Assert
        assert (gear.toolTip(), shown) == ("Settings", (True, [False, True, False], "EN", False))
        window.presenter.change_theme.assert_called_once_with(mode=ThemeMode.LIGHT)
        window.presenter.change_auto_update.assert_called_once_with(enabled=True)
        window.presenter.change_language.assert_called_once_with(language="ru")
        assert not menu.isVisible()

    def test_settings_menu_before_language(self, qt_app: QApplication) -> None:
        """
        Opens no menu before a language is applied: there are no texts to show yet.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        widget: MainWindow = MainWindow(log_lines=Queue())
        gear: IconButton = _Window.child(parent=widget, kind=IconButton)
        # Act
        gear.click()
        qt_app.processEvents()
        # Assert
        assert widget.findChild(SettingsMenu) is None

    def test_status(self, window: _Window) -> None:
        """
        Shows the status line.

        :param window: the window
        :return: None
        """
        # Arrange & Act
        window.widget.show_status(text="Loading…")
        # Assert
        assert window.label(text="Loading…").isVisible()

    def test_warn(self, window: _Window, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Shows a warning dialog over the window.

        :param window: the window
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        warning: MagicMock = MagicMock()
        monkeypatch.setattr(target=QMessageBox, name="warning", value=warning)
        # Act
        window.widget.warn(text="Only NVIDIA graphics cards")
        # Assert
        warning.assert_called_once_with(window.widget, "GamePreset Peek", "Only NVIDIA graphics cards")

    def test_logs_toggled(self, window: _Window) -> None:
        """
        Shows and hides the log panel, naming the next action on the button.

        :param window: the window
        :return: None
        """
        # Arrange
        button: QPushButton = window.button(text="Show logs")
        # Act
        button.click()
        shown: str = button.text()
        button.click()
        # Assert
        assert (shown, button.text()) == ("Hide logs", "Show logs")

    def test_apply_theme(self, window: _Window, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Applies the theme through Theme.

        :param window: the window
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        apply: MagicMock = MagicMock()
        monkeypatch.setattr(target=Theme, name="apply", value=apply)
        # Act
        window.widget.apply_theme(mode=ThemeMode.LIGHT)
        # Assert
        apply.assert_called_once_with(mode=ThemeMode.LIGHT)
