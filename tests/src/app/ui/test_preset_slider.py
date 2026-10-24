"""Tests of the quality slider drawn as one segment per preset."""

from typing import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.preset_slider import _FOCUS, _GAP, _MARK, PresetSlider
from app.ui.typography import Typography

__all__: tuple = ()

_WIDTH: int = 424


class TestPresetSlider:
    """Tests of PresetSlider."""

    @pytest.fixture(name="slider")
    def _slider(self, qt_app: QApplication) -> Iterator[PresetSlider]:
        """
        Show a slider over 4 presets at the second one, the third recommended, with its moves recorded.

        :param qt_app: Qt application
        :return: the slider
        """
        slider: PresetSlider = PresetSlider()
        slider.resize(_WIDTH, slider.sizeHint().height())
        slider.set_presets(count=4, index=2, recommended=3)
        slider.show()
        qt_app.processEvents()
        yield slider
        slider.close()

    @staticmethod
    def _center(*, value: int, slider: PresetSlider) -> QPoint:
        """
        Find the middle of a preset's segment: segments start after the focus ring room, 4 of them with 3 gaps.

        :param value: 1-based preset index
        :param slider: the slider
        :return: the point
        """
        left: float = Typography.length(ems=_FOCUS)
        gap: float = Typography.length(ems=_GAP)
        segment: float = (_WIDTH - left * 2 - gap * 3) / 4
        middle: float = slider.height() / 2 - Typography.length(ems=_MARK) * 2
        return QPoint(round(left + (value - 1) * (segment + gap) + segment / 2), round(middle))

    @staticmethod
    def _image(*, slider: PresetSlider) -> QImage:
        """
        Draw the slider.

        :param slider: the slider
        :return: its picture
        """
        return slider.grab().toImage()

    def test_presets_set_quietly(self, slider: PresetSlider) -> None:
        """
        Takes the presets of a game without reporting a move.

        :param slider: the slider
        :return: None
        """
        # Arrange
        moved: MagicMock = MagicMock()
        slider.valueChanged.connect(moved)
        # Act
        slider.set_presets(count=19, index=16, recommended=16)
        # Assert
        assert (slider.minimum(), slider.maximum(), slider.value(), slider.recommended) == (1, 19, 16, 16)
        assert slider.isEnabled()
        moved.assert_not_called()

    def test_single_preset_disabled(self, slider: PresetSlider) -> None:
        """
        Disables a slider over a single preset.

        :param slider: the slider
        :return: None
        """
        # Arrange & Act
        slider.set_presets(count=1, index=1, recommended=1)
        # Assert
        assert (slider.maximum(), slider.isEnabled()) == (1, False)

    def test_click_picks_segment(self, slider: PresetSlider) -> None:
        """
        Moves to the preset of the segment clicked and reports it.

        :param slider: the slider
        :return: None
        """
        # Arrange
        moved: MagicMock = MagicMock()
        slider.valueChanged.connect(moved)
        # Act
        QTest.mouseClick(
            slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._center(value=4, slider=slider)
        )
        # Assert
        assert slider.value() == 4
        moved.assert_called_once_with(4)

    def test_drag(self, slider: PresetSlider) -> None:
        """
        Follows a drag with the left button held, and ignores moves without it.

        :param slider: the slider
        :return: None
        """
        # Arrange
        point: QPointF = QPointF(self._center(value=1, slider=slider))
        held: QMouseEvent = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            point,
            slider.mapToGlobal(point),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        hovering: QMouseEvent = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(self._center(value=4, slider=slider)),
            slider.mapToGlobal(QPointF(self._center(value=4, slider=slider))),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        # Act
        QApplication.sendEvent(slider, held)
        QApplication.sendEvent(slider, hovering)
        QTest.mouseRelease(
            slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._center(value=1, slider=slider)
        )
        # Assert
        assert slider.value() == 1

    def test_right_click_ignored(self, slider: PresetSlider) -> None:
        """
        Leaves the preset alone on a right click.

        :param slider: the slider
        :return: None
        """
        # Arrange & Act
        QTest.mouseClick(
            slider, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, self._center(value=4, slider=slider)
        )
        # Assert
        assert slider.value() == 2

    def test_arrow_keys(self, slider: PresetSlider) -> None:
        """
        Steps to the next preset with the arrow key.

        :param slider: the slider
        :return: None
        """
        # Arrange
        slider.setFocus()
        # Act
        QTest.keyClick(slider, Qt.Key.Key_Right)
        # Assert
        assert slider.value() == 3

    def test_drawn(self, slider: PresetSlider) -> None:
        """
        Draws the handle in the accent color on the current segment and the rest in a faint text color.

        :param slider: the slider
        :return: None
        """
        # Arrange
        accent: QColor = slider.palette().color(QPalette.ColorRole.Link)
        slider.setFocus()
        # Act
        image: QImage = self._image(slider=slider)
        # Assert
        assert image.pixelColor(self._center(value=2, slider=slider)) == accent
        assert image.pixelColor(self._center(value=1, slider=slider)) == accent
        assert image.pixelColor(self._center(value=4, slider=slider)) != accent

    def test_drawn_disabled(self, slider: PresetSlider) -> None:
        """
        Draws a slider over one preset without the accent color.

        :param slider: the slider
        :return: None
        """
        # Arrange
        slider.set_presets(count=1, index=1, recommended=1)
        accent: QColor = slider.palette().color(QPalette.ColorRole.Link)
        # Act
        image: QImage = self._image(slider=slider)
        # Assert
        assert image.pixelColor(QPoint(_WIDTH // 2, slider.height() // 2)) != accent
