"""Light and dark mode of the window on the PyQtDarkTheme style."""

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QPainterPath, QRegion
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QWidget

from app.core.models import ThemeMode
from app.ui.vendor import qdarktheme

__all__: tuple[str, ...] = ("RoundedView", "Theme")

# Lists and tables run their rows up to the frame; a list in a tab page leaves the frame to the tab pane.
_QSS: str = """
QListView, QTreeView {padding:0}
QTabWidget > QStackedWidget > QAbstractItemView[frameShape=NoFrame] {margin:0;border:none}
"""
# Radius of the cut at a frame's corners: clears its rounded border, while the aliased cut of a larger one shows gaps.
_INNER_RADIUS: float = 1


class RoundedView(QObject):
    """Cuts the rows and the header of a list or table at the rounded corners of its frame, so they keep inside it."""

    def __init__(self, *, view: QAbstractItemView) -> None:
        """
        Watch the parts of the view that reach its frame and cut them each time they are resized or moved.

        :param view: list or table in a theme frame
        """
        super().__init__(view)
        self._view: QAbstractItemView = view
        parts: list[QWidget] = [view.viewport()]
        if isinstance(view, QTreeView):
            parts.append(view.header())
        for part in parts:
            part.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """
        Cut a part of the view to the rounded inside of the frame when its geometry changes.

        :param watched: viewport or header of the view
        :param event: event of the part
        :return: False: the event goes on to the part
        """
        if isinstance(watched, QWidget) and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            inside: QPainterPath = QPainterPath()
            inside.addRoundedRect(QRectF(self._view.contentsRect()), _INNER_RADIUS, _INNER_RADIUS)
            mask: QRegion = QRegion(inside.toFillPolygon().toPolygon())
            watched.setMask(mask.translated(-watched.mapTo(self._view, watched.rect().topLeft())))
        return False


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
