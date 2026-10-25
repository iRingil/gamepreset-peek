"""Tests of app.ui.flat_theme.palette."""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from app.ui.flat_theme.color_map import ColorMap
from app.ui.flat_theme.palette import Palette

__all__: tuple = ()


class TestPalette:
    """Tests of Palette."""

    def test_build(self, qt_app: QApplication) -> None:
        """
        Sets the text, link and placeholder roles from the colors, disabled ones from their states.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        colors: ColorMap = ColorMap(
            tree={
                "foreground": {
                    "base": "#e4e7eb",
                    "icon": "#010203",
                    "disabled": "#040506",
                    "input.placeholder": "#07080980",
                    "disabledSelectionBackground": "#0a0b0c",
                },
                "primary": "#8ab4f7",
                "linkVisited": "#c58af8",
            }
        )
        # Act
        palette: QPalette = Palette.build(colors=colors)
        # Assert
        assert palette.color(QPalette.ColorRole.Text).name() == "#010203"
        assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name() == "#040506"
        assert palette.color(QPalette.ColorRole.Link).name() == "#8ab4f7"
        assert palette.color(QPalette.ColorRole.LinkVisited).name() == "#c58af8"
        assert palette.color(QPalette.ColorRole.PlaceholderText).getRgb() == (7, 8, 9, 128)
        assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Link).name() == "#0a0b0c"
        assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.LinkVisited).name() == "#040506"
        assert qt_app is not None
