"""Tests of the settings menu: what it shows and which callbacks the user's picks make."""

from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QWidget

from app.config import LANGUAGE_NAMES
from app.core.models import ThemeMode
from app.i18n.translator import Translator
from app.ui.icons import IconButton
from app.ui.settings_menu import SettingsMenu

__all__: tuple = ()


class _Menu:
    """A settings menu in Russian over callback mocks, with its parts reached the way a user sees them."""

    def __init__(self, *, parent: QWidget, translator: Translator) -> None:
        """
        Open the menu with the dark theme and automatic updates on.

        :param parent: window the menu belongs to
        :param translator: Russian translator
        """
        self.on_theme: MagicMock = MagicMock()
        self.on_language: MagicMock = MagicMock()
        self.on_auto_update: MagicMock = MagicMock()
        self.widget: SettingsMenu = SettingsMenu(
            parent=parent,
            translator=translator,
            theme=ThemeMode.DARK,
            auto_update=True,
            on_theme=self.on_theme,
            on_language=self.on_language,
            on_auto_update=self.on_auto_update,
        )
        self.widget.show()

    def themes(self) -> list[IconButton]:
        """
        Get the theme buttons in menu order.

        :return: the buttons
        """
        return self.widget.findChildren(IconButton)

    def languages(self) -> QComboBox:
        """
        Get the language list.

        :return: the list
        """
        found: QComboBox | None = self.widget.findChild(QComboBox)
        assert found is not None
        return found

    def update(self) -> QCheckBox:
        """
        Get the database update switch.

        :return: the checkbox
        """
        found: QCheckBox | None = self.widget.findChild(QCheckBox)
        assert found is not None
        return found


class TestSettingsMenu:
    """Tests of SettingsMenu."""

    @pytest.fixture(name="menu")
    def _menu(self, qt_app: QApplication, locale_dir: Path) -> Iterator[_Menu]:
        """
        Open the menu over a parent widget.

        :param qt_app: Qt application
        :param locale_dir: folder of the compiled catalogs
        :return: the menu
        """
        parent: QWidget = QWidget()
        parent.show()
        menu: _Menu = _Menu(parent=parent, translator=Translator(language="ru", locale_dir=locale_dir))
        qt_app.processEvents()
        yield menu
        menu.widget.close()
        parent.close()

    def test_shown(self, menu: _Menu) -> None:
        """
        Shows the captions, the theme buttons with the theme in use checked, the language in use and the switch.

        :param menu: the menu
        :return: None
        """
        # Arrange & Act
        captions: list[str] = [label.text() for label in menu.widget.findChildren(QLabel)]
        themes: list[tuple[str, bool]] = [(button.toolTip(), button.isChecked()) for button in menu.themes()]
        languages: QComboBox = menu.languages()
        codes: list[str] = [languages.itemText(position) for position in range(languages.count())]
        names: list[str] = [
            languages.itemData(position, Qt.ItemDataRole.ToolTipRole) for position in range(languages.count())
        ]
        update: QCheckBox = menu.update()
        # Assert
        assert captions == ["Тема", "Язык"]
        assert themes == [("Авто", False), ("Тёмная", True), ("Светлая", False)]
        assert (codes, names, languages.currentText()) == (
            ["EN", "RU", "DE", "FR", "ES"],
            list(LANGUAGE_NAMES.values()),
            "RU",
        )
        assert (update.text(), update.isChecked()) == ("Автообновление", True)
        assert update.toolTip() == "Раз в неделю загружает свежие списки процессоров, видеокарт и игр."

    def test_no_focus(self, menu: _Menu) -> None:
        """
        Opens with nothing focused, and no part of it takes focus: the language list kept a focus frame.

        :param menu: the menu
        :return: None
        """
        # Arrange & Act
        parts: list[QWidget] = [*menu.themes(), menu.languages(), menu.update()]
        # Assert
        assert menu.widget.focusWidget() is None
        assert all(part.focusPolicy() == Qt.FocusPolicy.NoFocus for part in parts)

    def test_theme_picked(self, menu: _Menu) -> None:
        """
        Passes the theme picked on, checks its button only and keeps the menu open.

        :param menu: the menu
        :return: None
        """
        # Arrange
        themes: list[IconButton] = menu.themes()
        # Act
        themes[2].click()
        # Assert
        menu.on_theme.assert_called_once_with(ThemeMode.LIGHT)
        assert ([button.isChecked() for button in themes], menu.widget.isVisible()) == ([False, False, True], True)

    def test_language_picked(self, menu: _Menu) -> None:
        """
        Passes the language picked on and closes the menu.

        :param menu: the menu
        :return: None
        """
        # Arrange & Act
        menu.languages().activated.emit(list(LANGUAGE_NAMES).index("de"))
        # Assert
        menu.on_language.assert_called_once_with("de")
        assert not menu.widget.isVisible()

    def test_update_switched(self, menu: _Menu) -> None:
        """
        Passes the new state of the update switch on.

        :param menu: the menu
        :return: None
        """
        # Arrange & Act
        menu.update().click()
        # Assert
        menu.on_auto_update.assert_called_once_with(False)
