"""Tests of app.ui.theme."""

from typing import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.core.models import ThemeMode
from app.ui.theme import Theme

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
        Sets the color scheme of the mode and a style sheet that runs list rows up to the frame.

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
        assert "QListView, QTreeView {padding:0}" in themed.styleSheet()

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
