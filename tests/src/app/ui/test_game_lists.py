"""Tests of the game lists of both tabs and the game chosen in each tab."""

from pathlib import Path

import pytest

from app.core.models import Game, GameChoice, GamesTab, InstalledGame
from app.ui.game_lists import GameLists

__all__: tuple = ()

_BG3: Game = Game(game_id="baldurs_gate_3", name="Baldur's Gate 3")
_MORDHAU: Game = Game(game_id="mordhau", name="MORDHAU")
_GAMES: tuple[Game, ...] = (_BG3, _MORDHAU)
_EXE: Path = Path("D:/Games/game.exe")


class TestGameLists:
    """Tests of GameLists."""

    @pytest.mark.parametrize(
        argnames=("saved", "games", "chosen"),
        argvalues=[
            ("mordhau", _GAMES, "mordhau"),
            ("dead_or_alive_5", _GAMES, "baldurs_gate_3"),
            (None, _GAMES, "baldurs_gate_3"),
            ("mordhau", (), "mordhau"),
        ],
        ids=["listed", "not listed", "none saved", "empty list"],
    )
    def test_catalog_game_kept(self, saved: str | None, games: tuple[Game, ...], chosen: str | None) -> None:
        """
        Keeps the chosen game of all games while listed, else takes the first; an empty list keeps the identifier.

        :param saved: identifier chosen before
        :param games: the new list
        :param chosen: identifier expected chosen
        :return: None
        """
        # Arrange
        lists: GameLists = GameLists(choice=GameChoice(tab=GamesTab.ALL, catalog_game_id=saved))
        # Act
        lists.set_games(games=games)
        # Assert
        assert lists.choice.catalog_game_id == chosen

    def test_installed_game_kept(self) -> None:
        """
        Moves to the first installed game when the chosen one is no longer found, keeping it while nothing is found.

        :return: None
        """
        # Arrange
        lists: GameLists = GameLists(choice=GameChoice(installed_game_id="mordhau"))
        # Act
        lists.set_installed(installed=())
        kept: str | None = lists.choice.installed_game_id
        lists.set_installed(installed=(InstalledGame(game=_BG3, executable=_EXE),))
        # Assert
        assert (kept, lists.choice.installed_game_id, lists.installed_position) == ("mordhau", "baldurs_gate_3", 0)

    def test_game_of_the_tab(self) -> None:
        """
        Gives the game chosen in the tab in use.

        :return: None
        """
        # Arrange
        lists: GameLists = GameLists(choice=GameChoice())
        lists.set_games(games=_GAMES)
        lists.set_installed(installed=(InstalledGame(game=_MORDHAU, executable=_EXE),))
        installed: Game | None = lists.game
        # Act
        lists.choose_tab(tab=GamesTab.ALL)
        # Assert
        assert (installed, lists.game) == (_MORDHAU, _BG3)

    def test_search(self) -> None:
        """
        Shows the games matching the search ignoring case; the chosen game hidden by it has no position.

        :return: None
        """
        # Arrange
        lists: GameLists = GameLists(choice=GameChoice(tab=GamesTab.ALL))
        lists.set_games(games=_GAMES)
        lists.search(text=" Mord ")
        # Act
        lists.filter()
        hidden: int | None = lists.shown_position
        lists.choose_shown(position=0)
        # Assert
        assert (lists.shown, hidden, lists.shown_position, lists.game) == ((_MORDHAU,), None, 0, _MORDHAU)
