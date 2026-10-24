"""Tests of the skeletons shown in place of content that is not there yet."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

# noinspection PyProtectedMember
from app.ui.skeleton import _ROW, _TABLE_HEADER, _TABLE_ROW, _TABLE_TOP, ListSkeleton, SettingsSkeleton, Skeleton
from app.ui.typography import Typography

__all__: tuple = ()


class TestSkeleton:
    """Tests of Skeleton and its layouts."""

    def test_switched(self, qt_app: QApplication) -> None:
        """
        Starts still, moves while active, stops again; the base class draws no shapes.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        skeleton: Skeleton = Skeleton()
        states: list[bool] = [skeleton.active]
        # Act
        skeleton.set_active(active=True)
        skeleton.set_active(active=True)
        qt_app.processEvents()
        states.append(skeleton.active)
        skeleton.set_active(active=False)
        states.append(skeleton.active)
        # Assert
        assert (states, skeleton.shapes()) == ([False, True, False], [])

    def test_list_rows(self, qt_app: QApplication) -> None:
        """
        Lays out a name line per row, after an icon square when the list has icons, within the width.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        plain: ListSkeleton = ListSkeleton(icons=False)
        with_icons: ListSkeleton = ListSkeleton(icons=True)
        for skeleton in (plain, with_icons):
            skeleton.resize(300, Typography.px(ems=_ROW * 5.4))
        # Act
        shapes: tuple[list[QRectF], list[QRectF]] = (plain.shapes(), with_icons.shapes())
        # Assert
        assert (len(shapes[0]), len(shapes[1])) == (5, 10)
        assert all(0 <= shape.left() and shape.right() <= 300 for shape in shapes[0] + shapes[1])
        qt_app.processEvents()

    def test_settings_layout(self, qt_app: QApplication) -> None:
        """
        Lays out the settings panel's parts within the widget, rows down to its bottom, and draws them moving.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        skeleton: SettingsSkeleton = SettingsSkeleton()
        height: int = Typography.px(ems=_TABLE_TOP + _TABLE_HEADER + _TABLE_ROW * 3.4)
        skeleton.resize(600, height)
        skeleton.set_active(active=True)
        # Act
        shapes: list[QRectF] = skeleton.shapes()
        image: QImage = skeleton.grab().toImage()
        skeleton.set_active(active=False)
        # Assert
        assert len(shapes) == 6 + 3 * 2
        assert all(0 <= shape.left() and shape.right() <= 600 and shape.bottom() <= height for shape in shapes)
        assert not image.isNull()
        qt_app.processEvents()
