"""The proxy style of the theme: Qt's standard icons (dialog buttons, arrows, title bar) drawn as Material icons."""

import shiboken6
from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QIconEngine, QImage, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleOption, QWidget

from .color import Color
from .svg_icons import SvgIcons

__all__: tuple[str, ...] = ("FlatStyle",)

_Pixmap = QStyle.StandardPixmap


class _SvgIconEngine(QIconEngine):
    """Draws a Material icon in the text color of the application palette, at any size."""

    # Copies handed to Qt: Python would free one on return, while Qt deletes it only with its icon.
    _CLONES: list[QIconEngine] = []

    def __init__(self, *, icon_id: str, rotate: int) -> None:
        """
        Keep the icon to draw.

        :param icon_id: file name of the icon without the extension
        :param rotate: clockwise turn in degrees
        """
        super().__init__()
        self._icon_id: str = icon_id
        self._rotate: int = rotate

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        """
        Draw the icon into a rectangle, in the disabled text color for a disabled icon.

        :param painter: painter to draw with
        :param rect: where to draw it
        :param mode: icon mode
        :param state: icon state, the same look for both
        :return: None
        """
        group: QPalette.ColorGroup = (
            QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled else QPalette.ColorGroup.Active
        )
        text: QColor = QGuiApplication.palette().color(group, QPalette.ColorRole.Text)
        color: Color = Color.from_rgba(red=text.red(), green=text.green(), blue=text.blue(), alpha=text.alpha() / 255)
        source: str = SvgIcons.source(icon_id=self._icon_id, color=color, rotate=self._rotate)
        QSvgRenderer(QByteArray(source.encode(encoding="utf-8"))).render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        """
        Draw the icon into a square pixmap that fits the size.

        :param size: requested size
        :param mode: icon mode
        :param state: icon state
        :return: the pixmap
        """
        side: int = min(size.width(), size.height())
        image: QImage = QImage(side, side, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        pixmap: QPixmap = QPixmap.fromImage(image, Qt.ImageConversionFlag.NoFormatConversion)
        painter: QPainter = QPainter(pixmap)
        self.paint(painter, QRect(QPoint(0, 0), QSize(side, side)), mode, state)
        painter.end()
        return pixmap

    def clone(self) -> QIconEngine:
        """
        Copy the engine for a changed copy of its icon, kept referenced until Qt deletes it.

        :return: the copy
        """
        copy: QIconEngine = _SvgIconEngine(icon_id=self._icon_id, rotate=self._rotate)
        self._CLONES[:] = [engine for engine in self._CLONES if shiboken6.isValid(engine)] + [copy]
        return copy


class FlatStyle(QProxyStyle):
    """Wraps the application's style, replacing its standard icons with Material ones."""

    # Material icon and clockwise turn of each standard icon replaced.
    _ICONS: dict[QStyle.StandardPixmap, tuple[str, int]] = {
        _Pixmap.SP_ArrowBack: ("arrow_upward", 270),
        _Pixmap.SP_ArrowDown: ("arrow_upward", 180),
        _Pixmap.SP_ArrowForward: ("arrow_upward", 90),
        _Pixmap.SP_ArrowLeft: ("arrow_upward", 270),
        _Pixmap.SP_ArrowRight: ("arrow_upward", 90),
        _Pixmap.SP_ArrowUp: ("arrow_upward", 0),
        _Pixmap.SP_BrowserReload: ("refresh", 0),
        _Pixmap.SP_BrowserStop: ("close", 0),
        _Pixmap.SP_CommandLink: ("east", 0),
        _Pixmap.SP_DialogAbortButton: ("not_interested", 0),
        _Pixmap.SP_DialogApplyButton: ("check_circle", 0),
        _Pixmap.SP_DialogCancelButton: ("cancel", 0),
        _Pixmap.SP_DialogCloseButton: ("close", 0),
        _Pixmap.SP_DialogDiscardButton: ("delete", 0),
        _Pixmap.SP_DialogHelpButton: ("help", 0),
        _Pixmap.SP_DialogIgnoreButton: ("visibility_off", 0),
        _Pixmap.SP_DialogNoButton: ("not_interested", 0),
        _Pixmap.SP_DialogNoToAllButton: ("close", 0),
        _Pixmap.SP_DialogOkButton: ("check", 0),
        _Pixmap.SP_DialogOpenButton: ("launch", 0),
        _Pixmap.SP_DialogResetButton: ("cleaning_services", 0),
        _Pixmap.SP_DialogRetryButton: ("refresh", 0),
        _Pixmap.SP_DialogSaveAllButton: ("save", 0),
        _Pixmap.SP_DialogSaveButton: ("save", 0),
        _Pixmap.SP_DialogYesButton: ("circle", 0),
        _Pixmap.SP_DialogYesToAllButton: ("done_all", 0),
        _Pixmap.SP_DirHomeIcon: ("home", 0),
        _Pixmap.SP_DockWidgetCloseButton: ("close", 0),
        _Pixmap.SP_FileDialogBack: ("arrow_upward", 270),
        _Pixmap.SP_FileDialogContentsView: ("search", 0),
        _Pixmap.SP_FileDialogDetailedView: ("list", 0),
        _Pixmap.SP_FileDialogEnd: ("drive_file_move_rtl", 0),
        _Pixmap.SP_FileDialogInfoView: ("info", 0),
        _Pixmap.SP_FileDialogListView: ("grid_view", 0),
        _Pixmap.SP_FileDialogNewFolder: ("create_new_folder", 0),
        _Pixmap.SP_FileDialogStart: ("drive_file_move", 0),
        _Pixmap.SP_FileDialogToParent: ("arrow_upward", 0),
        _Pixmap.SP_LineEditClearButton: ("close", 0),
        _Pixmap.SP_MediaPause: ("pause", 0),
        _Pixmap.SP_MediaPlay: ("play_arrow", 0),
        _Pixmap.SP_MediaSeekBackward: ("fast_rewind", 0),
        _Pixmap.SP_MediaSeekForward: ("fast_forward", 0),
        _Pixmap.SP_MediaSkipBackward: ("skip_previous", 0),
        _Pixmap.SP_MediaSkipForward: ("skip_next", 0),
        _Pixmap.SP_MediaStop: ("stop", 0),
        _Pixmap.SP_MediaVolume: ("volume_up", 0),
        _Pixmap.SP_MediaVolumeMuted: ("volume_mute", 0),
        _Pixmap.SP_TabCloseButton: ("close", 0),
        _Pixmap.SP_TitleBarCloseButton: ("close", 0),
        _Pixmap.SP_TitleBarContextHelpButton: ("question_mark", 0),
        _Pixmap.SP_TitleBarMaxButton: ("fullscreen", 0),
        _Pixmap.SP_TitleBarMinButton: ("minimize", 0),
        _Pixmap.SP_TitleBarNormalButton: ("flip_to_front", 0),
        _Pixmap.SP_TitleBarShadeButton: ("chevron_right", 270),
        _Pixmap.SP_TitleBarUnshadeButton: ("chevron_right", 90),
        _Pixmap.SP_ToolBarHorizontalExtensionButton: ("double_arrow", 0),
        _Pixmap.SP_ToolBarVerticalExtensionButton: ("double_arrow", 90),
        _Pixmap.SP_TrashIcon: ("delete", 0),
    }

    def standardIcon(  # pylint: disable=invalid-name
        self, standard_icon: QStyle.StandardPixmap, option: QStyleOption | None = None, widget: QWidget | None = None
    ) -> QIcon:
        """
        Get a standard icon: a Material one where the theme has it, the wrapped style's otherwise.

        :param standard_icon: which icon
        :param option: style option of the widget asking
        :param widget: the widget asking
        :return: the icon
        """
        icon: tuple[str, int] | None = self._ICONS.get(standard_icon)
        if icon is None:
            return super().standardIcon(standard_icon, option, widget)
        return QIcon(_SvgIconEngine(icon_id=icon[0], rotate=icon[1]))
