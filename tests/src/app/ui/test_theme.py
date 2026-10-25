"""Tests of app.ui.theme."""

from typing import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QLabel

from app.core.models import ThemeMode
from app.ui.theme import Theme
from app.ui.views import StatusLevel

__all__: tuple = ()


class TestTheme:
    """Tests of Theme."""

    @pytest.mark.parametrize(
        argnames=("mode", "expected"),
        argvalues=[
            (ThemeMode.AUTO, Qt.ColorScheme.Unknown),
            (ThemeMode.LIGHT, Qt.ColorScheme.Light),
            (ThemeMode.DARK, Qt.ColorScheme.Dark),
        ],
        ids=["auto", "light", "dark"],
    )
    def test_scheme(self, mode: ThemeMode, expected: Qt.ColorScheme) -> None:
        """
        Maps AUTO to the scheme Qt takes from Windows and the others to their own scheme.

        :param mode: theme mode
        :param expected: Qt color scheme
        :return: None
        """
        # Arrange & Act
        scheme: Qt.ColorScheme = Theme.scheme(mode=mode)
        # Assert
        assert scheme == expected

    @pytest.mark.parametrize(
        argnames=("level", "background", "expected"),
        argvalues=[
            (StatusLevel.INFO, "#202124", None),
            (StatusLevel.WARNING, "#202124", "#fdd663"),
            (StatusLevel.ERROR, "#202124", "#f28b82"),
            (StatusLevel.INFO, "#f8f9fa", None),
            (StatusLevel.WARNING, "#f8f9fa", "#8a4b00"),
            (StatusLevel.ERROR, "#f8f9fa", "#b3261e"),
        ],
        ids=["dark info", "dark warning", "dark error", "light info", "light warning", "light error"],
    )
    def test_status_color(self, level: StatusLevel, background: str, expected: str | None) -> None:
        """
        Gives warnings and errors a color that reads on the background; an informing line keeps its own.

        :param level: how serious the line is
        :param background: background color
        :param expected: expected text color
        :return: None
        """
        # Arrange & Act
        color: str | None = Theme.status_color(level=level, background=QColor(background))
        # Assert
        assert color == expected

    @pytest.fixture(name="themed")
    def _themed(self, qt_app: QApplication) -> Iterator[QApplication]:
        """
        Give the application back its plain look after a test themes it.

        :param qt_app: Qt application
        :return: the application
        """
        yield qt_app
        qt_app.setStyleSheet("")
        qt_app.setPalette(qt_app.style().standardPalette())

    def test_apply(self, themed: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Sets the color scheme of the mode and a style sheet: roomier tree rows, a detected item's hover.

        :param themed: Qt application, restored after the test
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        hints: MagicMock = MagicMock()
        # The off-screen platform ignores color schemes, so the call itself is checked.
        monkeypatch.setattr(target=QGuiApplication, name="styleHints", value=lambda: hints)
        # Act
        Theme.apply(mode=ThemeMode.DARK)
        # Assert
        hints.setColorScheme.assert_called_once_with(Qt.ColorScheme.Dark)
        assert "QTreeView::item {padding: 0.1em 0}" in themed.styleSheet()
        assert "QListView#detected::item:selected:hover {background: " in themed.styleSheet()

    def test_tab_colors_of_theme(self, themed: QApplication) -> None:
        """
        Fills the color placeholders of the folder tabs with the colors of the theme in use.

        :param themed: Qt application, restored after the test
        :return: None
        """
        # Arrange & Act
        Theme.apply(mode=ThemeMode.LIGHT)
        light: str = themed.styleSheet()
        Theme.apply(mode=ThemeMode.DARK)
        dark: str = themed.styleSheet()
        # Assert
        assert "{{" not in light + dark
        assert "QTabBar::tab:top:selected" in light
        assert light[light.index("QTabBar::tab:top:selected") :] != dark[dark.index("QTabBar::tab:top:selected") :]

    def test_light_palette(self, themed: QApplication) -> None:
        """
        Gives the light theme a steel window, lighter lists and the teal-blue accent as the link color.

        :param themed: Qt application, restored after the test
        :return: None
        """
        # Arrange & Act
        Theme.apply(mode=ThemeMode.LIGHT)
        sheet: str = themed.styleSheet().lower()
        # Assert
        assert themed.palette().color(QPalette.ColorRole.Link).name() == "#0b6b8a"
        assert "qwidget {background: rgba(217, 224, 232, 1.000)" in sheet
        assert "rgba(247, 249, 251, 1.000)" in sheet

    @pytest.mark.parametrize(
        argnames=("mode", "color"),
        argvalues=[(ThemeMode.LIGHT, (61, 74, 90)), (ThemeMode.DARK, (130, 132, 136))],
        ids=["light", "dark"],
    )
    def test_muted_label(self, themed: QApplication, mode: ThemeMode, color: tuple[int, int, int]) -> None:
        """
        Draws a dimmed label in an opaque color of the theme: AA contrast in light mode, the old look in dark mode.

        :param themed: Qt application, restored after the test
        :param mode: theme mode
        :param color: expected text color
        :return: None
        """
        # Arrange
        Theme.apply(mode=mode)
        label: QLabel = QLabel(text="Caption")
        # Act
        Theme.mute(label=label)
        label.ensurePolished()
        # Assert
        assert label.palette().color(label.foregroundRole()).getRgb() == (*color, 255)
        assert themed is not None
