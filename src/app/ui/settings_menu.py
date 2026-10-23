"""The drop-down settings menu: theme buttons, the language list with flags and the database update switch."""

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QWidget

from app.config import LANGUAGE_NAMES
from app.core.models import ThemeMode
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.icons import ICON_SIZE, IconButton, Icons

__all__: tuple[str, ...] = ("SettingsMenu",)

_PAD: int = 8
# Language codes are shown as two letters, e.g. "RU".
_LANGUAGE_CODE_LENGTH: int = 2


class SettingsMenu(QFrame):
    """A popup under the settings button; a click outside closes it, a language pick too.

    The theme is one of three symbol buttons, the language a list of flags with language codes, the automatic
    database update a check box."""

    # Theme modes in menu order with the symbol and the tooltip of each.
    _THEMES: dict[ThemeMode, tuple[str, UiText]] = {
        ThemeMode.AUTO: ("sun-moon", UiText.THEME_AUTO),
        ThemeMode.DARK: ("moon", UiText.THEME_DARK),
        ThemeMode.LIGHT: ("sun", UiText.THEME_LIGHT),
    }

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        parent: QWidget,
        translator: Translator,
        theme: ThemeMode,
        auto_update: bool,
        on_theme: Callable[[ThemeMode], None],
        on_language: Callable[[str], None],
        on_auto_update: Callable[[bool], None],
    ) -> None:
        """
        Build the menu showing the settings in use.

        :param parent: window the menu belongs to
        :param translator: translator of the UI language, which is the language shown
        :param theme: theme in use
        :param auto_update: whether the database is updated automatically
        :param on_theme: called with the theme the user picks
        :param on_language: called with the code of the language the user picks
        :param on_auto_update: called with the new state when the user switches the database update
        """
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._on_language: Callable[[str], None] = on_language
        grid: QGridLayout = QGridLayout(self)
        grid.setHorizontalSpacing(_PAD * 2)
        grid.addWidget(QLabel(translator.text(item=UiText.THEME), parent=self), 0, 0)
        grid.addLayout(self._theme_buttons(translator=translator, theme=theme, on_theme=on_theme), 0, 1)
        grid.addWidget(QLabel(translator.text(item=UiText.LANGUAGE), parent=self), 1, 0)
        self._languages: QComboBox = QComboBox(parent=self)
        self._languages.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        # The default width counts the text only and cuts the code next to the flag.
        self._languages.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._languages.setMinimumContentsLength(_LANGUAGE_CODE_LENGTH + 2)
        for position, (code, name) in enumerate(LANGUAGE_NAMES.items()):
            self._languages.addItem(Icons.flag(language=code, ratio=self.devicePixelRatio()), code.upper())
            self._languages.setItemData(position, name, Qt.ItemDataRole.ToolTipRole)
        self._languages.setCurrentIndex(list(LANGUAGE_NAMES).index(translator.language))
        # Activated: chosen by the user, not set by the program.
        self._languages.activated.connect(self._pick_language)
        grid.addWidget(self._languages, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self._auto_update: QCheckBox = QCheckBox(translator.text(item=UiText.AUTO_UPDATE), parent=self)
        self._auto_update.setToolTip(translator.text(item=UiText.AUTO_UPDATE_HINT))
        self._auto_update.setChecked(auto_update)
        self._auto_update.toggled.connect(on_auto_update)
        grid.addWidget(self._auto_update, 2, 0, 1, 2)

    def _theme_buttons(
        self, *, translator: Translator, theme: ThemeMode, on_theme: Callable[[ThemeMode], None]
    ) -> QHBoxLayout:
        """
        Make the row of theme buttons, one of them checked.

        :param translator: translator of the UI language, for the tooltips
        :param theme: theme in use
        :param on_theme: called with the theme the user picks
        :return: the row
        """
        row: QHBoxLayout = QHBoxLayout()
        row.setSpacing(0)
        # Right-aligned, like the language list below.
        row.addStretch()
        group: QButtonGroup = QButtonGroup(self)
        modes: list[ThemeMode] = list(self._THEMES)
        for position, (mode, (symbol, hint)) in enumerate(self._THEMES.items()):
            button: IconButton = IconButton(symbol=symbol, parent=self)
            button.setCheckable(True)
            button.setChecked(mode is theme)
            button.setToolTip(translator.text(item=hint))
            group.addButton(button, position)
            row.addWidget(button)
        group.idClicked.connect(lambda position: on_theme(modes[position]))
        return row

    def _pick_language(self, position: int) -> None:
        """
        Close the menu and pass the language picked on; the window re-translates itself, this menu included.

        :param position: position in the language list
        :return: None
        """
        self.close()
        self._on_language(list(LANGUAGE_NAMES)[position])
