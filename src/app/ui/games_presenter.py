"""UI logic of the game tabs: both game lists, the search, the folders searched for installed games and box art."""

from pathlib import Path, PureWindowsPath
from typing import Callable

from loguru import logger

from app.config import REQUEST_DELAY_MS, SEARCH_DELAY_MS
from app.core.models import Game, GameChoice, GamesTab, InstalledGame
from app.core.service import PresetService
from app.i18n.ui_text import UiText
from app.ui.debouncer import Debouncer
from app.ui.game_lists import GameLists
from app.ui.status import Status, StatusTexts
from app.ui.views import InstalledGameView, MainView
from app.ui.worker import Runners

__all__: tuple[str, ...] = ("GamesPresenter",)


class GamesPresenter:
    """Drives the game tabs and tells the owner which game is chosen; box art follows the chosen game.

    Installed games are searched for in a runner of their own, so a long search never holds up the presets; a search
    asked for while one runs starts again once it ends.

    Each game tab has a game of its own: the game of the tab in use is the chosen one. The tab and both games are saved
    whenever they change, the first game of a list being chosen when the saved one is not there."""

    # Debouncer keys.
    _SEARCH: str = "search"
    _COVER: str = "cover"

    def __init__(
        self,
        *,
        view: MainView,
        service: PresetService,
        runners: Runners,
        debouncer: Debouncer,
        texts: StatusTexts,
        on_game: Callable[[Game | None], None],
        on_status: Callable[[Status], None],
        save: Callable[[Callable[[], None]], None],
    ) -> None:
        """
        Wire the game tabs; nothing is shown before start().

        :param view: the window
        :param service: service the requests go to
        :param runners: runners of the background tasks
        :param debouncer: delays the search and box art while the user is still changing them
        :param texts: makes the status lines
        :param on_game: called with the chosen game whenever another one is chosen, None when there is none
        :param on_status: shows a status line
        :param save: runs a settings save in the background
        """
        self._view: MainView = view
        self._service: PresetService = service
        self._runners: Runners = runners
        self._debouncer: Debouncer = debouncer
        self._texts: StatusTexts = texts
        self._on_game: Callable[[Game | None], None] = on_game
        self._on_status: Callable[[Status], None] = on_status
        self._save: Callable[[Callable[[], None]], None] = save
        self._lists: GameLists = GameLists(choice=GameChoice())
        self._saved_choice: GameChoice = GameChoice()
        self._folders: tuple[str, ...] = ()
        self._finding: bool = False
        self._find_again: bool = False
        self._game: Game | None = None
        self._cover_request: int = 0

    @property
    def game(self) -> Game | None:
        """
        Get the chosen game: the one of the tab in use.

        :return: the game, None when the tab has none
        """
        return self._game

    def start(self) -> None:
        """
        Show the saved tab and the games with the saved game chosen, and the skeleton of the installed games.

        :return: None
        """
        self._view.clear_cover(loading=False)
        self._saved_choice = self._service.saved_game_choice()
        self._lists = GameLists(choice=self._saved_choice)
        self._view.show_tab(tab=self._saved_choice.tab)
        self._set_games(games=self._service.games())
        self._view.show_finding()

    def load_folders(self) -> None:
        """
        Read the folders searched for games, then search them.

        :return: None
        """
        self._runners.requests.submit(
            task=self._service.game_folders, on_done=self._on_folders, on_error=self._on_folders_error
        )

    def refresh(self, *, games: tuple[Game, ...]) -> None:
        """
        Use the games of a new database and search for installed games again; the chosen game stays when it is there.

        :param games: games in list order
        :return: None
        """
        if self._game is not None:
            game_id: str = self._game.game_id
            self._game = next((game for game in games if game.game_id == game_id), self._game)
        self._set_games(games=games)
        self.find_games()

    def select_tab(self, *, tab: GamesTab) -> None:
        """
        Use another game tab and show the game chosen there.

        :param tab: the tab
        :return: None
        """
        self._lists.choose_tab(tab=tab)
        self._show_game()

    def select_game(self, *, index: int) -> None:
        """
        Choose a game of the list of all games.

        :param index: position of the game in the list as shown, i.e. after the search
        :return: None
        """
        self._lists.choose_shown(position=index)
        self._show_game()

    def select_installed_game(self, *, index: int) -> None:
        """
        Choose a game of the list of installed games.

        :param index: position of the game in the list
        :return: None
        """
        self._lists.choose_installed(position=index)
        self._show_game()

    def find_games(self) -> None:
        """
        Search the game folders and the registry for installed games again.

        :return: None
        """
        if self._finding:
            self._find_again = True
            return
        self._finding = True
        self._view.show_finding()
        folders: tuple[str, ...] = self._folders
        self._runners.finder.submit(
            task=lambda: self._service.find_games(folders=folders), on_done=self._on_found, on_error=self._on_find_error
        )

    def add_folder(self, *, folder: str) -> None:
        """
        Add a folder to search for games, save the list and search again; a folder already listed changes nothing.

        :param folder: folder the user picked
        :return: None
        """
        self._put_folder(position=len(self._folders), folder=folder, replacing=False)

    def change_folder(self, *, position: int, folder: str) -> None:
        """
        Put another folder in place of a listed one, save the list and search again.

        :param position: position of the folder in the list
        :param folder: folder the user picked
        :return: None
        """
        if 0 <= position < len(self._folders):
            self._put_folder(position=position, folder=folder, replacing=True)

    def remove_folder(self, *, position: int) -> None:
        """
        Stop searching a folder for games, save the list and search again.

        :param position: position of the folder in the list
        :return: None
        """
        if 0 <= position < len(self._folders):
            self._set_folders(folders=self._folders[:position] + self._folders[position + 1 :])

    def search_games(self, *, text: str) -> None:
        """
        Show only the games whose name contains the text, ignoring case, once the typing rests.

        :param text: text typed by the user; empty shows every game
        :return: None
        """
        self._lists.search(text=text)
        self._debouncer.call(key=self._SEARCH, delay_ms=SEARCH_DELAY_MS, action=self._render_games)

    def _show_game(self) -> None:
        """
        Save a changed game choice; when the tab's game changed, get its box art and tell the owner.

        :return: None
        """
        self._save_game_choice()
        game: Game | None = self._lists.game
        # The window reports its own selection of the chosen game too, e.g. after a search.
        if game == self._game:
            return
        self._game = game
        if game is None:
            self._view.clear_cover(loading=False)
        else:
            self._request_cover(game=game)
        self._on_game(game)

    def _save_game_choice(self) -> None:
        """
        Save the game tab and the game of each tab when they differ from the saved ones.

        :return: None
        """
        choice: GameChoice = self._lists.choice
        if choice == self._saved_choice:
            return
        self._saved_choice = choice
        self._save(lambda: self._service.save_game_choice(choice=choice))

    def _request_cover(self, *, game: Game) -> None:
        """
        Get the box art of a game once the choice rests; an answer for a game chosen before is dropped.

        :param game: the chosen game
        :return: None
        """
        self._cover_request += 1
        if game.cover_url is None:
            self._view.show_cover(picture=None)
            return
        request: int = self._cover_request
        self._view.clear_cover(loading=True)
        self._debouncer.call(
            key=self._COVER,
            delay_ms=REQUEST_DELAY_MS,
            action=lambda: self._runners.requests.submit(
                task=lambda: self._service.cover(game=game),
                on_done=lambda picture: self._on_cover(request=request, picture=picture),
                on_error=lambda _: self._on_cover(request=request, picture=None),
            ),
        )

    def _on_cover(self, *, request: int, picture: Path | None) -> None:
        """
        Show the box art of the chosen game, or the placeholder when it could not be had.

        :param request: number of the request
        :param picture: the picture file, None on failure
        :return: None
        """
        if request == self._cover_request:
            self._view.show_cover(picture=picture)

    def _on_folders(self, folders: tuple[str, ...]) -> None:
        """
        Show the folders searched for games and search them.

        :param folders: existing folders in the user's order
        :return: None
        """
        self._folders = folders
        self._view.show_folders(folders=folders)
        self.find_games()

    def _on_folders_error(self, error: Exception) -> None:
        """
        Search the registry alone when the saved folders can't be read.

        :param error: the failure
        :return: None
        """
        logger.warning("Searching without game folders: {}", error)
        self._on_folders(folders=())

    def _put_folder(self, *, position: int, folder: str, replacing: bool) -> None:
        """
        Put a folder at a position of the list, unless another position lists it already.

        :param position: position to put it at; the end of the list adds it
        :param folder: folder the user picked
        :param replacing: True to replace the folder at the position, False to insert it there
        :return: None
        """
        if not folder:
            return
        normalized: str = str(PureWindowsPath(folder))
        after: int = position + 1 if replacing else position
        others: tuple[str, ...] = self._folders[:position] + self._folders[after:]
        if normalized.casefold() in (item.casefold() for item in others):
            return
        self._set_folders(folders=self._folders[:position] + (normalized,) + self._folders[after:])

    def _set_folders(self, *, folders: tuple[str, ...]) -> None:
        """
        Use, show and save a new folder list and search it.

        :param folders: folders in the user's order
        :return: None
        """
        if folders == self._folders:
            return
        self._folders = folders
        self._view.show_folders(folders=folders)
        self._save(lambda: self._service.save_game_folders(folders=folders))
        self.find_games()

    def _on_found(self, games: tuple[InstalledGame, ...]) -> None:
        """
        Show the installed games, or search again when that was asked for during the search.

        :param games: installed games sorted by name
        :return: None
        """
        self._finding = False
        if self._find_again:
            self._find_again = False
            self.find_games()
            return
        self._lists.set_installed(installed=games)
        self._render_installed()
        self._show_game()

    def _on_find_error(self, error: Exception) -> None:
        """
        Report a failed search for installed games and show none.

        :param error: the failure
        :return: None
        """
        self._on_found(games=())
        self._on_status(self._texts.error(item=UiText.FIND_FAILED, error=error))

    def _set_games(self, *, games: tuple[Game, ...]) -> None:
        """
        Use and show a new list of all games, and the game of the tab in use.

        :param games: games in list order
        :return: None
        """
        self._lists.set_games(games=games)
        self._render_games()
        self._show_game()

    def _render_games(self) -> None:
        """
        Fill the list of all games with the ones matching the search, keeping the chosen game selected when it is there.

        :return: None
        """
        self._lists.filter()
        self._view.show_games(names=[game.name for game in self._lists.shown], selected=self._lists.shown_position)

    def _render_installed(self) -> None:
        """
        Fill the list of installed games, keeping the chosen game selected when it is there.

        :return: None
        """
        self._view.show_installed_games(
            games=[
                InstalledGameView(name=item.game.name, executable=item.executable) for item in self._lists.installed
            ],
            selected=self._lists.installed_position,
        )
