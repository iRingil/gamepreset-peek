"""Placeholder shapes of content that is not there yet, with a light band sweeping over them while it loads."""

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

from app.ui.typography import Typography

__all__: tuple[str, ...] = ("ListSkeleton", "SettingsSkeleton", "Skeleton")

# Opacity of the shapes and of the band's middle, out of 255, in the text color of the palette.
_SHAPE_ALPHA: int = 24
_BAND_ALPHA: int = 52
_SWEEP_MS: int = 1400
# Sizes in ems: corner radius, line height of a text placeholder, row heights of the lists and of the settings table
# with its header.
_RADIUS: float = 0.3
_LINE: float = 0.75
_ROW: float = 2.45
_TABLE_ROW: float = 1.7
_TABLE_HEADER: float = 1.85
# Top of the settings table header in the settings panel, in ems.
_TABLE_TOP: float = 8.6
# Smallest half width of the sweeping band, in ems.
_BAND: float = 9


class Skeleton(QWidget):
    """Draws the shapes a subclass lays out, in a faint text color; active, a light band sweeps across them.

    An inactive skeleton stands still: it marks the place of content nobody waits for yet."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        """
        Build an inactive skeleton.

        :param parent: widget the skeleton belongs to
        """
        super().__init__(parent)
        self._sweep: QVariantAnimation = QVariantAnimation(parent=self)
        self._sweep.setStartValue(0.0)
        self._sweep.setEndValue(1.0)
        self._sweep.setDuration(_SWEEP_MS)
        self._sweep.setLoopCount(-1)
        self._sweep.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._sweep.valueChanged.connect(self.update)

    @property
    def active(self) -> bool:
        """
        Tell whether the band sweeps.

        :return: True while it does
        """
        return self._sweep.state() == QAbstractAnimation.State.Running

    def set_active(self, *, active: bool) -> None:
        """
        Start or stop the band.

        :param active: True while the content loads
        :return: None
        """
        if active and not self.active:
            self._sweep.start()
        elif not active and self.active:
            self._sweep.stop()
        self.update()

    def shapes(self) -> list[QRectF]:
        """
        Lay out the shapes in the widget's rectangle; the base class draws none.

        :return: rectangles drawn with rounded corners
        """
        return []

    def paintEvent(self, event: QPaintEvent) -> None:  # pylint: disable=invalid-name,unused-argument
        """
        Draw the shapes, and the band over them while active.

        :param event: the paint request
        :return: None
        """
        radius: float = Typography.length(ems=_RADIUS)
        path: QPainterPath = QPainterPath()
        for shape in self.shapes():
            path.addRoundedRect(shape, radius, radius)
        painter: QPainter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_shapes(painter=painter, path=path)
        painter.end()

    def paint_shapes(self, *, painter: QPainter, path: QPainterPath) -> None:
        """
        Fill a path in the skeleton color, with the band over it while active.

        :param painter: painter of the widget
        :param path: the shapes
        :return: None
        """
        text: QColor = self.palette().color(QPalette.ColorRole.WindowText)
        painter.fillPath(path, self._faded(color=text, alpha=_SHAPE_ALPHA))
        if not self.active:
            return
        band: float = max(self.width() * 0.35, Typography.length(ems=_BAND))
        middle: float = -band + (self.width() + band * 2) * float(self._sweep.currentValue())
        gradient: QLinearGradient = QLinearGradient(middle - band, 0, middle + band, 0)
        gradient.setColorAt(0, self._faded(color=text, alpha=0))
        gradient.setColorAt(0.5, self._faded(color=text, alpha=_BAND_ALPHA))
        gradient.setColorAt(1, self._faded(color=text, alpha=0))
        painter.fillPath(path, gradient)

    @staticmethod
    def _faded(*, color: QColor, alpha: int) -> QColor:
        """
        Make a color see-through.

        :param color: the color
        :param alpha: opacity out of 255
        :return: the see-through color
        """
        faded: QColor = QColor(color)
        faded.setAlpha(alpha)
        return faded


class ListSkeleton(Skeleton):
    """Rows of a list: an icon square and a name line of a varying length on each."""

    # Name lengths as parts of the free width, repeated down the list.
    _LENGTHS: tuple[float, ...] = (0.62, 0.41, 0.74, 0.5, 0.33, 0.67, 0.46, 0.58)

    def __init__(self, *, icons: bool, parent: QWidget | None = None) -> None:
        """
        Build the skeleton.

        :param icons: True to draw an icon square before each name
        :param parent: widget the skeleton belongs to
        """
        super().__init__(parent=parent)
        self._icons: bool = icons

    def shapes(self) -> list[QRectF]:
        """
        Lay out a row per row height of the widget.

        :return: rectangles drawn with rounded corners
        """
        em: float = Typography.length(ems=1)
        row_height: float = _ROW * em
        line: float = _LINE * em
        icon: float = 1.25 * em
        shapes: list[QRectF] = []
        left: float = 0.6 * em
        width: float = self.width() - left * 2
        for row in range(int(self.height() // row_height)):
            top: float = row * row_height + (row_height - line) / 2
            text_left: float = left
            if self._icons:
                shapes.append(QRectF(left, row * row_height + (row_height - icon) / 2, icon, icon))
                text_left += icon + 0.6 * em
            length: float = self._LENGTHS[row % len(self._LENGTHS)] * (width - (text_left - left))
            shapes.append(QRectF(text_left, top, length, line))
        return shapes


class SettingsSkeleton(Skeleton):
    """The settings panel: the title with the preset number beside it, the slider row and the table."""

    _NAME_LENGTHS: tuple[float, ...] = (0.46, 0.3, 0.58, 0.38, 0.52, 0.26)
    _VALUE_LENGTHS: tuple[float, ...] = (0.5, 0.7, 0.35, 0.6)

    def shapes(self) -> list[QRectF]:
        """
        Lay out the panel's parts in the widget's rectangle.

        :return: rectangles drawn with rounded corners
        """
        em: float = Typography.length(ems=1)
        row_height: float = _TABLE_ROW * em
        line: float = _LINE * em
        inset: float = 0.45 * em
        width: float = self.width()
        shapes: list[QRectF] = [
            QRectF(0, 0.75 * em, width * 0.5, 1.4 * em),
            QRectF(width - 5 * em, 0.15 * em, 5 * em, 2.3 * em),
            QRectF(width - 8.5 * em, 3.1 * em, 8.5 * em, line),
            QRectF(0, 5.85 * em, width - 14.6 * em, 0.45 * em),
            QRectF(width - 13 * em, 4.9 * em, 13 * em, 2.3 * em),
            QRectF(0, _TABLE_TOP * em, width, _TABLE_HEADER * em),
        ]
        rows_top: float = (_TABLE_TOP + _TABLE_HEADER) * em
        value_left: float = width * 0.72
        for row in range(int((self.height() - rows_top) // row_height)):
            top: float = rows_top + row * row_height + (row_height - line) / 2
            name_width: float = self._NAME_LENGTHS[row % len(self._NAME_LENGTHS)] * value_left
            shapes.append(QRectF(inset, top, name_width, line))
            value_width: float = self._VALUE_LENGTHS[row % len(self._VALUE_LENGTHS)] * (width - value_left - inset)
            shapes.append(QRectF(value_left + inset, top, value_width, line))
        return shapes
