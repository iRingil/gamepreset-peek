"""Tests of the CPU, GPU and resolution drop-down choice."""

from typing import Iterator

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QWidget

from app.ui.choice_popup import ChoicePopup
from app.ui.views import ChoiceGroup, ChoiceView

__all__: tuple = ()

_DETECTED: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
_AMD: tuple[str, ...] = (
    "AMD Ryzen 5 3600 6-Core Processor",
    "AMD Ryzen 7 5800X3D 8-Core Processor",
    "AMD Ryzen 9 7950X 16-Core Processor",
)
_INTEL: tuple[str, ...] = (
    "13th Gen Intel(R) Core(TM) i7-13700K",
    "13th Gen Intel(R) Core(TM) i9-13900HX",
    "Intel(R) Core(TM) i5-9600K CPU @ 3.70GHz",
)
# Positions in the whole choice: the detected CPU, then the AMD tab, then the Intel tab.
_FIRST_AMD: int = 1
_FIRST_INTEL: int = 1 + len(_AMD)


class _Popup:
    """Opens a popup and reaches its parts the way a user sees them."""

    def __init__(self, *, qt_app: QApplication, choice: ChoiceView) -> None:
        """
        Open a popup over the choice, recording the positions picked.

        :param qt_app: Qt application
        :param choice: items to choose from
        """
        self.picked: list[int] = []
        self.qt_app: QApplication = qt_app
        # The window the popup belongs to; kept so that it outlives the popup.
        self.owner: QWidget = QWidget()
        self.widget: ChoicePopup = ChoicePopup(
            parent=self.owner,
            choice=choice,
            search_hint="Search",
            detected_mark="Detected",
            on_choose=self.picked.append,
        )
        self.widget.show()
        self.widget.activateWindow()
        qt_app.processEvents()

    @property
    def search(self) -> QLineEdit:
        """
        Get the search field.

        :return: the field
        """
        search: QLineEdit | None = self.widget.findChild(QLineEdit)
        assert search is not None
        return search

    @property
    def tabs(self) -> QTabWidget | None:
        """
        Get the tabs of the bundled items.

        :return: the tabs, None when there are none
        """
        return self.widget.findChild(QTabWidget)

    def titles(self) -> list[str]:
        """
        Get the tab titles.

        :return: titles in tab order
        """
        tabs: QTabWidget | None = self.tabs
        return [] if tabs is None else [tabs.tabText(index) for index in range(tabs.count())]

    def lists(self) -> list[QListWidget]:
        """
        Get every list: the detected items first, then the bundled ones in tab order.

        :return: the lists
        """
        tabs: QTabWidget | None = self.tabs
        pages: list[QWidget | None] = [] if tabs is None else [tabs.widget(index) for index in range(tabs.count())]
        grouped: list[QListWidget] = [page for page in pages if isinstance(page, QListWidget)]
        detected: list[QListWidget] = [view for view in self.widget.findChildren(QListWidget) if view not in grouped]
        return detected + grouped

    @staticmethod
    def shown(*, view: QListWidget) -> list[str]:
        """
        Get the texts of the items a list shows.

        :param view: the list
        :return: texts of the items not hidden
        """
        return [view.item(row).text() for row in range(view.count()) if not view.item(row).isHidden()]

    def type_text(self, *, text: str) -> None:
        """
        Type into the search field.

        :param text: text to type
        :return: None
        """
        QTest.keyClicks(self.search, text)
        self.qt_app.processEvents()


