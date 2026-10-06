"""Display names of games by their catalog identifier (slug)."""

import json
from pathlib import Path
from typing import Mapping, Self

from loguru import logger

from app.config import GAME_NAMES_FILE

__all__: tuple[str, ...] = ("GameNames",)


class GameNames:
    """Display names of games from the bundled list; a game missing there is named after its slug."""

    def __init__(self, *, names: Mapping[str, str]) -> None:
        """
        Use the given names.

        :param names: display names by game slug
        """
        self._names: Mapping[str, str] = names

    @classmethod
    def load(cls, *, path: Path = GAME_NAMES_FILE) -> Self:
        """
        Load the names from a JSON file.

        :param path: JSON object of display names by game slug
        :return: game names
        """
        names: dict[str, str] = json.loads(s=path.read_text(encoding="utf-8"))
        logger.debug("Loaded {} game names from {}", len(names), path)
        return cls(names=names)

    def name(self, *, game_id: str) -> str:
        """
        Get the display name of a game.

        :param game_id: game identifier (slug), e.g. "baldurs_gate_3"
        :return: display name from the list, or the slug with words capitalized and "_" replaced by spaces
        """
        return self._names.get(game_id) or self._from_slug(game_id=game_id)

    @staticmethod
    def _from_slug(*, game_id: str) -> str:
        """
        Make a display name from a slug: "the_blood_of_dawnwalker" -> "The Blood Of Dawnwalker".

        :param game_id: game identifier (slug)
        :return: display name
        """
        return " ".join(word.capitalize() for word in game_id.split("_") if word)
