"""UI language choice and the translation of UI texts through the compiled gettext catalogs."""

import ctypes
import gettext
import locale
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import DEFAULT_LANGUAGE, GETTEXT_DOMAIN, LOCALE_DIR, UI_LANGUAGES
from app.i18n.ui_text import UiText

__all__: tuple[str, ...] = ("Translator",)


class Translator:
    """Translates UI texts into one UI language; a missing catalog leaves the texts in English."""

    def __init__(self, *, language: str, locale_dir: Path = LOCALE_DIR) -> None:
        """
        Load the catalog of a UI language.

        :param language: one of the UI languages, e.g. "ru"
        :param locale_dir: folder of <language>/LC_MESSAGES/<domain>.mo catalogs
        """
        if language not in UI_LANGUAGES:
            raise ValueError(f"unsupported UI language {language!r}")
        self.language: str = language
        self._catalog: gettext.NullTranslations = gettext.translation(
            domain=GETTEXT_DOMAIN, localedir=locale_dir, languages=[language], fallback=True
        )
        if not isinstance(self._catalog, gettext.GNUTranslations):
            logger.warning("No catalog for {} in {}: texts stay in English", language, locale_dir)

    @property
    def nvidia_language(self) -> str:
        """
        Get the language code of NVIDIA's translation files for the UI language.

        :return: NVIDIA language code, e.g. "ru_RU"
        """
        return UI_LANGUAGES[self.language]

    def text(self, *, item: UiText, **values: str) -> str:
        """
        Translate a UI text and fill its placeholders.

        :param item: the text
        :param values: placeholder values by name, e.g. error="timeout"
        :return: translated text
        """
        return self._catalog.gettext(item.value).format(**values)

    @classmethod
    def pick_language(cls, *, saved: str | None) -> str:
        """
        Choose the UI language: the saved one, otherwise the Windows display language, otherwise English.

        :param saved: language saved in the user settings
        :return: one of the UI languages
        """
        if saved is not None and saved in UI_LANGUAGES:
            return saved
        detected: str | None = cls._windows_language()
        language: str = detected if detected is not None and detected in UI_LANGUAGES else DEFAULT_LANGUAGE
        logger.info("UI language: {} (Windows: {})", language, detected)
        return language

    @staticmethod
    def _windows_language() -> str | None:
        """
        Get the language of the Windows user interface.

        :return: language part of the Windows locale, e.g. "ru" for ru_RU, or None for an unknown one
        """
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        get_ui_language: Any = ctypes.WinDLL(name="kernel32")["GetUserDefaultUILanguage"]
        windows_locale: str | None = locale.windows_locale.get(get_ui_language())
        return None if windows_locale is None else windows_locale.split(sep="_")[0]
