"""Tests of app.ui.theme."""

import pytest
from PySide6.QtCore import Qt

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
