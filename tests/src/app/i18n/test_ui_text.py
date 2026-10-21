"""Tests that the .po catalogs translate every UI text."""

import re

import pytest
from babel.messages.catalog import Catalog, Message

from app.config import UI_LANGUAGES
from app.i18n.ui_text import UiText

__all__: tuple = ()

_PLACEHOLDER: re.Pattern[str] = re.compile(pattern=r"\{\w+\}")


class TestCatalogs:
    """Completeness of the translations of every UI language."""

    @pytest.mark.parametrize(argnames="language", argvalues=list(UI_LANGUAGES))
    def test_same_messages_as_enum(self, catalogs: dict[str, Catalog], language: str) -> None:
        """
        Holds exactly the UiText messages: no text missing, none left over from a removed member.

        :param catalogs: catalogs by UI language
        :param language: UI language
        :return: None
        """
        # Arrange & Act
        ids: set[str] = {str(message.id) for message in catalogs[language] if message.id}
        # Assert
        assert ids == {item.value for item in UiText}

    @pytest.mark.parametrize(argnames="language", argvalues=list(UI_LANGUAGES))
    def test_every_message_translated(self, catalogs: dict[str, Catalog], language: str) -> None:
        """
        Translates every message, none of them fuzzy, keeping the placeholders of the source.

        :param catalogs: catalogs by UI language
        :param language: UI language
        :return: None
        """
        # Arrange
        messages: list[Message] = [message for message in catalogs[language] if message.id]
        # Act
        broken: list[str] = [
            str(message.id)
            for message in messages
            if not message.string
            or message.fuzzy
            or set(_PLACEHOLDER.findall(string=str(message.string)))
            != set(_PLACEHOLDER.findall(string=str(message.id)))
        ]
        # Assert
        assert not broken
