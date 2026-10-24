"""The application font, and the font sizes and lengths of the window derived from it."""

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QApplication

from app.config import FONT_FILE

__all__: tuple[str, ...] = ("GAP", "Typography")

# Base font size in points: lists, tables, tabs, buttons and captions all use it.
_POINT_SIZE: float = 10
# Size of the game title and of the preset position, relative to the base font.
_HEADING_SCALE: float = 1.4
# Unit gap between widgets, in ems.
GAP: float = 0.6
_POINTS_PER_INCH: float = 72


class Typography:
    """Installs the bundled font and measures the window in ems of it, so every size follows the text size."""

    @staticmethod
    def install() -> None:
        """
        Make the bundled font the application font; if it can't be loaded, the system font gets the base size.

        :return: None
        """
        font: QFont = QGuiApplication.font()
        families: list[str] = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(FONT_FILE)))
        if families:
            font = QFont(families[0])
        font.setPointSizeF(_POINT_SIZE)
        # Unlike QGuiApplication's, this also drops the fonts Windows gives lists, menus and message boxes.
        QApplication.setFont(font)

    @staticmethod
    def length(*, ems: float) -> float:
        """
        Convert a length in ems of the application font to logical pixels.

        :param ems: the length in ems
        :return: the length in logical pixels
        """
        dpi: float = QGuiApplication.primaryScreen().logicalDotsPerInchY()
        return QGuiApplication.font().pointSizeF() * dpi / _POINTS_PER_INCH * ems

    @classmethod
    def px(cls, *, ems: float) -> int:
        """
        Convert a length in ems of the application font to whole logical pixels.

        :param ems: the length in ems
        :return: the length rounded to whole logical pixels
        """
        return round(cls.length(ems=ems))

    @staticmethod
    def strong(*, base: QFont) -> QFont:
        """
        Make the semibold variant of a font, for values next to their captions.

        :param base: font to start from
        :return: the font
        """
        font: QFont = QFont(base)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    @classmethod
    def heading(cls, *, base: QFont) -> QFont:
        """
        Make the heading font from a base one: larger and semibold.

        :param base: font to start from
        :return: the font
        """
        font: QFont = cls.strong(base=base)
        font.setPointSizeF(base.pointSizeF() * _HEADING_SCALE)
        return font
