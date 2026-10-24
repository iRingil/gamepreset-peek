"""The games of both tabs: all games with the search over them, the installed ones, and the game chosen in each tab."""

from dataclasses import replace

from app.core.models import Game, GameChoice, GamesTab, InstalledGame

__all__: tuple[str, ...] = ("GameLists",)


class GameLists:
    """Keeps the game lists of both tabs and the game chosen in each tab, by identifier.

    A tab's game survives a new database and a new search for installed games while the tab's list still has it;
    otherwise the first game of the list is chosen. An empty list keeps the identifier for when the game is back."""

    def __init__(self, *, choice: GameChoice) -> None:
        """
        Start with empty lists.

        :param choice: the saved tab and games
        """
        self._choice: GameChoice = choice
        self._games: tuple[Game, ...] = ()
        self._search: str = ""
        self._shown: tuple[Game, ...] = ()
        self._installed: tuple[InstalledGame, ...] = ()

    @property
    def choice(self) -> GameChoice:
        """
        Get the tab in use and the game chosen in each tab.

        :return: the choice
        """
        return self._choice

    @property
    def shown(self) -> tuple[Game, ...]:
        """
        Get the games of the list of all games that matched the search at the last filter().

        :return: games in list order
        """
        return self._shown

    @property
    def installed(self) -> tuple[InstalledGame, ...]:
        """
        Get the installed games.

        :return: installed games in list order
        """
        return self._installed

    @property
    def game(self) -> Game | None:
        """
        Get the game chosen in the tab in use.

        :return: the game, None when the tab's list is empty
        """
        return self.installed_game if self._choice.tab is GamesTab.INSTALLED else self.catalog_game

    @property
    def installed_game(self) -> Game | None:
        """
        Get the game chosen in the installed games tab.

        :return: the game, None when it is not installed
        """
        game_id: str | None = self._choice.installed_game_id
        return next((item.game for item in self._installed if item.game.game_id == game_id), None)

    @property
    def catalog_game(self) -> Game | None:
        """
        Get the game chosen in the all games tab.

        :return: the game, None when the database lacks it
        """
        return next((game for game in self._games if game.game_id == self._choice.catalog_game_id), None)

    @property
    def shown_position(self) -> int | None:
        """
        Find the game chosen in the all games tab in the list as shown.

        :return: its position, None when the search hides it
        """
        game: Game | None = self.catalog_game
        return self._shown.index(game) if game in self._shown else None

    @property
    def installed_position(self) -> int | None:
        """
        Find the game chosen in the installed games tab in its list.

        :return: its position, None when it is not installed
        """
        game_id: str | None = self._choice.installed_game_id
        return next((i for i, item in enumerate(self._installed) if item.game.game_id == game_id), None)

    def set_games(self, *, games: tuple[Game, ...]) -> None:
        """
        Use a new list of all games, keeping the chosen one when it is still there.

        :param games: games in list order
        :return: None
        """
        self._games = games
        self._choice = replace(
            self._choice, catalog_game_id=self._kept(game_id=self._choice.catalog_game_id, games=games)
        )

    def set_installed(self, *, installed: tuple[InstalledGame, ...]) -> None:
        """
        Use a new list of installed games, keeping the chosen one when it is still there.

        :param installed: installed games in list order
        :return: None
        """
        self._installed = installed
        self._choice = replace(
            self._choice,
            installed_game_id=self._kept(
                game_id=self._choice.installed_game_id, games=tuple(item.game for item in installed)
            ),
        )

    def search(self, *, text: str) -> None:
        """
        Keep the search text for the next filter().

        :param text: text typed by the user; empty shows every game
        :return: None
        """
        self._search = text.strip().casefold()

    def filter(self) -> None:
        """
        Show only the games whose name contains the search text, ignoring case.

        :return: None
        """
        self._shown = tuple(game for game in self._games if self._search in game.name.casefold())

    def choose_tab(self, *, tab: GamesTab) -> None:
        """
        Use another tab.

        :param tab: the tab
        :return: None
        """
        self._choice = replace(self._choice, tab=tab)

    def choose_shown(self, *, position: int) -> None:
        """
        Choose a game of the list of all games as shown.

        :param position: position of the game in the list as shown
        :return: None
        """
        self._choice = replace(self._choice, catalog_game_id=self._shown[position].game_id)

    def choose_installed(self, *, position: int) -> None:
        """
        Choose a game of the list of installed games.

        :param position: position of the game in the list
        :return: None
        """
        self._choice = replace(self._choice, installed_game_id=self._installed[position].game.game_id)

    @staticmethod
    def _kept(*, game_id: str | None, games: tuple[Game, ...]) -> str | None:
        """
        Keep a game identifier the list has, or take the first game of the list; an empty list keeps it.

        :param game_id: identifier of the chosen game, None when none was chosen
        :param games: the list
        :return: identifier of the game to choose
        """
        if not games or any(game.game_id == game_id for game in games):
            return game_id
        return games[0].game_id
