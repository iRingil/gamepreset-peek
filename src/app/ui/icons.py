"""Icons drawn from the bundled SVG files: symbols in the text color of the palette, and language flags."""

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QToolButton, QWidget

from app.config import FLAGS_DIR, ICONS_DIR
from app.ui.typography import Typography

__all__: tuple[str, ...] = ("ICON_SIZE", "IconButton", "Icons")

# Icon size of the buttons and the language flags, in ems.
ICON_SIZE: float = 1.5
# Sizes in ems every icon is drawn at; a widget takes the one nearest to its icon size.
_SIZES: tuple[float, ...] = (1.25, ICON_SIZE, 2.5)


class Icons:
    """Renders the bundled SVG files into icons, sharp at the pixel ratio of the screen."""

    @classmethod
    def symbol(cls, *, name: str, color: QColor, ratio: float) -> QIcon:
        """
        Draw a symbol in a color.

        :param name: file name of the symbol without the extension, e.g. "settings"
        :param color: line color, usually the text color of the palette
        :param ratio: device pixel ratio of the screen
        :return: the icon
        """
        source: str = cls._source(path=ICONS_DIR / f"{name}.svg")
        return cls._icon(svg=source.replace("currentColor", color.name()), ratio=ratio)

    @classmethod
    def flag(cls, *, language: str, ratio: float) -> QIcon:
        """
        Draw the flag of a UI language.

        :param language: language code, e.g. "ru"
        :param ratio: device pixel ratio of the screen
        :return: the icon
        """
        return cls._icon(svg=cls._source(path=FLAGS_DIR / f"{language}.svg"), ratio=ratio)

    @staticmethod
    @cache
    def _source(*, path: Path) -> str:
        """
        Read an SVG file once.

        :param path: the file
        :return: its text
        """
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _icon(*, svg: str, ratio: float) -> QIcon:
        """
        Render an SVG at every icon size, keeping its proportions and centering it.

        :param svg: SVG text
        :param ratio: device pixel ratio of the screen
        :return: the icon
        """
        renderer: QSvgRenderer = QSvgRenderer(QByteArray(svg.encode(encoding="utf-8")))
        shape: QSizeF = renderer.viewBoxF().size()
        icon: QIcon = QIcon()
        for ems in _SIZES:
            size: int = Typography.px(ems=ems)
            pixmap: QPixmap = QPixmap(round(size * ratio), round(size * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(Qt.GlobalColor.transparent)
            drawn: QSizeF = QSizeF(shape).scaled(QSizeF(size, size), Qt.AspectRatioMode.KeepAspectRatio)
            painter: QPainter = QPainter(pixmap)
            renderer.render(
                painter, QRectF((size - drawn.width()) / 2, (size - drawn.height()) / 2, drawn.width(), drawn.height())
            )
            painter.end()
            icon.addPixmap(pixmap)
        return icon


class IconButton(QToolButton):
    """A flat button showing a symbol in the text color of the palette, redrawn when the palette changes."""

    def __init__(self, *, symbol: str, parent: QWidget | None = None) -> None:
        """
        Build the button.

        :param symbol: file name of the symbol without the extension, e.g. "settings"
        :param parent: widget the button belongs to
        """
        super().__init__(parent)
        self._symbol: str = symbol
        self.setAutoRaise(True)
        self.setIconSize(QSize(Typography.px(ems=ICON_SIZE), Typography.px(ems=ICON_SIZE)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redraw()

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """
        Redraw the symbol when the palette changes, e.g. on a switch between the light and the dark theme.

        :param event: the change
        :return: None
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self.redraw()

    def redraw(self) -> None:
        """
        Draw the symbol in the current text color.

        :return: None
        """
        self.setIcon(
            Icons.symbol(
                name=self._symbol,
                color=self.palette().color(QPalette.ColorRole.ButtonText),
                ratio=self.devicePixelRatio(),
            )
        )
