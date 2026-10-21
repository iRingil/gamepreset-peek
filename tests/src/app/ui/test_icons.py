"""Tests of app.ui.icons."""

from PySide6.QtGui import QColor, QImage

from app.ui.icons import Icons

__all__: tuple = ()


class TestIcons:
    """Tests of Icons.warning, read back with QImage."""

    _SIZE: int = 32

    def test_warning(self) -> None:
        """
        Draws an amber triangle with a dark rim and exclamation mark on a transparent background.

        :return: None
        """
        # Arrange
        image: QImage = QImage()
        # Act
        image.loadFromData(Icons.warning(size=self._SIZE))
        # Assert
        assert (
            (image.width(), image.height()),
            image.pixelColor(0, 0).alpha(),
            image.pixelColor(9, 24),
            image.pixelColor(16, 15),
            image.pixelColor(16, 28),
        ) == ((32, 32), 0, QColor(0xFF, 0xC2, 0x4B), QColor(0x03, 0x18, 0x30), QColor(0x03, 0x18, 0x30))
