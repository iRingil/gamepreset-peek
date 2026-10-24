"""Tests of the big notice shown in an empty area."""

from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication

from app.ui.notice import Notice

__all__: tuple = ()


class TestNotice:
    """Tests of Notice."""

    def test_drawn_large_and_faint(self, qt_app: QApplication) -> None:
        """
        Draws the mark and the text across most of the widget in a faint accent color, nothing at the edges.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        notice: Notice = Notice()
        notice.set_text(text="No recommendations")
        notice.resize(600, 400)
        background: QColor = notice.palette().color(QPalette.ColorRole.Window)
        # Act
        image: QImage = notice.grab().toImage()
        # Assert
        drawn: list[tuple[int, int]] = [
            (x, y) for x in range(0, 600, 4) for y in range(0, 400, 4) if image.pixelColor(x, y) != background
        ]
        assert notice.text == "No recommendations"
        assert min(x for x, _ in drawn) < 600 * 0.2 and max(x for x, _ in drawn) > 600 * 0.8
        assert all(40 <= y <= 360 for _, y in drawn)
        link: str = notice.palette().color(QPalette.ColorRole.Link).name()
        assert drawn and all(image.pixelColor(x, y).name() != link for x, y in drawn)
        qt_app.processEvents()
