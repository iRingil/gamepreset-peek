"""Light and dark mode of the window on the PyQtDarkTheme style."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from app.core.models import ThemeMode
from app.ui.vendor import qdarktheme

__all__: tuple[str, ...] = ("Theme",)

# Lists and tables run their rows up to the frame; a list in a tab page leaves the frame to the tab pane.
# Table rows get a little air, still fitting a long settings list in the smallest window.
# A check box gets no underline on hover: it looked like a link.
# Tabs are folder tabs: the selected one is framed on top and at the sides and opens into the pane below it.
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
"""


class Theme:
    """Applies the PyQtDarkTheme style; with AUTO it follows the Windows app mode, also when it changes."""

    _SCHEMES: dict[ThemeMode, Qt.ColorScheme] = {
        ThemeMode.AUTO: Qt.ColorScheme.Unknown,
        ThemeMode.LIGHT: Qt.ColorScheme.Light,
        ThemeMode.DARK: Qt.ColorScheme.Dark,
    }

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
        qdarktheme.setup_theme(theme=mode.value, additional_qss=_QSS)
