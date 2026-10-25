"""Tests of app.ui.flat_theme.svg_icons."""

from pathlib import Path

from app.ui.flat_theme.color import Color
from app.ui.flat_theme.svg_icons import SvgIcons

__all__: tuple = ()


class TestSvgIcons:
    """Tests of SvgIcons."""

    def test_source(self) -> None:
        """
        Draws an icon in a color, turned around its center.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#112233")
        # Act
        source: str = SvgIcons.source(icon_id="check", color=color, rotate=90)
        # Assert
        assert source.startswith('<svg fill="#112233" transform="rotate(90, 12, 12)" ')
        assert source.endswith("</svg>")

    def test_source_unturned(self) -> None:
        """
        Leaves an unturned icon without a transform.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#11223380")
        # Act
        source: str = SvgIcons.source(icon_id="check", color=color)
        # Assert
        assert source.startswith('<svg fill="rgb(17,34,51)" fill-opacity="0.502" width=')
        assert "transform" not in source

    def test_file(self, tmp_path: Path) -> None:
        """
        Writes the icon into a new folder, named by icon, color and turn.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        folder: Path = tmp_path / "icons"
        color: Color = Color.from_hex(text="#112233")
        # Act
        path: Path = SvgIcons.file(folder=folder, icon_id="close", color=color, rotate=180)
        # Assert
        assert path == folder / "close_112233_180.svg"
        assert path.read_text(encoding="utf-8") == SvgIcons.source(icon_id="close", color=color, rotate=180)

    def test_file_rewritten(self, tmp_path: Path) -> None:
        """
        Replaces a file whose text differs, e.g. one left by an older version.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#112233")
        stale: Path = tmp_path / "close_112233_0.svg"
        stale.write_text("<svg/>", encoding="utf-8")
        # Act
        path: Path = SvgIcons.file(folder=tmp_path, icon_id="close", color=color)
        # Assert
        assert path.read_text(encoding="utf-8") == SvgIcons.source(icon_id="close", color=color)

    def test_file_kept(self, tmp_path: Path) -> None:
        """
        Leaves a file that already holds the icon untouched.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#112233")
        path: Path = SvgIcons.file(folder=tmp_path, icon_id="close", color=color)
        written: int = path.stat().st_mtime_ns
        # Act
        SvgIcons.file(folder=tmp_path, icon_id="close", color=color)
        # Assert
        assert path.stat().st_mtime_ns == written
