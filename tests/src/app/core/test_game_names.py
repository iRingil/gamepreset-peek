"""Tests of the game display names."""

import json
from pathlib import Path

import pytest

from app.config import GAME_NAMES_FILE
from app.core.game_names import GameNames

__all__: tuple = ()


class TestName:
    """Name lookup with the fallback to the slug."""

    @pytest.fixture(name="names")
    def _names(self) -> GameNames:
        """
        Create names with one known game.

        :return: game names
        """
        return GameNames(names={"baldurs_gate_3": "Baldur's Gate 3"})

    def test_known_game(self, names: GameNames) -> None:
        """
        Returns the name from the list for a known game.

        :param names: game names
        :return: None
        """
        # Arrange & Act
        name: str = names.name(game_id="baldurs_gate_3")
        # Assert
        assert name == "Baldur's Gate 3"

    @pytest.mark.parametrize(
        argnames=("game_id", "expected"),
        argvalues=[
            ("the_blood_of_dawnwalker", "The Blood Of Dawnwalker"),
            ("nba_2k27", "Nba 2k27"),
            ("wardogs", "Wardogs"),
            ("aniimo__uwp_", "Aniimo Uwp"),
        ],
        ids=["words", "digits", "single word", "extra underscores"],
    )
    def test_unknown_game(self, names: GameNames, game_id: str, expected: str) -> None:
        """
        Makes the name of a game missing from the list from its slug.

        :param names: game names
        :param game_id: slug missing from the list
        :param expected: expected display name
        :return: None
        """
        # Arrange & Act
        name: str = names.name(game_id=game_id)
        # Assert
        assert name == expected


class TestLoad:
    """Loading the names from a JSON file."""

    def test_from_file(self, tmp_path: Path) -> None:
        """
        Reads the names from a UTF-8 JSON file.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        path: Path = tmp_path / "game_names.json"
        path.write_text(data=json.dumps(obj={"hitman": "Hitman™"}, ensure_ascii=False), encoding="utf-8")
        # Act
        names: GameNames = GameNames.load(path=path)
        # Assert
        assert names.name(game_id="hitman") == "Hitman™"

    def test_bundled_file(self) -> None:
        """
        Loads the bundled file: every name is non-empty and has no surrounding whitespace.

        :return: None
        """
        # Arrange
        raw: dict[str, str] = json.loads(s=GAME_NAMES_FILE.read_text(encoding="utf-8"))
        # Act
        names: GameNames = GameNames.load()
        # Assert
        assert names.name(game_id="baldurs_gate_3") == "Baldur's Gate 3"
        assert names.name(game_id="dead_or_alive_5") == "DEAD OR ALIVE® 5 Last Round"
        assert all(name and name == name.strip() for name in raw.values())
