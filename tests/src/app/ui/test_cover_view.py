"""Tests of the box art view: picture, placeholder and skeleton."""

from pathlib import Path
from typing import Iterator

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.ui.cover_view import CoverView

__all__: tuple = ()

_RED: QColor = QColor("#ff0000")


class TestCoverView:
    """Tests of CoverView."""

    @pytest.fixture(name="cover")
    def _cover(self, qt_app: QApplication) -> Iterator[CoverView]:
        """
        Show an empty cover.

        :param qt_app: Qt application
        :return: the cover
        """
        cover: CoverView = CoverView()
        cover.show()
        qt_app.processEvents()
        yield cover
        cover.close()

    @pytest.fixture(name="picture")
    def _picture(self, tmp_path: Path) -> Path:
        """
        Write a red picture of the box art's shape.

        :param tmp_path: temporary directory
        :return: the picture file
        """
        image: QImage = QImage(314, 444, QImage.Format.Format_RGB32)
        image.fill(_RED)
        path: Path = tmp_path / "cover.jpg"
        assert image.save(str(path))
        return path

    def test_box_art_shape(self, cover: CoverView) -> None:
        """
        Keeps the shape of the box art.

        :param cover: the cover
        :return: None
        """
        # Arrange & Act
        ratio: float = cover.height() / cover.width()
        # Assert
        assert ratio == pytest.approx(888 / 628, abs=0.01)

    def test_picture(self, cover: CoverView, picture: Path) -> None:
        """
        Draws a picture over the whole cover and stops the skeleton.

        :param cover: the cover
        :param picture: the picture file
        :return: None
        """
        # Arrange
        cover.clear(loading=True)
        # Act
        cover.show_picture(path=picture)
        image: QImage = cover.grab().toImage()
        # Assert
        assert (cover.picture is not None, cover.placeholder, cover.active) == (True, False, False)
        assert image.pixelColor(QPoint(cover.width() // 2, cover.height() // 2)).red() > 240

    def test_repainted(self, cover: CoverView, picture: Path) -> None:
        """
        Draws the picture again on a repaint.

        :param cover: the cover
        :param picture: the picture file
        :return: None
        """
        # Arrange
        cover.show_picture(path=picture)
        cover.grab()
        # Act
        image: QImage = cover.grab().toImage()
        # Assert
        assert image.pixelColor(QPoint(cover.width() // 2, cover.height() // 2)).red() > 240

    def test_next_picture(self, tmp_path: Path, cover: CoverView, picture: Path) -> None:
        """
        Draws the next picture shown, not the one drawn before.

        :param tmp_path: temporary directory
        :param cover: the cover
        :param picture: the picture file
        :return: None
        """
        # Arrange
        blue: QImage = QImage(314, 444, QImage.Format.Format_RGB32)
        blue.fill(QColor("#0000ff"))
        path: Path = tmp_path / "next.png"
        assert blue.save(str(path))
        cover.show_picture(path=picture)
        cover.grab()
        # Act
        cover.show_picture(path=path)
        image: QImage = cover.grab().toImage()
        # Assert
        assert image.pixelColor(QPoint(cover.width() // 2, cover.height() // 2)).blue() > 240

    @pytest.mark.parametrize(argnames="broken", argvalues=[False, True], ids=["no picture", "broken file"])
    def test_placeholder(self, tmp_path: Path, cover: CoverView, broken: bool) -> None:
        """
        Draws the placeholder for a game without a picture, or for a file that is not a picture.

        :param tmp_path: temporary directory
        :param cover: the cover
        :param broken: True to pass a broken file
        :return: None
        """
        # Arrange
        path: Path | None = None
        if broken:
            broken_file: Path = tmp_path / "broken.jpg"
            broken_file.write_bytes(data=b"<html>")
            path = broken_file
        # Act
        cover.show_picture(path=path)
        cover.grab()
        # Assert
        assert (cover.picture, cover.placeholder) == (None, True)

    @pytest.mark.parametrize(argnames="loading", argvalues=[True, False], ids=["loading", "no game"])
    def test_cleared(self, cover: CoverView, picture: Path, loading: bool) -> None:
        """
        Drops the picture for the skeleton, moving only while a picture loads.

        :param cover: the cover
        :param picture: the picture file
        :param loading: True while a picture is on its way
        :return: None
        """
        # Arrange
        cover.show_picture(path=picture)
        # Act
        cover.clear(loading=loading)
        cover.grab()
        # Assert
        assert (cover.picture, cover.placeholder, cover.active) == (None, False, loading)
