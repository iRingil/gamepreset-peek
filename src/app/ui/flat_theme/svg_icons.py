"""The theme's Material icons: SVG text in a color and at an angle, and the files the style sheet points to."""

from functools import cache
from pathlib import Path

from .color import Color

__all__: tuple[str, ...] = ("SvgIcons",)


class SvgIcons:
    """Colors and turns the bundled 24x24 SVG icons, as text or as files for the style sheet's url()."""

    _DIR: Path = Path(__file__).parent / "icons"

    @classmethod
    def source(cls, *, icon_id: str, color: Color, rotate: int = 0) -> str:
        """
        Get the SVG text of an icon drawn in a color.

        :param icon_id: file name of the icon without the extension, e.g. "check_box"
        :param color: fill color
        :param rotate: clockwise turn in degrees
        :return: the SVG text
        """
        turn: str = f' transform="rotate({rotate}, 12, 12)"' if rotate else ""
        return cls._read(icon_id=icon_id).replace("<svg ", f"<svg {color.svg_fill}{turn} ", 1)

    @classmethod
    def file(cls, *, folder: Path, icon_id: str, color: Color, rotate: int = 0) -> Path:
        """
        Write an icon drawn in a color into a folder, unless the folder already holds the same file.

        :param folder: folder of the colored icons, created when missing
        :param icon_id: file name of the icon without the extension, e.g. "check_box"
        :param color: fill color
        :param rotate: clockwise turn in degrees
        :return: path of the file
        """
        path: Path = folder / f"{icon_id}_{color.hex}_{rotate}.svg"
        source: str = cls.source(icon_id=icon_id, color=color, rotate=rotate)
        if not path.is_file() or path.read_text(encoding="utf-8") != source:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        return path

    @classmethod
    @cache
    def _read(cls, *, icon_id: str) -> str:
        """
        Read an icon's SVG file once.

        :param icon_id: file name of the icon without the extension
        :return: its text
        """
        return (cls._DIR / f"{icon_id}.svg").read_text(encoding="utf-8").strip()
