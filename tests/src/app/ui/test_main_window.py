"""Tests of the main window: what the presenter's calls show and which presenter calls the user's actions make."""

from dataclasses import replace
from pathlib import Path
from queue import Queue
from typing import Iterator
from unittest.mock import MagicMock, create_autospec

import pytest
from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QRect
from PySide6.QtGui import QColor, QFont, QHelpEvent, QImage, QPalette
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeWidget,
)

from app.config import LANGUAGE_NAMES
from app.core.models import ThemeMode
from app.i18n.translator import Translator
from app.ui.choice_popup import ChoicePopup
from app.ui.main_window import MainWindow
from app.ui.presenter import (
    ChoiceGroup,
    ChoiceView,
    HardwareView,
    Hint,
    Presenter,
    ResolutionRow,
    SettingRow,
    SettingsView,
)
from app.ui.theme import Theme

__all__: tuple = ()

_HINT: Hint = Hint(title="Too demanding for this PC", text="Even the lowest settings may stutter at this resolution.")
_SETTINGS: SettingsView = SettingsView(
    title="Baldur's Gate 3",
    subtitle="1920x1080, target 60 FPS",
    position="2 / 3",
    caption="optimal preset",
    rows=(
        SettingRow(name="Shadows", value="High", changed=False),
        SettingRow(name="Textures", value="Ultra", changed=True),
    ),
    count=3,
    index=2,
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

    def lists(self) -> tuple[QListView, QListView]:
        """
        Get the game and resolution lists.

        :return: game list, resolution list
        """
        games, resolutions = (
            view for view in self.widget.findChildren(QListView) if type(view).__name__ == "_ChoiceList"
        )
        return games, resolutions

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
        Get the open CPU or GPU choice.

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
        assert [label.text() for label in window.widget.findChildren(QLabel)][:4] == ["CPU:", "GPU:", "RAM:", "VRAM:"]
        assert (search.placeholderText(), window.table().headerItem().text(1)) == ("Search", "Value")
        assert window.button(text="Show logs").isVisible()

    def test_hardware(self, window: _Window) -> None:
        """
        Shows the CPU and GPU as links, escaping their text, and the memory sizes.

        :param window: the window
        :return: None
        """
        # Arrange & Act
        window.widget.show_hardware(
            hardware=HardwareView(
                cpu="AMD <Ryzen>", gpu="NVIDIA GeForce RTX 4090", memory="32 GB", video_memory="24 GB"
            )
        )
        # Assert
        assert window.label(text='<a href="choose">AMD &lt;Ryzen&gt;</a>') is not None
        assert window.label(text='<a href="choose">NVIDIA GeForce RTX 4090</a>') is not None
        assert (window.label(text="32 GB").isVisible(), window.label(text="24 GB").isVisible()) == (True, True)

    @pytest.mark.parametrize(
        argnames=("link", "action"),
        argvalues=[(0, "open_cpu_choice"), (1, "open_gpu_choice")],
        ids=["cpu", "gpu"],
    )
    def test_hardware_links(self, window: _Window, link: int, action: str) -> None:
        """
        Opens the CPU or GPU choice through the presenter when its link is clicked.

        :param window: the window
        :param link: 0 for the CPU link, 1 for the GPU one
        :param action: presenter method expected
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action=action)
        window.widget.show_hardware(hardware=HardwareView(cpu="CPU", gpu="GPU", memory="", video_memory=""))
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
        games, _ = window.lists()
        window.widget.show_games(names=["Baldur's Gate 3", "MORDHAU"], selected=0)
        window.presenter.reset_mock()
        # Act
        games.setCurrentIndex(games.model().index(1, 0))
        window.child(parent=window.widget, kind=QLineEdit).setText("mord")
        # Assert
        assert games.model().rowCount() == 2
        window.presenter.select_game.assert_called_once_with(index=1)
        window.presenter.search_games.assert_called_once_with(text="mord")

    def test_load_games(self, window: _Window) -> None:
        """
        Shows the "Load games" button on request, which asks the presenter for the list again.

        :param window: the window
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action="load_games")
        window.widget.show_load_games(visible=True)
        button: QPushButton = window.button(text="Load games")
        # Act
        button.click()
        # Assert
        assert button.isVisible()
        method.assert_called_once_with(window.presenter)

    def test_resolution_selection_kept(self, window: _Window) -> None:
        """
        Keeps the selected resolution when only the texts of the rows change, and drops it for other rows.

        :param window: the window
        :return: None
        """
        # Arrange
        _, resolutions = window.lists()
        window.widget.show_resolutions(
            items=[
                ResolutionRow(resolution="3840x2160", warning=_HINT),
                ResolutionRow(resolution="1920x1080", warning=None),
            ]
        )
        resolutions.setCurrentIndex(resolutions.model().index(1, 0))
        window.presenter.reset_mock()
        # Act
        window.widget.show_resolutions(
            items=[
                ResolutionRow(resolution="3840x2160", warning=None),
                ResolutionRow(resolution="1920x1080", warning=None),
            ]
        )
        kept: int = resolutions.currentIndex().row()
        window.widget.show_resolutions(items=[ResolutionRow(resolution="1280x720", warning=None)])
        # Assert
        assert (kept, resolutions.currentIndex().isValid()) == (1, False)
        window.presenter.select_resolution.assert_called_once_with(index=1)

    def test_warning_sign_hint(self, window: _Window) -> None:
        """
        Pops the hint of a warning sign up over the sign only.

        :param window: the window
        :return: None
        """
        # Arrange
        _, resolutions = window.lists()
        window.widget.show_resolutions(items=[ResolutionRow(resolution="3840x2160", warning=_HINT)])
        index: QModelIndex = resolutions.model().index(0, 0)
        row: QRect = resolutions.visualRect(index)
        text_end: int = row.left() + resolutions.fontMetrics().horizontalAdvance("3840x2160 ")
        # Act
        hints: list[str] = []
        for x in (row.left() + 2, text_end + 12):
            position: QPoint = QPoint(x, row.center().y())
            event: QHelpEvent = QHelpEvent(QEvent.Type.ToolTip, position, resolutions.viewport().mapToGlobal(position))
            option: QStyleOptionViewItem = QStyleOptionViewItem()
            option.initFrom(resolutions)
            option.rect = row
            window.delegate(view=resolutions).helpEvent(event, resolutions, option, index)
            hints.append(QToolTip.text())
            QToolTip.hideText()
        # Assert
        assert hints[0] == "" and _HINT.title in hints[1] and _HINT.text in hints[1]

    def test_warning_sign_drawn(self, window: _Window) -> None:
        """
        Draws the amber warning sign after the text of a row that has one, and none on a row without it.

        :param window: the window
        :return: None
        """
        # Arrange
        _, resolutions = window.lists()
        window.widget.show_resolutions(
            items=[
                ResolutionRow(resolution="3840x2160", warning=_HINT),
                ResolutionRow(resolution="1920x1080", warning=None),
            ]
        )
        # Act
        image: QImage = resolutions.viewport().grab().toImage()
        # Assert
        amber_rows: list[int] = []
        for row in range(2):
            area: QRect = resolutions.visualRect(resolutions.model().index(row, 0))
            ratio: float = image.devicePixelRatio()
            colors: list[QColor] = [
                image.pixelColor(round(x * ratio), round(y * ratio))
                for x in range(area.left(), area.right())
                for y in range(area.top(), area.bottom())
            ]
            if any(color.red() == 0xFF and color.green() == 0xC2 and color.blue() == 0x4B for color in colors):
                amber_rows.append(row)
        assert amber_rows == [0]

    def test_settings(self, window: _Window) -> None:
        """
        Shows the preset with the slider on it and the changed values emphasized; a slider move goes to the presenter.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.show_settings(settings=_SETTINGS)
        slider: QSlider = window.child(parent=window.widget, kind=QSlider)
        table: QTreeWidget = window.table()
        option: QStyleOptionViewItem = QStyleOptionViewItem()
        changed: QModelIndex = table.model().index(1, 1)
        # Act
        window.delegate(view=table).initStyleOption(option, changed)
        slider.setValue(3)
        # Assert
        assert (slider.minimum(), slider.maximum(), table.topLevelItemCount()) == (1, 3, 2)
        assert (window.label(text="2 / 3").isVisible(), window.button(text="Back to optimal").isEnabled()) == (
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

    def test_settings_cleared(self, window: _Window) -> None:
        """
        Hides the table and the slider, and offers the "Show settings" button on request.

        :param window: the window
        :return: None
        """
        # Arrange
        method: MagicMock = window.spy(action="show_settings")
        window.widget.show_settings(settings=_SETTINGS)
        # Act
        window.widget.clear_settings()
        window.widget.show_settings_button(visible=True)
        window.button(text="Show settings").click()
        # Assert
        assert (window.table().isVisible(), window.child(parent=window.widget, kind=QSlider).isVisible()) == (
            False,
            False,
        )
        method.assert_called_once_with(window.presenter)

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
        window.button(text="Back to optimal").click()
        # Assert
        method.assert_called_once_with(window.presenter)

    def test_themes_and_language(self, window: _Window) -> None:
        """
        Fills the theme choice and passes the theme and the language the user picks on.

        :param window: the window
        :return: None
        """
        # Arrange
        window.widget.show_themes(names=["Auto", "Light", "Dark"], selected=2)
        themes, languages = window.widget.findChildren(QComboBox)
        # Act
        themes.activated.emit(1)
        languages.activated.emit(list(LANGUAGE_NAMES).index("ru"))
        # Assert
        assert (themes.currentText(), languages.currentText()) == ("Dark", LANGUAGE_NAMES["en"])
        window.presenter.change_theme.assert_called_once_with(index=1)
        window.presenter.change_language.assert_called_once_with(language="ru")

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
