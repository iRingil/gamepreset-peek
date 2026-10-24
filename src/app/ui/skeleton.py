"""Placeholder shapes of content that is not there yet, with a light band sweeping over them while it loads."""

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

__all__: tuple[str, ...] = ("ListSkeleton", "SettingsSkeleton", "Skeleton")

# Opacity of the shapes and of the band's middle, out of 255, in the text color of the palette.
_SHAPE_ALPHA: int = 24
_BAND_ALPHA: int = 52
_SWEEP_MS: int = 1400
_RADIUS: float = 4
# Line height of a text placeholder and the row height of the lists and the settings table.
_LINE: float = 10
_ROW: float = 28


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
        path: QPainterPath = QPainterPath()
        for shape in self.shapes():
            path.addRoundedRect(shape, _RADIUS, _RADIUS)
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
        band: float = max(self.width() * 0.35, 120.0)
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
        shapes: list[QRectF] = []
        left: float = 8
        width: float = self.width() - left * 2
        for row in range(int(self.height() // _ROW)):
            top: float = row * _ROW + (_ROW - _LINE) / 2
            text_left: float = left
            if self._icons:
                shapes.append(QRectF(left, row * _ROW + (_ROW - 16) / 2, 16, 16))
                text_left += 24
            length: float = self._LENGTHS[row % len(self._LENGTHS)] * (width - (text_left - left))
            shapes.append(QRectF(text_left, top, length, _LINE))
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
        width: float = self.width()
        shapes: list[QRectF] = [
            QRectF(0, 10, width * 0.5, 18),
            QRectF(width - 64, 2, 64, 30),
            QRectF(width - 110, 40, 110, _LINE),
            QRectF(0, 76, width - 190, 6),
            QRectF(width - 170, 64, 170, 30),
            QRectF(0, 112, width, _ROW),
        ]
        value_left: float = width * 0.72
        for row in range(int((self.height() - 144) // _ROW)):
            top: float = 144 + row * _ROW + (_ROW - _LINE) / 2
            shapes.append(QRectF(6, top, self._NAME_LENGTHS[row % len(self._NAME_LENGTHS)] * value_left, _LINE))
            value_width: float = self._VALUE_LENGTHS[row % len(self._VALUE_LENGTHS)] * (width - value_left - 6)
            shapes.append(QRectF(value_left + 6, top, value_width, _LINE))
        return shapes
