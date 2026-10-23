"""UI logic of the main window: user actions -> service calls in the background -> what the window shows."""

from dataclasses import replace
from pathlib import Path
from typing import Callable, Sequence

from app.config import LOCALE_DIR, REQUEST_DELAY_MS, SEARCH_DELAY_MS
from app.core.models import (
    DatabaseUpdate,
    Game,
    GamePresets,
    GameSettings,
    Gpu,
    Hardware,
    HardwareCheck,
    HardwareChoice,
    HardwareSetup,
    HardwareState,
    ResolutionPreset,
    ThemeMode,
)
from app.core.service import PresetService
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.debouncer import Debouncer
from app.ui.views import ChoiceGroup, ChoiceView, HardwareView, MainView, SettingRow, SettingsView
from app.ui.worker import TaskRunner

__all__: tuple[str, ...] = ("Presenter",)


class Presenter:  # pylint: disable=too-many-instance-attributes
    """Drives the main window: every blocking service call runs through the task runner.

    A chosen game's presets are requested once the selection rests for a moment, so stepping through the list sends
    no burst of requests; the settings of the resolution in use follow at once. Each request gets a number; an answer
    to a request made before the user changed the game or the resolution is dropped. Texts are kept as functions, so
    a language switch re-renders them.

    Why no presets can be requested stays in the status line until NVIDIA accepts the hardware.

    The database update runs once the first hardware check has answered, so a slow download never delays the start;
    a new database refreshes the game names and the choice lists."""

    _COMPONENTS: dict[str, UiText] = {
        "cpu": UiText.COMPONENT_CPU,
        "gpu": UiText.COMPONENT_GPU,
        "memory": UiText.COMPONENT_MEMORY,
        "os": UiText.COMPONENT_OS,
    }
    # Tabs of the bundled CPUs: vendor names, not translated.
    _AMD: str = "AMD"
    _INTEL: str = "Intel"
    # Debouncer keys.
    _PRESETS: str = "presets"
    _SEARCH: str = "search"

    def __init__(
        self,
        *,
        view: MainView,
        service: PresetService,
        runner: TaskRunner,
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
        :param debouncer: delays the preset requests and the search while the user is still changing them
        :param translator: translator of the initial UI language
        :param theme: initial theme mode
        :param auto_update: whether the database is updated automatically
        :param locale_dir: folder of the compiled catalogs, for language switches
        """
        self._view: MainView = view
        self._service: PresetService = service
        self._runner: TaskRunner = runner
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
        self._problem: Callable[[], str] | None = None
        self._games: tuple[Game, ...] = ()
        self._search: str = ""
        self._shown_games: tuple[Game, ...] = ()
        self._game: Game | None = None
        self._presets: GamePresets | None = None
        self._resolution: ResolutionPreset | None = None
        self._settings: GameSettings | None = None
        self._preset_index: int = 0
        self._request: int = 0
        self._status: Callable[[], str] | None = None

    @property
    def language(self) -> str:
        """
        Get the current UI language.

        :return: language code, e.g. "ru"
        """
        return self._translator.language

    def start(self) -> None:
        """
        Theme and translate the window, then request the game list and detect the hardware.

        :return: None
        """
        self._view.apply_theme(mode=self._theme)
        self._view.apply_language(translator=self._translator)
        self._view.show_auto_update(enabled=self._auto_update)
        self._render_hardware()
        self.load_games()
        self._runner.submit(task=self._service.hardware_setup, on_done=self._on_setup, on_error=self._on_setup_error)

    def load_games(self) -> None:
        """
        Request the game list.

        :return: None
        """
        self._view.show_load_games(visible=False)
        self._set_status(text=self._text(item=UiText.LOADING))
        self._runner.submit(task=self._service.games, on_done=self._on_games, on_error=self._on_games_error)

    def select_game(self, *, index: int) -> None:
        """
        Show the settings of a game, requesting its presets once the selection rests.

        :param index: position of the game in the list as shown, i.e. after the search
        :return: None
        """
        game: Game = self._shown_games[index]
        # The window reports its own selection of the chosen game too, e.g. after a search.
        if game == self._game:
            return
        self._game = game
        self._clear_game()
        if self._hardware is None:
            self._set_status(text=self._problem or self._text(item=UiText.LOADING))
            return
        self._set_status(text=self._text(item=UiText.LOADING))
        self._debouncer.call(key=self._PRESETS, delay_ms=REQUEST_DELAY_MS, action=self._request_presets)

    def search_games(self, *, text: str) -> None:
        """
        Show only the games whose name contains the text, ignoring case, once the typing rests.

        :param text: text typed by the user; empty shows every game
        :return: None
        """
        self._search = text.strip().casefold()
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
        self._set_status(text=self._status)
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
        options: tuple[str, ...] = self._cpu_options(setup=self._setup)
        groups: tuple[ChoiceGroup, ...] = ()
        if self._setup.amd_cpus or self._setup.intel_cpus:
            groups = (
                ChoiceGroup(title=self._AMD, items=self._setup.amd_cpus),
                ChoiceGroup(title=self._INTEL, items=self._setup.intel_cpus),
            )
        self._view.offer_cpus(
            choice=ChoiceView(
                detected=self._detected_cpus(setup=self._setup),
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
        options: tuple[Gpu, ...] = self._gpu_options(setup=self._setup)
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
        options: tuple[str, ...] = self._resolution_options(setup=self._setup)
        self._view.offer_resolutions(
            choice=ChoiceView(
                detected=self._detected_resolutions(setup=self._setup),
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
            self._choose(choice=replace(self._choice, cpu_name=self._cpu_options(setup=self._setup)[position]))

    def choose_gpu(self, *, position: int) -> None:
        """
        Use the GPU the user picked, checking it with NVIDIA.

        :param position: position in the GPU choice
        :return: None
        """
        if self._setup is not None:
            self._choose(choice=replace(self._choice, gpu=self._gpu_options(setup=self._setup)[position]))

    def choose_resolution(self, *, position: int) -> None:
        """
        Use the resolution the user picked, save it and show the settings of the game for it.

        :param position: position in the resolution choice
        :return: None
        """
        if self._setup is None:
            return
        resolution: str = self._resolution_options(setup=self._setup)[position]
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

    def _on_games(self, games: tuple[Game, ...]) -> None:
        """
        Fill the game list.

        :param games: games sorted by name
        :return: None
        """
        self._games = games
        self._render_games()
        self._set_status(text=self._problem)

    def _on_games_error(self, error: Exception) -> None:
        """
        Report a failed game list request and offer to repeat it.

        :param error: the failure
        :return: None
        """
        self._set_status(text=self._text(item=UiText.GAMES_FAILED, error=str(error)))
        self._view.show_load_games(visible=True)

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
        self._lose_hardware(text=self._text(item=UiText.HARDWARE_FAILED, error=str(error)))
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
                self._set_status(text=None)
            self._problem = None
            if self._game is not None:
                self._clear_game()
                self._request_presets()
        else:
            self._lose_hardware(text=self._problem_text(check=check))
        self._update_database_once()

    def _on_check_error(self, *, previous: HardwareChoice, error: Exception) -> None:
        """
        Report a failed hardware check; hardware in use stays in use and is shown again.

        :param previous: the CPU and GPU shown before the check
        :param error: the failure
        :return: None
        """
        text: Callable[[], str] = self._text(item=UiText.REQUEST_FAILED, error=str(error))
        if self._hardware is None:
            self._lose_hardware(text=text)
        else:
            self._choice = previous
            self._render_hardware()
            self._set_status(text=text)
        self._update_database_once()

    def _problem_text(self, *, check: HardwareCheck) -> Callable[[], str]:
        """
        Explain why presets can't be requested.

        :param check: a result other than READY
        :return: the explanation in the current language
        """
        if check.state is HardwareState.NO_NVIDIA_GPU:
            return self._text(item=UiText.NO_NVIDIA_GPU)
        if check.state is HardwareState.NO_CPU:
            return self._text(item=UiText.CPU_NOT_DETECTED)
        if check.failed == ("cpu",):
            return self._text(item=UiText.CPU_REJECTED)
        if check.failed == ("gpu",):
            return self._text(item=UiText.GPU_REJECTED)
        failed: tuple[str, ...] = check.failed
        return lambda: self._translator.text(
            item=UiText.HARDWARE_REJECTED,
            components=", ".join(
                self._translator.text(item=self._COMPONENTS[name]) if name in self._COMPONENTS else name
                for name in failed
            ),
        )

    def _lose_hardware(self, *, text: Callable[[], str]) -> None:
        """
        Stop using any hardware: nothing can be requested until NVIDIA accepts a CPU and GPU.

        :param text: why there is no hardware
        :return: None
        """
        self._hardware = None
        self._problem = text
        self._set_status(text=text)
        self._clear_game()

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
        self._set_status(text=self._text(item=UiText.LOADING))
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
        self._clear_settings()
        self._resolution = self._match(resolutions=self._presets.resolutions, wanted=self._resolution_name)
        if self._resolution is None:
            self._set_status(text=self._text(item=UiText.NO_RECOMMENDATION))
            return
        game_id: str = self._game.game_id
        presets: GamePresets = self._presets
        self._set_status(text=self._text(item=UiText.LOADING))
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
        self._set_status(text=self._resolution_note())
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
        self._set_status(text=self._text(item=UiText.REQUEST_FAILED, error=str(error)))

    def _resolution_note(self) -> Callable[[], str] | None:
        """
        Tell what is special about the preset shown: another resolution than the one in use, or hardware too weak.

        :return: the note in the current language, None when there is nothing to tell
        """
        if self._resolution is None or self._resolution_name is None:  # pragma: no cover
            return None
        if self._resolution.resolution != self._resolution_name:
            return self._text(
                item=UiText.RESOLUTION_FALLBACK, chosen=self._resolution_name, shown=self._resolution.resolution
            )
        if self._resolution.below_min_spec:
            return self._text(item=UiText.RESOLUTION_BELOW_MIN_SPEC)
        return None

    def _render_games(self) -> None:
        """
        Fill the game list with the games matching the search, keeping the chosen game selected when it is there.

        :return: None
        """
        self._shown_games = tuple(game for game in self._games if self._search in game.name.casefold())
        self._view.show_games(
            names=[game.name for game in self._shown_games],
            selected=self._shown_games.index(self._game) if self._game in self._shown_games else None,
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
        Read the choice lists and the game names again when a new database is in use.

        :param result: outcome of the update
        :return: None
        """
        if result is not DatabaseUpdate.UPDATED:
            return
        if self._setup is not None:
            self._runner.submit(
                task=self._service.hardware_setup, on_done=self._on_setup_refresh, on_error=lambda _: None
            )
        if self._games:
            games: tuple[Game, ...] = self._games
            self._runner.submit(
                task=lambda: self._service.rename_games(games=games),
                on_done=self._on_games_renamed,
                on_error=lambda _: None,
            )

    def _on_setup_refresh(self, setup: HardwareSetup) -> None:
        """
        Take the choice lists of a new database; the hardware and resolution in use stay as they are.

        :param setup: detected hardware, bundled lists and what is saved
        :return: None
        """
        self._setup = setup

    def _on_games_renamed(self, games: tuple[Game, ...]) -> None:
        """
        Show the game names of a new database, keeping the chosen game.

        :param games: games named again, sorted by name
        :return: None
        """
        self._games = games
        if self._game is not None:
            game_id: str = self._game.game_id
            self._game = next((game for game in games if game.game_id == game_id), self._game)
        self._render_games()

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
                optimal=optimal,
            )
        )

    def _clear_game(self) -> None:
        """
        Forget the presets and settings shown for a game, dropping requests still running.

        :return: None
        """
        self._next_request()
        self._presets = None
        self._clear_settings()

    def _clear_settings(self) -> None:
        """
        Hide the settings shown.

        :return: None
        """
        self._resolution = None
        self._settings = None
        self._view.clear_settings()

    def _next_request(self) -> int:
        """
        Number a new request, which makes every earlier one stale.

        :return: number of the request
        """
        self._request += 1
        return self._request

    def _set_status(self, *, text: Callable[[], str] | None) -> None:
        """
        Show the status line and keep it for language switches.

        :param text: the line in the current language, None to clear it
        :return: None
        """
        self._status = text
        self._view.show_status(text="" if text is None else text())

    def _text(self, *, item: UiText, **values: str) -> Callable[[], str]:
        """
        Make a text that translates itself into the UI language at the time it is shown.

        :param item: the text
        :param values: placeholder values by name
        :return: function giving the translated text
        """
        return lambda: self._translator.text(item=item, **values)

    @staticmethod
    def _detected_cpus(*, setup: HardwareSetup) -> tuple[str, ...]:
        """
        List the detected CPU.

        :param setup: hardware setup
        :return: the detected CPU name, nothing when none was detected
        """
        return () if setup.system.cpu_name is None else (setup.system.cpu_name,)

    @classmethod
    def _cpu_options(cls, *, setup: HardwareSetup) -> tuple[str, ...]:
        """
        List the CPUs in the order of the choice.

        :param setup: hardware setup
        :return: the detected CPU, then the AMD and the Intel ones
        """
        return cls._detected_cpus(setup=setup) + setup.amd_cpus + setup.intel_cpus

    @staticmethod
    def _gpu_options(*, setup: HardwareSetup) -> tuple[Gpu, ...]:
        """
        List the GPUs in the order of the choice.

        :param setup: hardware setup
        :return: the detected GPUs, then the bundled ones
        """
        return setup.system.gpus + setup.gpus

    @staticmethod
    def _detected_resolutions(*, setup: HardwareSetup) -> tuple[str, ...]:
        """
        List the detected screen resolution.

        :param setup: hardware setup
        :return: the detected resolution, nothing when none was detected
        """
        return () if setup.system.resolution is None else (setup.system.resolution,)

    @classmethod
    def _resolution_options(cls, *, setup: HardwareSetup) -> tuple[str, ...]:
        """
        List the resolutions in the order of the choice.

        :param setup: hardware setup
        :return: the detected resolution, then the bundled ones
        """
        return cls._detected_resolutions(setup=setup) + setup.resolutions

    @classmethod
    def _match(cls, *, resolutions: Sequence[ResolutionPreset], wanted: str) -> ResolutionPreset | None:
        """
        Find the preset of a resolution, or of the closest smaller one; the smallest when none is as small.

        :param resolutions: resolutions NVIDIA gave presets for
        :param wanted: resolution in use, e.g. "2560x1600"
        :return: the preset, None when NVIDIA gave none
        """
        by_size: list[ResolutionPreset] = sorted(resolutions, key=lambda item: cls._pixels(resolution=item.resolution))
        if not by_size:
            return None
        exact: ResolutionPreset | None = next((item for item in by_size if item.resolution == wanted), None)
        if exact is not None:
            return exact
        limit: int = cls._pixels(resolution=wanted)
        smaller: list[ResolutionPreset] = [item for item in by_size if cls._pixels(resolution=item.resolution) <= limit]
        return smaller[-1] if smaller else by_size[0]

    @staticmethod
    def _pixels(*, resolution: str) -> int:
        """
        Count the pixels of a resolution for comparison.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1080"
        :return: width times height, 0 for a malformed resolution
        """
        width: str
        height: str
        width, _, height = resolution.partition("x")
        return int(width) * int(height) if width.isdigit() and height.isdigit() else 0
