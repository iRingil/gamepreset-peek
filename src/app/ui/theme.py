"""Light and dark mode of the window on the PyQtDarkTheme style."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from app.core.models import ThemeMode
from app.ui.vendor import qdarktheme
from app.ui.views import StatusLevel

__all__: tuple[str, ...] = ("Theme",)

# Lists and tables run their rows up to the frame; a list in a tab page leaves the frame to the tab pane.
# Table rows get a little air, still fitting a long settings list in the smallest window.
# A checkbox gets no underline on hover: it looked like a link.
# Tabs are folder tabs: the selected one is framed on top and at the sides and opens into the pane below it.
# The detected item of a choice, mostly the one in use, still answers the mouse with a stronger selection color.
# The {{name|color}} placeholders take the colors of the theme in use.
_QSS: str = """
QListView, QTreeView {padding:0}
QTreeView::item {padding:0.1em 0}
QTabWidget > QStackedWidget > QAbstractItemView[frameShape=NoFrame] {margin:0;border:none}
QCheckBox:hover {border-bottom:2px solid transparent}
QTabWidget::tab-bar {left:0}
QTabWidget::pane {border-top-left-radius:0}
QTabBar::tab:top {margin:0 0.15em 0 0;padding:0.45em 1.1em;border:1px solid transparent;border-bottom:none;
border-top-left-radius:4px;border-top-right-radius:4px}
QTabBar::tab:top:first, QTabBar::tab:top:only-one {margin-left:0}
QTabBar::tab:top:selected, QTabBar::tab:top:selected:hover:enabled {margin-bottom:-1px;
border-color:{{border|color}};background:{{background|color}}}
QListView#detected::item:selected:hover {background:{{primary|color(state="table.selectionBackground")}}}
"""


class Theme:
    """Applies the PyQtDarkTheme style; with AUTO it follows the Windows app mode, also when it changes."""

    _SCHEMES: dict[ThemeMode, Qt.ColorScheme] = {
        ThemeMode.AUTO: Qt.ColorScheme.Unknown,
        ThemeMode.LIGHT: Qt.ColorScheme.Light,
        ThemeMode.DARK: Qt.ColorScheme.Dark,
    }

    # The theme's own light palette is near white with grey text and faint borders: a steel window holds lighter
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
    }

    # Status line colors on a dark and a light background; an informing line keeps the placeholder text color.
    _STATUS_COLORS: dict[tuple[StatusLevel, bool], str] = {
        (StatusLevel.WARNING, True): "#fdd663",
        (StatusLevel.ERROR, True): "#f28b82",
        (StatusLevel.WARNING, False): "#b06000",
        (StatusLevel.ERROR, False): "#d93025",
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
        # The Qt color scheme still drives the window title bar, which the style sheet can't reach.
        QGuiApplication.styleHints().setColorScheme(cls.scheme(mode=mode))
        # ThemeMode values are the theme names of PyQtDarkTheme.
        colors: dict[str, str | dict[str, str]] = {"[light]": cls._LIGHT_COLORS}
        qdarktheme.setup_theme(theme=mode.value, custom_colors=colors, additional_qss=_QSS)
