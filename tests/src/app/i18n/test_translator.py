"""Tests of the UI language choice and the translation of UI texts."""

import locale
from pathlib import Path

import pytest

from app.i18n.translator import Translator
from app.i18n.ui_text import UiText

__all__: tuple = ()


class _AnyLanguageId(dict[int, str]):
    """Maps every Windows language id to one locale, whatever language the test machine has."""

    def __init__(self, *, windows_locale: str) -> None:
        """
        Use one locale for every id.

        :param windows_locale: locale name, e.g. "ru_RU"
        """
        super().__init__()
        self._windows_locale: str = windows_locale

    # noinspection PyMethodOverriding
    def get(self, key: int, default: str | None = None) -> str | None:  # type: ignore[override]
        """
        Give the locale of any language id.

        :param key: Windows language id
        :param default: ignored
        :return: the locale
        """
        return self._windows_locale


class TestText:
    """Tests of Translator.text and nvidia_language."""

    def test_translated(self, locale_dir: Path) -> None:
        """
        Translates a text into the UI language.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        translator: Translator = Translator(language="ru", locale_dir=locale_dir)
        # Act
        text: str = translator.text(item=UiText.GAME)
        # Assert
        assert text == "Игра"

    def test_placeholders_filled(self, locale_dir: Path) -> None:
        """
        Fills the placeholders of a translated text.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        translator: Translator = Translator(language="de", locale_dir=locale_dir)
        # Act
        text: str = translator.text(item=UiText.GAMES_FAILED, error="timeout")
        # Assert
        assert text == "Die Spieleliste konnte nicht geladen werden: timeout"

    def test_missing_catalog(self, tmp_path: Path) -> None:
        """
        Leaves texts in English when the catalog of the language is missing.

        :param tmp_path: empty locale folder
        :return: None
        """
        # Arrange
        translator: Translator = Translator(language="fr", locale_dir=tmp_path)
        # Act
        text: str = translator.text(item=UiText.SHOW_LOGS)
        # Assert
        assert text == "Show logs"

    def test_unsupported_language(self, locale_dir: Path) -> None:
        """
        Rejects a language the UI does not offer.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Act & Assert
        with pytest.raises(ValueError):
            Translator(language="it", locale_dir=locale_dir)

    def test_nvidia_language(self, locale_dir: Path) -> None:
        """
        Maps the UI language to the language code of NVIDIA's translation files.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange & Act
        translator: Translator = Translator(language="es", locale_dir=locale_dir)
        # Assert
        assert translator.nvidia_language == "es_ES"


class TestPickLanguage:
    """Tests of Translator.pick_language."""

    @pytest.mark.parametrize(
        argnames=("saved", "windows_locale", "expected"),
        argvalues=[
            ("de", "ru_RU", "de"),
            (None, "ru_RU", "ru"),
            ("it", "fr_FR", "fr"),
            (None, "ja_JP", "en"),
        ],
        ids=["saved", "windows", "saved unsupported", "windows unsupported"],
    )
    def test_pick(self, monkeypatch: pytest.MonkeyPatch, saved: str | None, windows_locale: str, expected: str) -> None:
        """
        Prefers the saved language, then the Windows display language, then English.

        :param monkeypatch: pytest monkeypatch
        :param saved: saved language
        :param windows_locale: locale of the Windows display language
        :param expected: chosen language
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=locale, name="windows_locale", value=_AnyLanguageId(windows_locale=windows_locale))
        # Act
        language: str = Translator.pick_language(saved=saved)
        # Assert
        assert language == expected

    def test_unknown_windows_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Falls back to English when Windows reports a language id with no known locale.

        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=locale, name="windows_locale", value={})
        # Act
        language: str = Translator.pick_language(saved=None)
        # Assert
        assert language == "en"
