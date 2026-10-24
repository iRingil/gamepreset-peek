"""Tests of the icons drawn from the bundled SVG files and of the button showing one."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from app.config import UI_LANGUAGES
from app.ui.icons import ICON_SIZE, IconButton, Icons
from app.ui.typography import Typography

__all__: tuple = ()

_RED: QColor = QColor("#ff0000")
_SIZE: int = 32


class _Pixels:
    """Pixel checks on an icon."""

    @staticmethod
    def image(*, icon: QIcon, size: int = _SIZE) -> QImage:
        """
        Render an icon at a size.

        :param icon: the icon
        :param size: logical size in pixels
        :return: the image, with straight (not premultiplied) colors
        """
        pixmap: QPixmap = icon.pixmap(QSize(size, size))
        assert not pixmap.isNull()
        return pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    @classmethod
    def colors(cls, *, icon: QIcon) -> set[str]:
        """
        Collect the colors of the fully opaque pixels of an icon.

        :param icon: the icon
        :return: color names, e.g. "#ff0000"
        """
        image: QImage = cls.image(icon=icon)
        return {
            image.pixelColor(x, y).name()
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() == 255
        }


class TestIcons:
    """Tests of Icons.symbol and Icons.flag."""

    def test_symbol_in_color(self, qt_app: QApplication) -> None:
        """
        Draws a symbol in the color given, with nothing else fully opaque.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange & Act
        icon: QIcon = Icons.symbol(name="settings", color=_RED, ratio=1.0)
        # Assert
        assert qt_app is not None
        assert _Pixels.colors(icon=icon) == {"#ff0000"}

    def test_symbol_at_screen_ratio(self, qt_app: QApplication) -> None:
        """
        Draws the pixmaps at the device pixel ratio given, so they stay sharp on a scaled screen.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange & Act
        icon: QIcon = Icons.symbol(name="sun", color=_RED, ratio=2.0)
        size: int = Typography.px(ems=ICON_SIZE)
        pixmap: QPixmap = icon.pixmap(QSize(size, size), 2.0)
        # Assert
        assert qt_app is not None
        assert (pixmap.devicePixelRatio(), pixmap.width()) == (2.0, size * 2)

    def test_flag_keeps_proportions(self, qt_app: QApplication) -> None:
        """
        Draws a flag 4:3 centered in the square icon: transparent above, its own colors in the middle.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange & Act
        image: QImage = _Pixels.image(icon=Icons.flag(language="ru", ratio=1.0))
        # Assert
        assert qt_app is not None
        assert (image.pixelColor(_SIZE // 2, 1).alpha(), image.pixelColor(_SIZE // 2, _SIZE // 2).name()) == (
            0,
            "#0039a6",
        )

    def test_every_language_has_a_flag(self, qt_app: QApplication) -> None:
        """
        Draws a flag for every UI language.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange & Act
        drawn: list[bool] = [bool(_Pixels.colors(icon=Icons.flag(language=code, ratio=1.0))) for code in UI_LANGUAGES]
        # Assert
        assert qt_app is not None
        assert drawn == [True] * len(UI_LANGUAGES)


class TestIconButton:
    """Tests of IconButton."""

    def test_redrawn_on_palette_change(self, qt_app: QApplication) -> None:
        """
        Draws the symbol in the button text color and again when the palette changes.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        button: IconButton = IconButton(symbol="moon")
        palette: QPalette = QPalette(button.palette())
        palette.setColor(QPalette.ColorRole.ButtonText, _RED)
        before: set[str] = _Pixels.colors(icon=button.icon())
        # Act
        button.setPalette(palette)
        qt_app.processEvents()
        # Assert
        size: int = Typography.px(ems=ICON_SIZE)
        assert (button.iconSize(), button.autoRaise()) == (QSize(size, size), True)
        assert "#ff0000" not in before
        assert _Pixels.colors(icon=button.icon()) == {"#ff0000"}
