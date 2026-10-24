"""A big translucent notice filling an empty area: a large exclamation mark over a short line of text."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

from app.ui.icons import Icons
from app.ui.typography import Typography

__all__: tuple[str, ...] = ("Notice",)

# Share of the area's width and height the notice fills, and its opacity.
_SHARE: float = 0.8
_OPACITY: float = 0.3
# Largest text height as a share of the notice's height, and the gap between the mark and the text, in text heights.
_TEXT_SHARE: float = 0.16
_GAP: float = 0.35
# Pixel size the text is measured at before it is scaled to fit.
_MEASURE_PX: int = 100


class Notice(QWidget):
    """Draws a large exclamation mark above a line of text in the accent of the theme, translucent and centered.

    The pair fills most of the widget: the text as large as fits its width, the mark taking the rest of the height."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        """
        Build an empty notice.

        :param parent: widget the notice belongs to
        """
        super().__init__(parent)
        self._text: str = ""

    def set_text(self, *, text: str) -> None:
        """
        Show a line of text under the mark.

        :param text: the line, e.g. "No recommendations"
        :return: None
        """
        self._text = text
        self.update()

    @property
    def text(self) -> str:
        """
        Get the line shown under the mark.

        :return: the line
        """
        return self._text

    def paintEvent(self, event: QPaintEvent) -> None:  # pylint: disable=invalid-name,unused-argument
        """
        Draw the mark and the text, scaled to the widget's size.

        :param event: the paint request
        :return: None
        """
        width: float = self.width() * _SHARE
        height: float = self.height() * _SHARE
        font: QFont = Typography.heading(base=self.font())
        font.setPixelSize(_MEASURE_PX)
        measured: float = max(QFontMetricsF(font).horizontalAdvance(self._text), 1.0)
        text_px: int = max(1, int(min(height * _TEXT_SHARE, width / measured * _MEASURE_PX)))
        font.setPixelSize(text_px)
        text_height: float = QFontMetricsF(font).height()
        mark: float = max(0.0, min(width, height - text_height * (1 + _GAP)))
        top: float = (self.height() - mark - text_height * (1 + _GAP)) / 2
        # The theme sets its accent as the link color.
        color: QColor = self.palette().color(QPalette.ColorRole.Link)
        painter: QPainter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(_OPACITY)
        Icons.paint(
            painter=painter, name="circle-alert", color=color, rect=QRectF((self.width() - mark) / 2, top, mark, mark)
        )
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(
            QRectF(0, top + mark + text_height * _GAP, self.width(), text_height),
            Qt.AlignmentFlag.AlignCenter,
            self._text,
        )
        painter.end()
