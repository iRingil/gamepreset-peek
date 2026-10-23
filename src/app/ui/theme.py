"""Light and dark mode of the window on the PyQtDarkTheme style."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from app.core.models import ThemeMode
from app.ui.vendor import qdarktheme

__all__: tuple[str, ...] = ("Theme",)

# Lists and tables run their rows up to the frame; a list in a tab page leaves the frame to the tab pane.
# A check box gets no underline on hover: it looked like a link.
_QSS: str = """
QListView, QTreeView {padding:0}
QTabWidget > QStackedWidget > QAbstractItemView[frameShape=NoFrame] {margin:0;border:none}
QCheckBox:hover {border-bottom:2px solid transparent}
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
