"""The palette that goes with the style sheet: the colors Qt takes only from a palette, e.g. links, placeholders."""

from PySide6.QtGui import QColor, QPalette

from .color import Color
from .color_map import ColorMap

__all__: tuple[str, ...] = ("Palette",)


class Palette:
    """Builds the palette of a mode; every other role keeps the application's default."""

    # Role, its color group (None for all groups), color id and state.
    _ROLES: tuple[tuple[QPalette.ColorRole, QPalette.ColorGroup | None, str, str | None], ...] = (
        (QPalette.ColorRole.Text, None, "foreground", "icon"),
        (QPalette.ColorRole.Text, QPalette.ColorGroup.Disabled, "foreground", "disabled"),
        (QPalette.ColorRole.Link, None, "primary", None),
        (QPalette.ColorRole.LinkVisited, None, "linkVisited", None),
        (QPalette.ColorRole.PlaceholderText, None, "foreground", "input.placeholder"),
        (QPalette.ColorRole.Link, QPalette.ColorGroup.Disabled, "foreground", "disabledSelectionBackground"),
        (QPalette.ColorRole.LinkVisited, QPalette.ColorGroup.Disabled, "foreground", "disabled"),
    )

    @classmethod
    def build(cls, *, colors: ColorMap) -> QPalette:
        """
        Build the palette of a mode.

        :param colors: colors of the mode
        :return: the palette
        """
        palette: QPalette = QPalette()
        for role, group, color_id, state in cls._ROLES:
            color: Color = colors.color(color_id=color_id, state=state)
            value: QColor = QColor(color.red, color.green, color.blue, color.alpha_byte)
            if group is None:
                palette.setColor(role, value)
            else:
                palette.setColor(group, role, value)
        return palette
