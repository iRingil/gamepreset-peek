"""Light and dark mode of the window: the flat theme in the app's colors."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from app.config import THEME_ICONS_DIR
from app.core.models import ThemeMode
from app.ui.flat_theme import FlatTheme
from app.ui.views import StatusLevel

__all__: tuple[str, ...] = ("Theme",)

# Table rows get a little air, still fitting a long settings list in the smallest window.
# The detected item of a choice, mostly the one in use, still answers the mouse with a stronger selection color.
# The settings table, reached with Tab to scroll by keys, shows its focus in the frame: its rows can't be selected.
# Dimmed labels get an opaque color: Qt draws the placeholder text role at half the opacity of the text color.
# The {{name|color}} placeholders take the colors of the theme in use.
_QSS: str = """
QTreeView::item {padding: 0.1em 0}
QListView#detected::item:selected:hover {background: {{primary|color(state="table.selectionBackground")}}}
QTreeView#settings:focus {border-color: {{primary|color}}}
QLabel[muted="true"] {color: {{foreground|color(state="input.placeholder")}}}
"""


class Theme:
    """Applies the flat theme in the app's colors; with AUTO it follows the Windows app mode, also when it changes."""

    _SCHEMES: dict[ThemeMode, Qt.ColorScheme] = {
        ThemeMode.AUTO: Qt.ColorScheme.Unknown,
        ThemeMode.LIGHT: Qt.ColorScheme.Light,
        ThemeMode.DARK: Qt.ColorScheme.Dark,
    }

    # The theme's own light palette is near white with gray text and faint borders: a steel window holds lighter
    # lists and tables, with near-black text and one teal-blue accent (links, slider, selection).
    _LIGHT_COLORS: dict[str, str] = {
        "background": "#d9e0e8",
        "background>list": "#f7f9fb",
        "background>table": "#f7f9fb",
        "background>textarea": "#f7f9fb",
        "foreground": "#0f1b2a",
        "border": "#9fabba",
        "input.background": "#f2f5f8",
        "primary": "#0b6b8a",
        "primary>list.selectionBackground": "#a9d3e3",
        "primary>table.selectionBackground": "#a9d3e3",
        "primary>list.inactiveSelectionBackground": "#c4e0ea",
        "primary>table.inactiveSelectionBackground": "#c4e0ea",
        "statusBar.background": "#c9d2dc",
        "tableSectionHeader.background": "#c6d0db",
        # Dimmed text: 6.8:1 on the window, the AA contrast for text.
        "foreground>input.placeholder": "#3d4a5a",
    }
    # Dimmed text of the dark mode: the theme's text at half opacity on its window, as it always looked.
    _DARK_COLORS: dict[str, str] = {"foreground>input.placeholder": "#828488"}

    # The theme of the whole application; Qt is touched only by apply().
    _FLAT: FlatTheme = FlatTheme(
        colors={Qt.ColorScheme.Light: _LIGHT_COLORS, Qt.ColorScheme.Dark: _DARK_COLORS},
        extra_qss=_QSS,
        icon_dir=THEME_ICONS_DIR,
    )

    # Status line colors on a dark and a light background; an informing line keeps the dimmed text color.
    _STATUS_COLORS: dict[tuple[StatusLevel, bool], str] = {
        (StatusLevel.WARNING, True): "#fdd663",
        (StatusLevel.ERROR, True): "#f28b82",
        (StatusLevel.WARNING, False): "#8a4b00",
        (StatusLevel.ERROR, False): "#b3261e",
    }

    # Green of a confirmation on a dark and a light background.
    _SUCCESS_COLORS: dict[bool, str] = {True: "#81c995", False: "#188038"}

    @classmethod
    def success_color(cls, *, background: QColor) -> str:
        """
        Get the green of a confirmation, e.g. the check of a detected item, that reads well on the background.

        :param background: color the mark is drawn on
        :return: the color as "#rrggbb"
        """
        return cls._SUCCESS_COLORS[background.lightness() < 128]

    @staticmethod
    def mute(*, label: QLabel) -> None:
        """
        Draw a label in the dimmed text color of the theme, e.g. a caption next to its value.

        :param label: the label, not yet shown
        :return: None
        """
        label.setProperty("muted", True)

    @classmethod
    def status_color(cls, *, level: StatusLevel, background: QColor) -> str | None:
        """
        Get the text color of a status line that reads well on the background.

        :param level: how serious the line is
        :param background: color the line is drawn on
        :return: the color as "#rrggbb", None for an informing line
        """
        return cls._STATUS_COLORS.get((level, background.lightness() < 128))

    @classmethod
    def scheme(cls, *, mode: ThemeMode) -> Qt.ColorScheme:
        """
        Get the Qt color scheme of a theme mode.

        :param mode: theme mode
        :return: the scheme; Unknown lets Qt take the one of Windows
        """
        return cls._SCHEMES[mode]

    @classmethod
    def apply(cls, *, mode: ThemeMode) -> None:
        """
        Switch the style and the color scheme of the whole application.

        :param mode: theme mode
        :return: None
        """
        cls._FLAT.apply(scheme=cls.scheme(mode=mode))
