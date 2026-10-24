"""The quality slider over the presets of a game: a stop per preset, the recommended one marked."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSlider, QWidget

from app.ui.typography import Typography

__all__: tuple[str, ...] = ("PresetSlider",)

# Sizes in ems: track thickness, handle and focus ring radii, mark radius, handle outline, widget size.
_TRACK: float = 0.45
_HANDLE: float = 0.6
_FOCUS: float = 0.9
_MARK: float = 0.2
_OUTLINE: float = 0.15
_HEIGHT: float = 2.6
_WIDTH: float = 15
# Gap at a stop between two segments in ems, at most this and at most a quarter of a segment.
_GAP: float = 0.25
# Opacity out of 255 of the segments past the handle, in the text color of the palette.
_REST_ALPHA: int = 48
_FOCUS_ALPHA: int = 70


class PresetSlider(QSlider):
    """A horizontal slider drawn as a track broken into segments; the presets are its stops, the handle on one of them.

    The first preset is the start of the track, the last one its end, and the others are the gaps between the
    segments. Segments up to the handle take the accent color. A dot under a stop marks the recommended preset. A click
    or a drag moves the handle to the stop nearest to the pointer; the arrow keys step through the presets."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        """
        Build the slider over one preset.

        :param parent: widget the slider belongs to
        """
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._recommended: int = 1
        self.setPageStep(1)
        self.setRange(1, 1)
        self.setMinimumHeight(Typography.px(ems=_HEIGHT))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def recommended(self) -> int:
        """
        Get the recommended preset.

        :return: its 1-based index
        """
        return self._recommended

    def set_presets(self, *, count: int, index: int, recommended: int) -> None:
        """
        Show the presets of a game without reporting a move.

        :param count: number of presets
        :param index: 1-based index of the preset shown
        :param recommended: 1-based index of the recommended preset
        :return: None
        """
        self.blockSignals(True)
        self.setRange(1, max(count, 1))
        self.setValue(index)
        self.blockSignals(False)
        self._recommended = recommended
        self.setEnabled(count > 1)
        self.update()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """
        Ask for a row as tall as the handle with its focus ring and the mark below.

        :return: the size
        """
        return QSize(Typography.px(ems=_WIDTH), Typography.px(ems=_HEIGHT))

    def paintEvent(self, event: QPaintEvent) -> None:  # pylint: disable=invalid-name,unused-argument
        """
        Draw the segments, the recommended mark and the handle.

        :param event: the paint request
        :return: None
        """
        palette: QPalette = self.palette()
        # The theme sets its accent as Link; Accent is left to Windows and would differ from the links.
        accent: QColor = palette.color(QPalette.ColorRole.Link)
        rest: QColor = QColor(palette.color(QPalette.ColorRole.WindowText))
        rest.setAlpha(_REST_ALPHA)
        if not self.isEnabled():
            accent = rest
        track: float = Typography.length(ems=_TRACK)
        radius: float = Typography.length(ems=_HANDLE)
        mark_radius: float = Typography.length(ems=_MARK)
        painter: QPainter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        stops: list[float] = self._stops()
        top: float = self._track_top()
        middle: float = top + track / 2
        # Segment i joins the stops of presets i and i + 1 (0-based).
        for i, segment in enumerate(self._segments()):
            painter.setBrush(accent if self.minimum() + i < self.value() else rest)
            painter.drawRoundedRect(segment, track / 2, track / 2)
        if self.maximum() > self.minimum():
            painter.setBrush(accent)
            painter.drawEllipse(
                QPointF(stops[self._recommended - self.minimum()], top + track + radius + mark_radius),
                mark_radius,
                mark_radius,
            )
        handle: QPointF = QPointF(stops[self.value() - self.minimum()], middle)
        if self.hasFocus():
            ring: QColor = QColor(accent)
            ring.setAlpha(_FOCUS_ALPHA)
            painter.setBrush(ring)
            painter.drawEllipse(handle, Typography.length(ems=_FOCUS), Typography.length(ems=_FOCUS))
        painter.setBrush(accent)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Base), Typography.length(ems=_OUTLINE)))
        painter.drawEllipse(handle, radius, radius)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """
        Move the handle to the segment clicked.

        :param event: the click
        :return: None
        """
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setValue(self._value_at(x=event.position().x()))
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """
        Move the handle with a drag.

        :param event: the move
        :return: None
        """
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._value_at(x=event.position().x()))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """
        End a drag; the value is set already.

        :param event: the release
        :return: None
        """
        event.accept()

    def _stops(self) -> list[float]:
        """
        Place a stop per preset evenly from the start of the track to its end, leaving room for the handle at both ends.

        :return: horizontal positions from the first preset to the last; a single preset stands at the start
        """
        count: int = self.maximum() - self.minimum() + 1
        focus: float = Typography.length(ems=_FOCUS)
        step: float = (self.width() - focus * 2) / (count - 1) if count > 1 else 0.0
        return [focus + i * step for i in range(count)]

    def _segments(self) -> list[QRectF]:
        """
        Lay out the segments between neighboring stops, a gap at each stop inside the track.

        :return: segments from the first stop to the last; one whole track for a single preset
        """
        stops: list[float] = self._stops()
        track: float = Typography.length(ems=_TRACK)
        top: float = self._track_top()
        if len(stops) == 1:
            focus: float = Typography.length(ems=_FOCUS)
            return [QRectF(focus, top, self.width() - focus * 2, track)]
        gap: float = min(Typography.length(ems=_GAP), (stops[1] - stops[0]) / 4)
        return [
            QRectF(
                left + (0 if i == 0 else gap / 2),
                top,
                right - left - (0 if i == 0 else gap / 2) - (0 if i == len(stops) - 2 else gap / 2),
                track,
            )
            for i, (left, right) in enumerate(zip(stops, stops[1:]))
        ]

    def _track_top(self) -> float:
        """
        Find the top of the track: the track and the mark below it are centered together.

        :return: vertical position in the widget
        """
        track: float = Typography.length(ems=_TRACK)
        mark: float = Typography.length(ems=_MARK)
        return (self.height() - mark * 2) / 2 - track / 2 - mark

    def _value_at(self, *, x: float) -> int:
        """
        Find the preset of the stop nearest to a point.

        :param x: horizontal position in the widget
        :return: 1-based preset index
        """
        distances: list[float] = [abs(stop - x) for stop in self._stops()]
        return self.minimum() + distances.index(min(distances))
