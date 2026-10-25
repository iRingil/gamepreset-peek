"""Tests of app.ui.flat_theme.style."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QStyle

from app.ui.flat_theme.style import FlatStyle

__all__: tuple = ()


class TestFlatStyle:
    """Tests of FlatStyle."""

    @staticmethod
    def _image(*, icon: QIcon, mode: QIcon.Mode = QIcon.Mode.Normal) -> QImage:
        """
        Draw an icon at 24x24.

        :param icon: the icon
        :param mode: icon mode
        :return: the drawn image
        """
        return icon.pixmap(QSize(24, 24), mode).toImage()

    @staticmethod
    def _ink(*, image: QImage, top: bool) -> int:
        """
        Sum the alpha of one half of an image.

        :param image: the image
        :param top: the top half, else the bottom one
        :return: the sum
        """
        rows: range = range(image.height() // 2) if top else range(image.height() // 2, image.height())
        return sum(image.pixelColor(x, y).alpha() for y in rows for x in range(image.width()))

    def test_material_icon(self, plain_app: QApplication) -> None:
        """
        Draws a replaced standard icon square, in the palette's text color, also from a changed copy of the icon.

        :param plain_app: Qt application, restored after the test
        :return: None
        """
        # Arrange
        palette: QPalette = QPalette(plain_app.palette())
        palette.setColor(QPalette.ColorRole.Text, "#ff0000")
        plain_app.setPalette(palette)
        icon: QIcon = FlatStyle().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
        changed: QIcon = QIcon(icon)
        # A change detaches the copy, which makes Qt clone the icon engine.
        changed.setIsMask(True)
        # Act
        pixmap: QPixmap = icon.pixmap(QSize(32, 24))
        image: QImage = self._image(icon=changed)
        # Assert
        assert (pixmap.width(), pixmap.height()) == (24, 24)
        assert image.pixelColor(12, 12).name() == "#ff0000"

    def test_disabled_icon(self, plain_app: QApplication) -> None:
        """
        Draws a disabled icon in the disabled text color.

        :param plain_app: Qt application, restored after the test
        :return: None
        """
        # Arrange
        palette: QPalette = QPalette(plain_app.palette())
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, "#00ff00")
        plain_app.setPalette(palette)
        icon: QIcon = FlatStyle().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
        # Act
        image: QImage = self._image(icon=icon, mode=QIcon.Mode.Disabled)
        # Assert
        assert image.pixelColor(12, 12).name() == "#00ff00"

    def test_turned_icon(self, plain_app: QApplication) -> None:
        """
        Turns an arrow for its direction: the up arrow's ink is in the top half, the down arrow's in the bottom one.

        :param plain_app: Qt application, restored after the test
        :return: None
        """
        # Arrange
        style: FlatStyle = FlatStyle()
        up: QImage = self._image(icon=style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        # Act
        down: QImage = self._image(icon=style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        # Assert
        assert self._ink(image=up, top=True) > self._ink(image=up, top=False)
        assert self._ink(image=down, top=False) > self._ink(image=down, top=True)
        assert plain_app is not None

    def test_other_icon(self, plain_app: QApplication) -> None:
        """
        Leaves a standard icon the theme has no Material one for to the wrapped style.

        :param plain_app: Qt application, restored after the test
        :return: None
        """
        # Arrange
        pixmap: QStyle.StandardPixmap = QStyle.StandardPixmap.SP_MessageBoxWarning
        # Act
        icon: QIcon = FlatStyle().standardIcon(pixmap)
        # Assert
        assert icon.cacheKey() != 0
        assert self._image(icon=icon) == self._image(icon=plain_app.style().standardIcon(pixmap))
