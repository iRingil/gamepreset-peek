"""UI logic of the main window: user actions -> service calls in the background -> what the window shows."""

from dataclasses import replace
from pathlib import Path, PureWindowsPath

from loguru import logger

from app.config import LOCALE_DIR, REQUEST_DELAY_MS, SEARCH_DELAY_MS
from app.core.models import (
    DatabaseUpdate,
    Game,
    GameChoice,
    GamePresets,
    GamesTab,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
    InstalledGame,
    ResolutionPreset,
    ThemeMode,
)
from app.core.service import PresetService
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.debouncer import Debouncer
from app.ui.game_lists import GameLists
from app.ui.status import Status, StatusTexts
from app.ui.views import (
    ChoiceGroup,
    ChoiceView,
    HardwareView,
    InstalledGameView,
    MainView,
    SettingRow,
    SettingsView,
    StatusLevel,
)
from app.ui.worker import TaskRunner

__all__: tuple[str, ...] = ("Presenter",)


class Presenter:  # pylint: disable=too-many-instance-attributes
    """Drives the main window: every blocking service call runs through the task runner.

    A chosen game's presets are requested once the selection rests for a moment, so stepping through the list sends
    no burst of requests; the settings of the resolution in use follow at once. Each request gets a number; an answer
    to a request made before the user changed the game or the resolution is dropped. Texts are kept as functions, so
    a language switch re-renders them.

    Why no presets can be requested stays in the status line until NVIDIA accepts the hardware.

    Installed games are searched for in a runner of their own, so a long search never holds up the presets; a search
    asked for while one runs starts again once it ends. Box art follows the chosen game like its presets.

    Each game tab has a game of its own: the settings show the one of the tab in use. The tab and both games are saved
    whenever they change, the first game of a list being chosen when the saved one is not there.

    The database update runs once the first hardware check has answered, so a slow download never delays the start;
    a new database refreshes the games, the installed ones and the choice lists."""

    # Tabs of the bundled CPUs: vendor names, not translated.
    _AMD: str = "AMD"
    _INTEL: str = "Intel"
    # Debouncer keys.
    _PRESETS: str = "presets"
    _SEARCH: str = "search"
    _COVER: str = "cover"

    def __init__(
        self,
        *,
        view: MainView,
        service: PresetService,
        runner: TaskRunner,
        finder: TaskRunner,
        debouncer: Debouncer,
        translator: Translator,
        theme: ThemeMode,
        auto_update: bool,
        locale_dir: Path = LOCALE_DIR,
    ) -> None:
        """
        Wire the presenter; nothing is requested before start().

        :param view: the window
        :param service: service the requests go to
        :param runner: runs service calls in the background
        :param finder: runs the search for installed games in the background
        :param debouncer: delays the preset requests and the search while the user is still changing them
        :param translator: translator of the initial UI language
        :param theme: initial theme mode
        :param auto_update: whether the database is updated automatically
        :param locale_dir: folder of the compiled catalogs, for language switches
        """
        self._view: MainView = view
        self._service: PresetService = service
        self._runner: TaskRunner = runner
        self._finder: TaskRunner = finder
        self._debouncer: Debouncer = debouncer
        self._translator: Translator = translator
        self._locale_dir: Path = locale_dir
        self._theme: ThemeMode = theme
        self._auto_update: bool = auto_update
        self._database_checked: bool = False
        self._setup: HardwareSetup | None = None
        self._choice: HardwareChoice = HardwareChoice(cpu_name=None, gpu=None)
        self._hardware: Hardware | None = None
        self._resolution_name: str | None = None
        self._problem: Status | None = None
        self._lists: GameLists = GameLists(choice=GameChoice())
        self._saved_choice: GameChoice = GameChoice()
        self._folders: tuple[str, ...] = ()
        self._finding: bool = False
        self._find_again: bool = False
        self._game: Game | None = None
        self._presets: GamePresets | None = None
        self._resolution: ResolutionPreset | None = None
        self._settings: GameSettings | None = None
        self._preset_index: int = 0
        self._request: int = 0
        self._cover_request: int = 0
        self._status: Status | None = None
        self._texts: StatusTexts = StatusTexts(translator=lambda: self._translator)

    @property
    def language(self) -> str:
        """
        Get the current UI language.

        :return: language code, e.g. "ru"
        """
        return self._translator.language

    def start(self) -> None:
        """
        Theme and translate the window, show the saved tab and the games, then detect hardware and find installed games.

        :return: None
        """
        self._view.apply_theme(mode=self._theme)
        self._view.apply_language(translator=self._translator)
        self._view.show_auto_update(enabled=self._auto_update)
        self._render_hardware()
        self._view.clear_cover(loading=False)
        self._view.clear_settings(loading=False)
        self._saved_choice = self._service.saved_game_choice()
        self._lists = GameLists(choice=self._saved_choice)
        self._view.show_tab(tab=self._saved_choice.tab)
        self._set_games(games=self._service.games())
        self._view.show_finding()
        self._runner.submit(task=self._service.hardware_setup, on_done=self._on_setup, on_error=self._on_setup_error)
        self._runner.submit(task=self._service.game_folders, on_done=self._on_folders, on_error=self._on_folders_error)

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
        self._finder.submit(
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

    def move_slider(self, *, index: int) -> None:
        """
        Show another preset of the game.

        :param index: 1-based preset index
        :return: None
        """
        if self._settings is None or index == self._preset_index or not 1 <= index <= self._settings.count:
            return
        self._preset_index = index
        self._render_settings()

    def back_to_optimal(self) -> None:
        """
        Move the slider back to the recommended preset.

        :return: None
        """
        if self._resolution is not None:
            self.move_slider(index=self._resolution.preset_index)

    def change_language(self, *, language: str) -> None:
        """
        Switch the UI language, save it and re-render every text.

        :param language: language code, e.g. "ru"
        :return: None
        """
        if language == self._translator.language:
            return
        self._translator = Translator(language=language, locale_dir=self._locale_dir)
        self._runner.submit(
            task=lambda: self._service.save_language(language=language),
            on_done=lambda _: None,
            on_error=lambda _: None,
        )
        self._view.apply_language(translator=self._translator)
        self._render_hardware()
        self._set_status(status=self._status)
        if self._settings is not None:
            self._render_settings()

    def change_theme(self, *, mode: ThemeMode) -> None:
        """
        Switch the theme and save it.

        :param mode: theme mode
        :return: None
        """
        if mode is self._theme:
            return
        self._theme = mode
        self._runner.submit(
            task=lambda: self._service.save_theme(theme=mode), on_done=lambda _: None, on_error=lambda _: None
        )
        self._view.apply_theme(mode=mode)

    def change_auto_update(self, *, enabled: bool) -> None:
        """
        Switch the automatic database update and save it; switching it on runs an update if one is due.

        :param enabled: True to update the database automatically
        :return: None
        """
        if enabled == self._auto_update:
            return
        self._auto_update = enabled
        self._runner.submit(
            task=lambda: self._service.save_auto_update(enabled=enabled),
            on_done=lambda _: None,
            on_error=lambda _: None,
        )
        if enabled:
            self._update_database()

    def open_cpu_choice(self) -> None:
        """
        Offer the detected CPU, then the bundled ones by vendor, the one in use selected.

        :return: None
        """
        if self._setup is None:
            return
        options: tuple[str, ...] = self._setup.cpu_options
        groups: tuple[ChoiceGroup, ...] = ()
        if self._setup.amd_cpus or self._setup.intel_cpus:
            groups = (
                ChoiceGroup(title=self._AMD, items=self._setup.amd_cpus),
                ChoiceGroup(title=self._INTEL, items=self._setup.intel_cpus),
            )
        self._view.offer_cpus(
            choice=ChoiceView(
                detected=self._setup.detected_cpus,
                groups=groups,
                selected=options.index(self._choice.cpu_name) if self._choice.cpu_name in options else None,
            )
        )

    def open_gpu_choice(self) -> None:
        """
        Offer the detected GPUs, then the bundled ones, the one in use selected.

        :return: None
        """
        if self._setup is None:
            return
        options: tuple[Gpu, ...] = self._setup.gpu_options
        self._view.offer_gpus(
            choice=ChoiceView(
                detected=tuple(gpu.name for gpu in self._setup.system.gpus),
                groups=(ChoiceGroup(title="", items=tuple(gpu.name for gpu in self._setup.gpus)),),
                selected=options.index(self._choice.gpu) if self._choice.gpu in options else None,
            )
        )

    def open_resolution_choice(self) -> None:
        """
        Offer the detected screen resolution, then the bundled ones, the one in use selected.

        :return: None
        """
        if self._setup is None:
            return
        options: tuple[str, ...] = self._setup.resolution_options
        self._view.offer_resolutions(
            choice=ChoiceView(
                detected=self._setup.detected_resolutions,
                groups=(ChoiceGroup(title="", items=self._setup.resolutions),),
                selected=options.index(self._resolution_name) if self._resolution_name in options else None,
            )
        )

    def choose_cpu(self, *, position: int) -> None:
        """
        Use the CPU the user picked, checking it with NVIDIA.

        :param position: position in the CPU choice
        :return: None
        """
        if self._setup is not None:
            self._choose(choice=replace(self._choice, cpu_name=self._setup.cpu_options[position]))

    def choose_gpu(self, *, position: int) -> None:
        """
        Use the GPU the user picked, checking it with NVIDIA.

        :param position: position in the GPU choice
        :return: None
        """
        if self._setup is not None:
            self._choose(choice=replace(self._choice, gpu=self._setup.gpu_options[position]))

    def choose_resolution(self, *, position: int) -> None:
        """
        Use the resolution the user picked, save it and show the settings of the game for it.

        :param position: position in the resolution choice
        :return: None
        """
        if self._setup is None:
            return
        resolution: str = self._setup.resolution_options[position]
        if resolution == self._resolution_name:
            return
        self._resolution_name = resolution
        self._runner.submit(
            task=lambda: self._service.save_resolution(resolution=resolution),
            on_done=lambda _: None,
            on_error=lambda _: None,
        )
        self._render_hardware()
        if self._presets is not None:
            self._apply_resolution()

    def _show_game(self) -> None:
        """
        Save a changed game choice; show the settings and box art of the tab's game, requested once the choice rests.

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
            self._clear_game(loading=False)
            self._set_status(status=self._problem)
            return
        self._request_cover()
        self._clear_game(loading=self._hardware is not None)
        if self._hardware is None:
            self._set_status(status=self._problem or self._texts.info(item=UiText.LOADING))
            return
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._debouncer.call(key=self._PRESETS, delay_ms=REQUEST_DELAY_MS, action=self._request_presets)

    def _save_game_choice(self) -> None:
        """
        Save the game tab and the game of each tab when they differ from the saved ones.

        :return: None
        """
        choice: GameChoice = self._lists.choice
        if choice == self._saved_choice:
            return
        self._saved_choice = choice
        self._runner.submit(
            task=lambda: self._service.save_game_choice(choice=choice), on_done=lambda _: None, on_error=lambda _: None
        )

    def _request_cover(self) -> None:
        """
        Get the box art of the chosen game once the choice rests; an answer for a game chosen before is dropped.

        :return: None
        """
        self._cover_request += 1
        game: Game | None = self._game
        if game is None:  # pragma: no cover
            return
        if game.cover_url is None:
            self._view.show_cover(picture=None)
            return
        request: int = self._cover_request
        chosen: Game = game
        self._view.clear_cover(loading=True)
        self._debouncer.call(
            key=self._COVER,
            delay_ms=REQUEST_DELAY_MS,
            action=lambda: self._runner.submit(
                task=lambda: self._service.cover(game=chosen),
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
        self._runner.submit(
            task=lambda: self._service.save_game_folders(folders=folders),
            on_done=lambda _: None,
            on_error=lambda _: None,
        )
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
        self._set_status(status=self._texts.error(item=UiText.FIND_FAILED, error=error))

    def _on_setup(self, setup: HardwareSetup) -> None:
        """
        Show the hardware and resolution in use and check the hardware; warn when a CPU or GPU is neither chosen nor
        detected.

        :param setup: detected hardware, bundled lists and what is in use
        :return: None
        """
        self._setup = setup
        self._choice = setup.choice
        self._resolution_name = setup.resolution
        self._render_hardware()
        choice: HardwareChoice = setup.choice
        self._runner.submit(
            task=lambda: self._service.check_hardware(choice=choice),
            on_done=self._on_hardware,
            on_error=lambda error: self._on_check_error(previous=choice, error=error),
        )
        if setup.choice.cpu_name is None or setup.choice.gpu is None:
            self._view.warn(text=self._translator.text(item=UiText.UNSUPPORTED_HARDWARE))

    def _on_setup_error(self, error: Exception) -> None:
        """
        Report a failed hardware detection.

        :param error: the failure
        :return: None
        """
        self._lose_hardware(status=self._texts.error(item=UiText.HARDWARE_FAILED, error=error))
        self._update_database_once()

    def _choose(self, *, choice: HardwareChoice) -> None:
        """
        Show a new CPU and GPU pair at once and have NVIDIA check it; the hardware in use stays until it is accepted.

        :param choice: the pair the user made
        :return: None
        """
        if choice == self._choice and self._hardware is not None:
            return
        previous: HardwareChoice = self._choice
        self._choice = choice
        self._render_hardware()
        self._runner.submit(
            task=lambda: self._service.choose_hardware(choice=choice),
            on_done=self._on_hardware,
            on_error=lambda error: self._on_check_error(previous=previous, error=error),
        )

    def _on_hardware(self, check: HardwareCheck) -> None:
        """
        Use the hardware NVIDIA accepted, or show why there are no recommendations.

        :param check: result of the hardware check
        :return: None
        """
        if check.state is HardwareState.READY and check.hardware is not None:
            self._hardware = check.hardware
            if self._problem is not None and self._status is self._problem:
                self._set_status(status=None)
            self._problem = None
            if self._game is not None:
                self._clear_game(loading=True)
                self._request_presets()
        else:
            self._lose_hardware(status=self._texts.problem(check=check))
        self._update_database_once()

    def _on_check_error(self, *, previous: HardwareChoice, error: Exception) -> None:
        """
        Report a failed hardware check; hardware in use stays in use and is shown again.

        :param previous: the CPU and GPU shown before the check
        :param error: the failure
        :return: None
        """
        status: Status = self._texts.error(item=UiText.REQUEST_FAILED, error=error)
        if self._hardware is None:
            self._lose_hardware(status=status)
        else:
            self._choice = previous
            self._render_hardware()
            self._set_status(status=status)
        self._update_database_once()

    def _lose_hardware(self, *, status: Status) -> None:
        """
        Stop using any hardware: nothing can be requested until NVIDIA accepts a CPU and GPU.

        :param status: why there is no hardware
        :return: None
        """
        self._hardware = None
        self._problem = status
        self._set_status(status=status)
        self._clear_game(loading=False)

    def _request_presets(self) -> None:
        """
        Request the presets of the chosen game for the hardware in use.

        :return: None
        """
        if self._game is None or self._hardware is None:
            return
        request: int = self._next_request()
        game_id: str = self._game.game_id
        hardware: Hardware = self._hardware
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._runner.submit(
            task=lambda: self._service.game_presets(game_id=game_id, hardware=hardware),
            on_done=lambda presets: self._on_presets(request=request, presets=presets),
            on_error=lambda error: self._on_request_error(request=request, error=error),
        )

    def _on_presets(self, *, request: int, presets: GamePresets) -> None:
        """
        Keep the presets of a game and show the settings for the resolution in use.

        :param request: number of the request
        :param presets: presets of the game
        :return: None
        """
        if request != self._request:
            return
        self._presets = presets
        self._apply_resolution()

    def _apply_resolution(self) -> None:
        """
        Find the game's preset for the resolution in use and request the settings of the game, dropping older requests.

        :return: None
        """
        if self._game is None or self._presets is None or self._resolution_name is None:  # pragma: no cover
            return
        request: int = self._next_request()
        self._resolution = self._presets.preset_for(resolution=self._resolution_name)
        self._settings = None
        self._view.clear_settings(loading=self._resolution is not None)
        if self._resolution is None:
            self._set_status(status=self._texts.warning(item=UiText.NO_RECOMMENDATION))
            return
        game_id: str = self._game.game_id
        presets: GamePresets = self._presets
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._runner.submit(
            task=lambda: self._service.game_settings(game_id=game_id, presets=presets),
            on_done=lambda settings: self._on_settings(request=request, settings=settings),
            on_error=lambda error: self._on_request_error(request=request, error=error),
        )

    def _on_settings(self, *, request: int, settings: GameSettings) -> None:
        """
        Show the recommended preset of the resolution in use.

        :param request: number of the request
        :param settings: all presets of the game
        :return: None
        """
        if request != self._request or self._resolution is None:
            return
        self._settings = settings
        self._preset_index = self._resolution.preset_index
        self._set_status(status=self._resolution_note())
        self._render_settings()

    def _on_request_error(self, *, request: int, error: Exception) -> None:
        """
        Report a failed presets or settings request.

        :param request: number of the request
        :param error: the failure
        :return: None
        """
        if request != self._request:
            return
        self._view.clear_settings(loading=False)
        self._set_status(status=self._texts.error(item=UiText.REQUEST_FAILED, error=error))

    def _resolution_note(self) -> Status | None:
        """
        Tell what is special about the preset shown: another resolution than the one in use, or hardware too weak.

        :return: the note, a warning; None when there is nothing to tell
        """
        if self._resolution is None or self._resolution_name is None:  # pragma: no cover
            return None
        if self._resolution.resolution != self._resolution_name:
            return self._texts.warning(
                item=UiText.RESOLUTION_FALLBACK, chosen=self._resolution_name, shown=self._resolution.resolution
            )
        if self._resolution.below_min_spec:
            return self._texts.warning(item=UiText.RESOLUTION_BELOW_MIN_SPEC)
        return None

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

    def _update_database_once(self) -> None:
        """
        Update the database the first time the hardware is answered for: the start is not delayed by a download.

        :return: None
        """
        if not self._database_checked:
            self._database_checked = True
            self._update_database()

    def _update_database(self) -> None:
        """
        Update the database if one is due; a failure is only logged, the database in use stays.

        :return: None
        """
        self._runner.submit(
            task=self._service.update_database_if_due, on_done=self._on_database_update, on_error=lambda _: None
        )

    def _on_database_update(self, result: DatabaseUpdate) -> None:
        """
        Read the choice lists and the games again and search for installed games when a new database is in use.

        The chosen game is matched by its identifier and stays chosen when the new database still has it; otherwise
        the first game of the tab is chosen.

        :param result: outcome of the update
        :return: None
        """
        if result is not DatabaseUpdate.UPDATED:
            return
        if self._setup is not None:
            self._runner.submit(
                task=self._service.hardware_setup, on_done=self._on_setup_refresh, on_error=lambda _: None
            )
        games: tuple[Game, ...] = self._service.games()
        if self._game is not None:
            game_id: str = self._game.game_id
            self._game = next((game for game in games if game.game_id == game_id), self._game)
        self._set_games(games=games)
        self.find_games()

    def _on_setup_refresh(self, setup: HardwareSetup) -> None:
        """
        Take the choice lists of a new database; the hardware and resolution in use stay as they are.

        :param setup: detected hardware, bundled lists and what is saved
        :return: None
        """
        self._setup = setup

    def _render_hardware(self) -> None:
        """
        Show the CPU, GPU and resolution in use and the memory sizes; a missing component's link invites a choice.

        :return: None
        """
        if self._setup is None:
            loading: str = self._translator.text(item=UiText.LOADING)
            self._view.show_hardware(
                hardware=HardwareView(cpu=loading, gpu=loading, resolution=loading, memory="", video_memory="")
            )
            return
        gpu: Gpu | None = self._choice.gpu
        self._view.show_hardware(
            hardware=HardwareView(
                cpu=self._choice.cpu_name or self._translator.text(item=UiText.CHOOSE_CPU),
                gpu=self._translator.text(item=UiText.CHOOSE_GPU) if gpu is None else gpu.name,
                resolution=self._resolution_name or "",
                memory=self._size(gb=self._setup.system.memory_gb),
                video_memory=(
                    self._translator.text(item=UiText.UNKNOWN)
                    if gpu is None or gpu.memory_gb is None
                    else self._size(gb=gpu.memory_gb)
                ),
            )
        )

    def _size(self, *, gb: float) -> str:
        """
        Write a memory size: 16 -> "16 GB", 7.5 -> "7.5 GB".

        :param gb: size in GiB
        :return: the size in the current language
        """
        return self._translator.text(item=UiText.SIZE_GB, size=f"{gb:g}")

    def _render_settings(self) -> None:
        """
        Show the preset at the slider position.

        :return: None
        """
        if self._settings is None or self._resolution is None or self._game is None:  # pragma: no cover
            return
        language: str = self._translator.nvidia_language
        optimal: bool = self._preset_index == self._resolution.preset_index
        rows: tuple[tuple[str, str], ...] = self._settings.rows(index=self._preset_index, language=language)
        recommended: tuple[tuple[str, str], ...] = self._settings.rows(
            index=self._resolution.preset_index, language=language
        )
        self._view.show_settings(
            settings=SettingsView(
                title=self._game.name,
                position=f"{self._preset_index} / {self._settings.count}",
                caption=self._translator.text(item=UiText.OPTIMAL_PRESET if optimal else UiText.PRESET),
                rows=tuple(
                    SettingRow(name=name, value=value, changed=value != recommended_value)
                    for (name, value), (_, recommended_value) in zip(rows, recommended, strict=True)
                ),
                count=self._settings.count,
                index=self._preset_index,
                recommended=self._resolution.preset_index,
                optimal=optimal,
            )
        )

    def _clear_game(self, *, loading: bool) -> None:
        """
        Forget the presets and settings shown for a game, dropping requests still running.

        :param loading: True when the settings of a game are about to be requested
        :return: None
        """
        self._next_request()
        self._presets = None
        self._resolution = None
        self._settings = None
        self._view.clear_settings(loading=loading)

    def _next_request(self) -> int:
        """
        Number a new request, which makes every earlier one stale.

        :return: number of the request
        """
        self._request += 1
        return self._request

    def _set_status(self, *, status: Status | None) -> None:
        """
        Show the status line and keep it for language switches.

        :param status: the line, None to clear it
        :return: None
        """
        self._status = status
        if status is None:
            self._view.show_status(text="", level=StatusLevel.INFO)
        else:
            self._view.show_status(text=status.text(), level=status.level)
