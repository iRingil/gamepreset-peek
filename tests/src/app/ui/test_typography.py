"""Tests of the application font and the lengths measured in ems of it."""

from pathlib import Path
from typing import Iterator

import pytest
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QApplication

from app.ui import typography
from app.ui.typography import Typography

__all__: tuple = ()


class TestTypography:
    """Tests of Typography."""

    @pytest.fixture(name="font_kept")
    def _font_kept(self, qt_app: QApplication) -> Iterator[QFont]:
        """
        Give the application back its font after a test changes it.

        :param qt_app: Qt application
        :return: the font the application had
        """
        font: QFont = QFont(qt_app.font())
        yield font
        QApplication.setFont(font)

    @pytest.mark.usefixtures("font_kept")
    def test_install(self) -> None:
        """
        Makes the bundled font the application font at the base size, for lists too.

        :return: None
        """
        # Arrange & Act
        Typography.install()
        # Assert
        assert (QApplication.font().family(), QApplication.font().pointSizeF()) == ("Golos Text", 10)
        assert QApplication.font("QAbstractItemView").family() == "Golos Text"

    def test_install_without_font_file(self, font_kept: QFont, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Keeps the system font family at the base size when the bundled font can't be loaded.

        :param font_kept: the font before the test, restored after it
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=typography, name="FONT_FILE", value=Path("missing.ttf"))
        # Act
        Typography.install()
        # Assert
        assert (QApplication.font().family(), QApplication.font().pointSizeF()) == (font_kept.family(), 10)

    def test_lengths(self, font_kept: QFont) -> None:
        """
        Measures an em as the point size of the application font at the logical DPI of the screen.

        :param font_kept: the font before the test, restored after it
        :return: None
        """
        # Arrange
        font: QFont = QFont(font_kept)
        font.setPointSizeF(12)
        QApplication.setFont(font)
        em: float = 12 * QGuiApplication.primaryScreen().logicalDotsPerInchY() / 72
        # Act
        lengths: tuple[float, int] = (Typography.length(ems=1.5), Typography.px(ems=1.5))
        # Assert
        assert lengths == (pytest.approx(em * 1.5), round(em * 1.5))

    def test_derived_fonts(self, qt_app: QApplication) -> None:
        """
        Makes the semibold font at the same size and the heading semibold and larger.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        base: QFont = QFont(qt_app.font())
        base.setPointSizeF(10)
        # Act
        strong: QFont = Typography.strong(base=base)
        heading: QFont = Typography.heading(base=base)
        # Assert
        assert (strong.weight(), strong.pointSizeF()) == (QFont.Weight.DemiBold, 10)
        assert (heading.weight(), heading.pointSizeF()) == (QFont.Weight.DemiBold, pytest.approx(14))
