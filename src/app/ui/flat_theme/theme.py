"""The theme applied to the whole application, optionally following the Windows app mode."""

from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QStyleHints
from PySide6.QtWidgets import QApplication

from .color_map import ColorMap
from .default_colors import DEFAULT_COLORS
from .palette import Palette
from .style import FlatStyle
from .style_sheet import StyleSheet

__all__: tuple[str, ...] = ("FlatTheme",)


class FlatTheme:
    """A flat light and dark theme with an app's own colors and QSS on top.

    With Qt.ColorScheme.Unknown it takes the mode of Windows and switches with it."""

    # Mode used when Windows tells none.
    _FALLBACK: Qt.ColorScheme = Qt.ColorScheme.Dark

    def __init__(self, *, colors: Mapping[Qt.ColorScheme, Mapping[str, str]], extra_qss: str, icon_dir: Path) -> None:
        """
        Keep what the theme is made of; nothing is applied until apply().

        :param colors: per mode (Light, Dark), hex colors replacing defaults by "id" or "id>state"
        :param extra_qss: the app's QSS, whose {{id|color}} placeholders take the colors of the mode shown
        :param icon_dir: folder the colored icon files of the style sheet are written to
        """
        self._colors: dict[Qt.ColorScheme, ColorMap] = {
            scheme: ColorMap.overridden(defaults=defaults, overrides=colors.get(scheme, {}))
            for scheme, defaults in DEFAULT_COLORS.items()
        }
        self._extra_qss: str = extra_qss
        self._icon_dir: Path = icon_dir
        # The mode asked for; None while switching, so Qt's own change signals are left alone.
        self._requested: Qt.ColorScheme | None = None
        self._style: FlatStyle | None = None

    def apply(self, *, scheme: Qt.ColorScheme) -> None:
        """
        Switch the whole application to a mode; the first call also sets the theme's style.

        :param scheme: Light or Dark, or Unknown to follow Windows
        :return: None
        """
        hints: QStyleHints = QGuiApplication.styleHints()
        if self._style is None:
            hints.colorSchemeChanged.connect(self._follow)
        self._requested = None
        # The color scheme also drives the window title bar, which the style sheet can't reach.
        hints.setColorScheme(scheme)
        self._requested = scheme
        self._show(scheme=scheme if scheme != Qt.ColorScheme.Unknown else hints.colorScheme())
        if self._style is None:
            style: FlatStyle = FlatStyle()
            # Kept referenced, so Python can't free the style while Qt uses it.
            self._style = style
            QApplication.setStyle(style)

    def _follow(self, scheme: Qt.ColorScheme) -> None:
        """
        Switch with Windows while the theme follows it.

        :param scheme: the scheme Qt now uses
        :return: None
        """
        if self._requested == Qt.ColorScheme.Unknown:
            self._show(scheme=scheme)

    def _show(self, *, scheme: Qt.ColorScheme) -> None:
        """
        Set the style sheet and palette of a mode.

        :param scheme: Light or Dark; Unknown takes the fallback mode
        :return: None
        """
        if scheme not in self._colors:
            scheme = self._FALLBACK
        colors: ColorMap = self._colors[scheme]
        application: QApplication = QApplication.instance()  # type: ignore[assignment]
        application.setStyleSheet(StyleSheet.render(colors=colors, extra_qss=self._extra_qss, icon_dir=self._icon_dir))
        application.setPalette(Palette.build(colors=colors))
