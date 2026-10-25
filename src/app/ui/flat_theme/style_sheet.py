"""The theme's style sheet: the bundled QSS and the app's own, with the color placeholders filled for one mode."""

import re
from pathlib import Path

from .color import Color
from .color_map import ColorMap
from .svg_icons import SvgIcons

__all__: tuple[str, ...] = ("StyleSheet",)


class StyleSheet:
    """Fills the placeholders of QSS text with the colors of a mode.

    A placeholder is {{id|color}}, {{id|color(state="x")}} or either followed by |url(id="icon") or
    |url(id="icon",rotate=90), which gives the url() of that icon file drawn in the color."""

    _FILE: Path = Path(__file__).parent / "style.qss"
    _PLACEHOLDER: re.Pattern[str] = re.compile(r"\{\{.*?}}")
    _PARTS: re.Pattern[str] = re.compile(
        r"\{\{\s*(?P<id>[\w.-]+)\s*\|\s*color(?:\(\s*state=\"(?P<state>[\w.-]+)\"\s*\))?"
        r"(?:\s*\|\s*url\(\s*id=\"(?P<icon>\w+)\"(?:\s*,\s*rotate=(?P<rotate>\d+))?\s*\))?\s*}}"
    )

    @classmethod
    def render(cls, *, colors: ColorMap, extra_qss: str, icon_dir: Path) -> str:
        """
        Get the style sheet of a mode: the bundled QSS, then the app's.

        :param colors: colors of the mode
        :param extra_qss: the app's QSS, with placeholders of its own
        :param icon_dir: folder for the colored icon files
        :return: the style sheet
        """
        text: str = cls._FILE.read_text(encoding="utf-8") + extra_qss
        return cls._PLACEHOLDER.sub(lambda match: cls._fill(text=match.group(), colors=colors, icon_dir=icon_dir), text)

    @classmethod
    def _fill(cls, *, text: str, colors: ColorMap, icon_dir: Path) -> str:
        """
        Get the value of one placeholder.

        :param text: the placeholder, braces included
        :param colors: colors of the mode
        :param icon_dir: folder for the colored icon files
        :return: the color as rgba(), or the url() of the icon file
        """
        parts: re.Match[str] | None = cls._PARTS.fullmatch(text)
        if parts is None:
            raise ValueError(f"Not a color placeholder: {text}")
        color: Color = colors.color(color_id=parts["id"], state=parts["state"])
        if parts["icon"] is None:
            return color.qss
        path: Path = SvgIcons.file(
            folder=icon_dir, icon_id=parts["icon"], color=color, rotate=int(parts["rotate"] or 0)
        )
        return f"url({path.as_posix()})"
