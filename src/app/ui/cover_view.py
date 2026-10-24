"""The box art of the chosen game, a skeleton while it loads and a placeholder when the game has none."""

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPaintEvent, QPalette, QPixmap
from PySide6.QtWidgets import QWidget

from app.ui.icons import Icons
from app.ui.skeleton import Skeleton
from app.ui.typography import Typography

__all__: tuple[str, ...] = ("CoverView",)

# Width of the cover in ems; the height follows the box art's 628 x 888 shape.
_WIDTH: float = 17
_SHAPE: float = 888 / 628
# Corner radius and placeholder symbol size, in ems.
_RADIUS: float = 0.6
_SYMBOL: float = 2.5


class CoverView(Skeleton):
    """A vertical picture with rounded corners; without a picture it is a skeleton, or a placeholder with a symbol."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        """
        Build an empty cover.

        :param parent: widget the cover belongs to
        """
        super().__init__(parent=parent)
        self.setFixedSize(QSize(Typography.px(ems=_WIDTH), Typography.px(ems=_WIDTH * _SHAPE)))
        self._picture: QPixmap | None = None
        self._placeholder: bool = False
        # The picture scaled for the last size and pixel ratio drawn, so a repaint doesn't scale it again.
        self._scaled: tuple[QSize, float, QPixmap] | None = None

    @property
    def picture(self) -> QPixmap | None:
        """
        Get the picture shown.

        :return: the picture, None when there is none
        """
        return self._picture

    @property
    def placeholder(self) -> bool:
        """
        Tell whether the placeholder is shown.

        :return: True when it is
        """
        return self._placeholder

    def show_picture(self, *, path: Path | None) -> None:
        """
        Show a picture file; a missing or broken file shows the placeholder.

        :param path: the picture file, None for the placeholder
        :return: None
        """
        self.set_active(active=False)
        picture: QPixmap | None = None if path is None else QPixmap(str(path))
        self._picture = None if picture is None or picture.isNull() else picture
        self._placeholder = self._picture is None
        self._scaled = None
        self.update()

    def clear(self, *, loading: bool) -> None:
        """
        Show the skeleton.

        :param loading: True while the picture is on its way
        :return: None
        """
        self._picture = None
        self._placeholder = False
        self._scaled = None
        self.set_active(active=loading)

    def shapes(self) -> list[QRectF]:
        """
        Fill the whole cover with one shape.

        :return: the cover's rectangle
        """
        return [QRectF(self.rect())]

    def paintEvent(self, event: QPaintEvent) -> None:  # pylint: disable=invalid-name
        """
        Draw the picture cut to rounded corners, the placeholder, or the skeleton.

        :param event: the paint request
        :return: None
        """
        if self._picture is None and not self._placeholder:
            super().paintEvent(event)
            return
        frame: QPainterPath = QPainterPath()
        radius: float = Typography.length(ems=_RADIUS)
        frame.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter: QPainter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        if self._picture is not None:
            painter.setClipPath(frame)
            ratio: float = self.devicePixelRatioF()
            scaled: QPixmap = self._scaled_picture(picture=self._picture, ratio=ratio)
            left: float = (self.width() - scaled.width() / ratio) / 2
            top: float = (self.height() - scaled.height() / ratio) / 2
            painter.drawPixmap(round(left), round(top), scaled)
        else:
            self.paint_shapes(painter=painter, path=frame)
            symbol: QIcon = Icons.symbol(
                name="image",
                color=self.palette().color(QPalette.ColorRole.PlaceholderText),
                ratio=self.devicePixelRatioF(),
            )
            size: int = Typography.px(ems=_SYMBOL)
            symbol.paint(painter, (self.width() - size) // 2, (self.height() - size) // 2, size, size)
        painter.end()

    def _scaled_picture(self, *, picture: QPixmap, ratio: float) -> QPixmap:
        """
        Scale the picture to cover the widget in device pixels, once per size and pixel ratio.

        :param picture: the picture
        :param ratio: device pixel ratio of the screen
        :return: the scaled picture, its pixel ratio set
        """
        if self._scaled is not None and self._scaled[:2] == (self.size(), ratio):
            return self._scaled[2]
        scaled: QPixmap = picture.scaled(
            round(self.width() * ratio),
            round(self.height() * ratio),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        self._scaled = (self.size(), ratio, scaled)
        return scaled
