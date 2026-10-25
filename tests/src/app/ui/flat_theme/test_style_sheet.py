"""Tests of app.ui.flat_theme.style_sheet."""

import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from app.ui.flat_theme.color_map import ColorMap
from app.ui.flat_theme.default_colors import DEFAULT_COLORS
from app.ui.flat_theme.style_sheet import StyleSheet

__all__: tuple = ()


class TestStyleSheet:
    """Tests of StyleSheet."""

    @pytest.fixture(name="colors")
    def _colors(self) -> ColorMap:
        """
        Give the default dark colors.

        :return: the colors
        """
        return ColorMap(tree=DEFAULT_COLORS[Qt.ColorScheme.Dark])

    @pytest.mark.parametrize(argnames="scheme", argvalues=list(DEFAULT_COLORS), ids=["dark", "light"])
    def test_render_bundled(self, tmp_path: Path, scheme: Qt.ColorScheme) -> None:
        """
        Leaves no placeholder of the bundled QSS unfilled in either mode, and writes each icon file it points to.

        :param tmp_path: temporary directory
        :param scheme: mode
        :return: None
        """
        # Arrange
        colors: ColorMap = ColorMap(tree=DEFAULT_COLORS[scheme])
        # Act
        sheet: str = StyleSheet.render(colors=colors, extra_qss="", icon_dir=tmp_path)
        # Assert
        assert "{{" not in sheet
        assert all(Path(path).is_file() for path in re.findall(pattern=r"url\(([^)]+)\)", string=sheet))

    def test_render_extra(self, tmp_path: Path, colors: ColorMap) -> None:
        """
        Appends the app's QSS after the bundled one, its placeholders filled too.

        :param tmp_path: temporary directory
        :param colors: dark colors
        :return: None
        """
        # Arrange
        extra: str = 'QLabel {color: {{ foreground | color(state="disabled") }}}'
        # Act
        sheet: str = StyleSheet.render(colors=colors, extra_qss=extra, icon_dir=tmp_path)
        # Assert
        assert sheet.endswith("QLabel {color: rgba(228, 231, 235, 0.400)}")

    def test_render_url(self, tmp_path: Path, colors: ColorMap) -> None:
        """
        Turns an icon placeholder into the url() of the icon file drawn in the color.

        :param tmp_path: temporary directory
        :param colors: dark colors
        :return: None
        """
        # Arrange
        extra: str = 'QCheckBox::indicator {image: {{primary|color|url(id="check_box", rotate=90)}}}'
        # Act
        sheet: str = StyleSheet.render(colors=colors, extra_qss=extra, icon_dir=tmp_path)
        # Assert
        assert sheet.endswith(f"{{image: url({(tmp_path / 'check_box_8ab4f7_90.svg').as_posix()})}}")

    @pytest.mark.parametrize(
        argnames="placeholder",
        argvalues=["{{primary}}", "{{primary|url(id='x')}}", "{{primary|color(state=disabled)}}"],
        ids=["no filter", "no color", "unquoted state"],
    )
    def test_render_malformed(self, tmp_path: Path, colors: ColorMap, placeholder: str) -> None:
        """
        Refuses a placeholder outside the template's forms.

        :param tmp_path: temporary directory
        :param colors: dark colors
        :param placeholder: malformed placeholder
        :return: None
        """
        # Act & Assert
        with pytest.raises(expected_exception=ValueError, match="Not a color placeholder"):
            StyleSheet.render(colors=colors, extra_qss=f"QLabel {{color: {placeholder}}}", icon_dir=tmp_path)
