"""Tests of the gettext template generator."""

from pathlib import Path

from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po
from make_pot import _PotMaker

from app.i18n.ui_text import UiText

__all__: tuple = ()


class TestPotMaker:
    """Tests of _PotMaker."""

    def test_every_text(self, tmp_path: Path) -> None:
        """
        Writes every UiText member in enum order, named in a translator comment, placeholders flagged.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        output: Path = tmp_path / "locale" / "messages.pot"
        # Act
        _PotMaker.make(output=output)
        # Assert
        with output.open(mode="rb") as file:
            catalog: Catalog = read_po(fileobj=file)
        messages: list[Message] = [message for message in catalog if message.id]
        assert [(message.id, message.auto_comments) for message in messages] == [
            (item.value, [item.name]) for item in UiText
        ]
        assert {str(message.id) for message in messages if "python-brace-format" in message.flags} == {
            item.value for item in UiText if "{" in item.value
        }
