"""Tests of app.ui.flat_theme.theme."""

from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from app.ui.flat_theme import FlatTheme
from app.ui.flat_theme.style import FlatStyle

__all__: tuple = ()

# The window background of each mode at the start of the style sheet.
_DARK: str = "QWidget {background: rgba(32, 33, 36, 1.000)"
_LIGHT: str = "QWidget {background: rgba(17, 34, 51, 1.000)"


class TestFlatTheme:
    """Tests of FlatTheme."""

    @pytest.fixture(name="hints")
    def _hints(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """
        Replace Qt's style hints: the off-screen platform ignores color schemes.

        :param monkeypatch: pytest monkeypatch
        :return: the replacement, reporting no scheme of Windows
        """
        hints: MagicMock = MagicMock()
        hints.colorScheme.return_value = Qt.ColorScheme.Unknown
        monkeypatch.setattr(target=QGuiApplication, name="styleHints", value=lambda: hints)
        return hints

    @pytest.fixture(name="set_style")
    def _set_style(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """
        Catch the style the theme sets, leaving the application's own style for the other tests.

        :param monkeypatch: pytest monkeypatch
        :return: the replaced QApplication.setStyle
        """
        set_style: MagicMock = MagicMock()
        monkeypatch.setattr(target=QApplication, name="setStyle", value=set_style)
        return set_style

    @pytest.fixture(name="theme")
    def _theme(self, tmp_path: Path, set_style: MagicMock) -> FlatTheme:
        """
        Make a theme with an own light window color and an app rule.

        :param tmp_path: temporary directory for the icon files
        :param set_style: replaced QApplication.setStyle
        :return: the theme
        """
        assert set_style is not None
        return FlatTheme(
            colors={Qt.ColorScheme.Light: {"background": "#112233"}},
            extra_qss="QLabel#app {color: {{primary|color}}}",
            icon_dir=tmp_path,
        )

    @staticmethod
    def _follow(*, hints: MagicMock) -> Callable[[Qt.ColorScheme], None]:
        """
        Get what the theme connected to Qt's color scheme changes.

        :param hints: replaced style hints
        :return: the connected callable
        """
        return hints.colorSchemeChanged.connect.call_args.args[0]  # type: ignore[no-any-return]

    def test_apply(self, plain_app: QApplication, hints: MagicMock, set_style: MagicMock, theme: FlatTheme) -> None:
        """
        Sets the mode's scheme, style sheet with the app's rule, palette and the theme's style.

        :param plain_app: Qt application, restored after the test
        :param hints: replaced style hints
        :param set_style: replaced QApplication.setStyle
        :param theme: theme under test
        :return: None
        """
        # Arrange & Act
        theme.apply(scheme=Qt.ColorScheme.Light)
        # Assert
        hints.setColorScheme.assert_called_once_with(Qt.ColorScheme.Light)
        assert plain_app.styleSheet().startswith(_LIGHT)
        assert "QLabel#app {color: rgba(26, 115, 232, 1.000)}" in plain_app.styleSheet()
        assert plain_app.palette().color(QPalette.ColorRole.Link).name() == "#1a73e8"
        assert isinstance(set_style.call_args.args[0], FlatStyle)

    def test_apply_again(
        self, plain_app: QApplication, hints: MagicMock, set_style: MagicMock, theme: FlatTheme
    ) -> None:
        """
        Switches modes, setting the style and connecting to Qt only once.

        :param plain_app: Qt application, restored after the test
        :param hints: replaced style hints
        :param set_style: replaced QApplication.setStyle
        :param theme: theme under test
        :return: None
        """
        # Arrange
        theme.apply(scheme=Qt.ColorScheme.Light)
        # Act
        theme.apply(scheme=Qt.ColorScheme.Dark)
        # Assert
        assert plain_app.styleSheet().startswith(_DARK)
        set_style.assert_called_once()
        hints.colorSchemeChanged.connect.assert_called_once()

    @pytest.mark.parametrize(
        argnames=("windows", "expected"),
        argvalues=[(Qt.ColorScheme.Light, _LIGHT), (Qt.ColorScheme.Unknown, _DARK)],
        ids=["windows light", "windows tells none"],
    )
    def test_apply_auto(
        self, plain_app: QApplication, hints: MagicMock, theme: FlatTheme, windows: Qt.ColorScheme, expected: str
    ) -> None:
        """
        Takes the mode of Windows for Unknown, dark when Windows tells none.

        :param plain_app: Qt application, restored after the test
        :param hints: replaced style hints
        :param theme: theme under test
        :param windows: scheme Qt reports
        :param expected: start of the style sheet
        :return: None
        """
        # Arrange
        hints.colorScheme.return_value = windows
        # Act
        theme.apply(scheme=Qt.ColorScheme.Unknown)
        # Assert
        hints.setColorScheme.assert_called_once_with(Qt.ColorScheme.Unknown)
        assert plain_app.styleSheet().startswith(expected)

    def test_follows_windows(self, plain_app: QApplication, hints: MagicMock, theme: FlatTheme) -> None:
        """
        Switches with Windows while following it.

        :param plain_app: Qt application, restored after the test
        :param hints: replaced style hints
        :param theme: theme under test
        :return: None
        """
        # Arrange
        theme.apply(scheme=Qt.ColorScheme.Unknown)
        # Act
        self._follow(hints=hints)(Qt.ColorScheme.Light)
        # Assert
        assert plain_app.styleSheet().startswith(_LIGHT)

    def test_keeps_chosen_mode(self, plain_app: QApplication, hints: MagicMock, theme: FlatTheme) -> None:
        """
        Ignores scheme changes once a mode is chosen, also the ones the switch itself makes Qt send.

        :param plain_app: Qt application, restored after the test
        :param hints: replaced style hints
        :param theme: theme under test
        :return: None
        """
        # Arrange
        theme.apply(scheme=Qt.ColorScheme.Unknown)
        hints.setColorScheme.side_effect = lambda scheme: self._follow(hints=hints)(Qt.ColorScheme.Light)
        theme.apply(scheme=Qt.ColorScheme.Dark)
        # Act
        self._follow(hints=hints)(Qt.ColorScheme.Light)
        # Assert
        assert plain_app.styleSheet().startswith(_DARK)