class TestChoicePopup:
    """Tests of ChoicePopup."""

    @pytest.fixture(name="cpus")
    def _cpus(self) -> ChoiceView:
        """
        Offer the detected CPU and the bundled ones in two vendor tabs, the second AMD CPU in use.

        :return: the CPU choice
        """
        return ChoiceView(
            detected=(_DETECTED,),
            groups=(ChoiceGroup(title="AMD", items=_AMD), ChoiceGroup(title="Intel", items=_INTEL)),
            selected=_FIRST_AMD + 1,
        )

    @pytest.fixture(name="popup")
    def _popup(self, qt_app: QApplication, cpus: ChoiceView) -> Iterator[_Popup]:
        """
        Open the CPU choice.

        :param qt_app: Qt application
        :param cpus: the CPU choice
        :return: the open popup
        """
        popup: _Popup = _Popup(qt_app=qt_app, choice=cpus)
        yield popup
        popup.widget.close()

    def test_layout(self, popup: _Popup) -> None:
        """
        Shows the detected items above the bundled ones in tabs, the item in use current in its open tab.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange & Act
        detected, amd, intel = popup.lists()
        tabs: QTabWidget | None = popup.tabs
        # Assert
        assert (popup.shown(view=detected), popup.shown(view=amd), popup.shown(view=intel)) == (
            [_DETECTED],
            list(_AMD),
            list(_INTEL),
        )
        assert popup.titles() == ["AMD", "Intel"]
        assert tabs is not None and tabs.currentWidget() is amd and amd.currentRow() == 1

    def test_detected_mark(self, popup: _Popup) -> None:
        """
        Draws the green check of the detected mark at the right end of a detected item only.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        detected, amd, _ = popup.lists()
        # Act
        image: QImage = detected.grab().toImage()
        bundled: QImage = amd.grab().toImage()
        # Assert
        assert detected.objectName() == "detected"
        assert self._green_columns(image=image)[0] > image.width() // 2
        assert not self._green_columns(image=bundled)

    @staticmethod
    def _green_columns(*, image: QImage) -> list[int]:
        """
        Find the columns of an image with clearly green pixels.

        :param image: the picture of a list
        :return: the columns from left to right
        """
        return [
            x
            for x in range(image.width())
            if any(
                (color := image.pixelColor(x, y)).green() > color.red() + 40 and color.green() > color.blue() + 20
                for y in range(image.height())
            )
        ]

    def test_fit_mark(self, qt_app: QApplication) -> None:
        """
        Draws the fit mark in the link color at the right end of fitting items only, with the hint on hover.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        choice: ChoiceView = ChoiceView(
            detected=("2560x1600",),
            groups=(ChoiceGroup(title="", items=("3840x2160", "1920x1200")),),
            selected=0,
            fitting=frozenset({2}),
            fit_mark="16:10",
            fit_hint="Same shape as your screen",
        )
        popup: _Popup = _Popup(qt_app=qt_app, choice=choice)
        bundled: QListWidget = popup.lists()[1]
        # Act
        image: QImage = bundled.viewport().grab().toImage()
        # Assert
        wide, fitting = (bundled.visualItemRect(bundled.item(row)) for row in range(2))
        assert (self._link_pixels(image=image, row=wide), self._link_pixels(image=image, row=fitting) > 0) == (0, True)
        assert (bundled.item(0).toolTip(), bundled.item(1).toolTip()) == ("", "Same shape as your screen")
        popup.widget.close()

    @staticmethod
    def _link_pixels(*, image: QImage, row: QRect) -> int:
        """
        Count the pixels of the link color in the right half of a row.

        :param image: the picture of a list's viewport
        :param row: the row in the picture
        :return: number of pixels
        """
        link: str = QApplication.palette().color(QPalette.ColorRole.Link).name()
        return sum(
            image.pixelColor(x, y).name() == link
            for x in range(image.width() // 2, image.width())
            for y in range(row.top(), row.bottom() + 1)
        )

    def test_selected_tab_opened(self, qt_app: QApplication, cpus: ChoiceView) -> None:
        """
        Opens the tab of the item in use.

        :param qt_app: Qt application
        :param cpus: the CPU choice
        :return: None
        """
        # Arrange
        choice: ChoiceView = ChoiceView(detected=cpus.detected, groups=cpus.groups, selected=_FIRST_INTEL + 2)
        # Act
        popup: _Popup = _Popup(qt_app=qt_app, choice=choice)
        # Assert
        tabs: QTabWidget | None = popup.tabs
        assert tabs is not None and tabs.currentIndex() == 1 and popup.lists()[2].currentRow() == 2
        popup.widget.close()

    def test_single_group_without_tabs(self, qt_app: QApplication) -> None:
        """
        Shows a single group of bundled items as a plain list, without tabs.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        choice: ChoiceView = ChoiceView(
            detected=(), groups=(ChoiceGroup(title="", items=("NVIDIA GeForce RTX 3050",)),), selected=None
        )
        # Act
        popup: _Popup = _Popup(qt_app=qt_app, choice=choice)
        # Assert
        assert (popup.tabs, [popup.shown(view=view) for view in popup.lists()]) == (
            None,
            [["NVIDIA GeForce RTX 3050"]],
        )
        popup.widget.close()

    def test_detected_only(self, qt_app: QApplication) -> None:
        """
        Offers no search over detected items alone and gives them the keys.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        choice: ChoiceView = ChoiceView(detected=(_DETECTED,), groups=(), selected=0)
        # Act
        popup: _Popup = _Popup(qt_app=qt_app, choice=choice)
        # Assert
        assert (popup.search.isVisible(), qt_app.focusWidget() is popup.lists()[0]) == (False, True)
        popup.widget.close()

    def test_click_picks(self, popup: _Popup) -> None:
        """
        Picks a clicked item by its position in the whole choice and closes the list.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        intel: QListWidget = popup.lists()[2]
        item: QListWidgetItem = intel.item(1)
        # Act
        intel.itemClicked.emit(item)
        # Assert
        assert (popup.picked, popup.widget.isVisible()) == ([_FIRST_INTEL + 1], False)

    def test_pick_once(self, popup: _Popup) -> None:
        """
        Passes one pick on when a click is followed by the activation of the same item.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        detected: QListWidget = popup.lists()[0]
        item: QListWidgetItem = detected.item(0)
        # Act
        detected.itemClicked.emit(item)
        detected.itemActivated.emit(item)
        # Assert
        assert popup.picked == [0]

    def test_search_focused(self, popup: _Popup) -> None:
        """
        Gives the keys to the search field when there are bundled items.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange & Act
        focused: bool = popup.qt_app.focusWidget() is popup.search
        # Assert
        assert (focused, popup.search.placeholderText()) == (True, "Search")

    def test_search_filters_every_tab(self, popup: _Popup) -> None:
        """
        Shows in every tab only the items holding each word, in any order and case, and counts them in the titles.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange & Act
        popup.type_text(text="CORE 7")
        # Assert
        detected, amd, intel = popup.lists()
        assert [popup.shown(view=view) for view in (detected, amd, intel)] == [
            [_DETECTED],
            [_AMD[1], _AMD[2]],
            [_INTEL[0], _INTEL[2]],
        ]
        assert popup.titles() == ["AMD (2)", "Intel (2)"]

    def test_tab_with_matches_opened(self, popup: _Popup) -> None:
        """
        Opens the first tab with matches when the open one has none, its first match current.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange & Act
        popup.type_text(text="13900")
        # Assert
        tabs: QTabWidget | None = popup.tabs
        intel: QListWidget = popup.lists()[2]
        assert popup.titles() == ["AMD (0)", "Intel (1)"]
        assert tabs is not None and tabs.currentWidget() is intel and intel.currentRow() == 1

    def test_no_match(self, popup: _Popup) -> None:
        """
        Keeps the open tab when no tab has a match, and Enter picks nothing.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        popup.type_text(text="pentium")
        # Act
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        # Assert
        tabs: QTabWidget | None = popup.tabs
        assert popup.titles() == ["AMD (0)", "Intel (0)"]
        assert tabs is not None and tabs.currentIndex() == 0 and popup.picked == []

    def test_search_cleared(self, popup: _Popup) -> None:
        """
        Shows every item and the plain tab titles again when the search is cleared.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        popup.type_text(text="ryzen 9")
        # Act
        popup.search.clear()
        # Assert
        assert [popup.shown(view=view) for view in popup.lists()[1:]] == [list(_AMD), list(_INTEL)]
        assert popup.titles() == ["AMD", "Intel"]

    def test_enter_picks_item_in_use(self, popup: _Popup) -> None:
        """
        Picks the item in use on Enter in the search field while the search shows it.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        popup.type_text(text="ryzen")
        # Act
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        # Assert
        assert popup.picked == [_FIRST_AMD + 1]

    def test_enter_picks_first_match(self, popup: _Popup) -> None:
        """
        Picks the first match on Enter when the search hides the item in use.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        popup.type_text(text="i7")
        # Act
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        # Assert
        assert popup.picked == [_FIRST_INTEL]

    def test_down_moves_into_list(self, popup: _Popup) -> None:
        """
        Moves the keys from the search field into the list of the open tab on the Down key.

        :param popup: the CPU choice
        :return: None
        """
        # Arrange
        amd: QListWidget = popup.lists()[1]
        # Act
        QTest.keyClick(popup.search, Qt.Key.Key_Down)
        # Assert
        assert popup.qt_app.focusWidget() is amd
