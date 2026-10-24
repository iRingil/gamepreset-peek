"""UI logic of the main window: user actions -> service calls in the background -> what the window shows."""

from dataclasses import replace
from pathlib import Path
from typing import Callable

from app.config import LOCALE_DIR, REQUEST_DELAY_MS
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
from app.ui.exe_icons import ExeIcons
from app.ui.games_presenter import GamesPresenter
from app.ui.resolution_choice import ResolutionChoice
from app.ui.status import Status, StatusTexts
from app.ui.views import (
    ChoiceGroup,
    ChoiceView,
    HardwareView,
    MainView,
    SettingRow,
    SettingsView,
    StatusLevel,
)
from app.ui.worker import Runners

__all__: tuple[str, ...] = ("Presenter",)


class Presenter:  # pylint: disable=too-many-instance-attributes
    """Drives the main window through background runners; the game tabs are driven by games, a GamesPresenter.

    A chosen game's presets are requested once the selection rests for a moment, so stepping through the list sends
    no burst of requests; the settings of the resolution in use follow at once. Each request gets a number; an answer
    to a request made before the user changed the game or the resolution is dropped. Texts are kept as functions, so
    a language switch re-renders them.

    Why no presets can be requested stays in the status line until NVIDIA accepts the hardware. A failed settings save
    is reported there too.

    The database update runs once the first hardware check has answered; a new database refreshes the games, the
    installed ones and the choice lists."""

    # Tabs of the bundled CPUs: vendor names, not translated.
    _AMD: str = "AMD"
    _INTEL: str = "Intel"
    # Debouncer key.
    _PRESETS: str = "presets"

    def __init__(
        self,
        *,
        view: MainView,
        service: PresetService,
        runners: Runners,
        debouncer: Debouncer,
        icons: ExeIcons,
        translator: Translator,
        theme: ThemeMode,
        auto_update: bool,
        locale_dir: Path = LOCALE_DIR,
    ) -> None:
        """
        Wire the presenter; nothing is requested before start().

        :param view: the window
        :param service: service the requests go to
        :param runners: run the service calls in the background
        :param debouncer: delays the requests and the search while the user is still changing them
        :param icons: icons of the installed games' executables
        :param translator: translator of the initial UI language
        :param theme: initial theme mode
        :param auto_update: whether the database is updated automatically
        :param locale_dir: folder of the compiled catalogs, for language switches
        """
        self._view: MainView = view
        self._service: PresetService = service
        self._runners: Runners = runners
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
        self._offered_cpus: tuple[str, ...] = ()
        self._offered_gpus: tuple[Gpu, ...] = ()
        self._offered_resolutions: tuple[str, ...] = ()
        self._problem: Status | None = None
        self._presets: GamePresets | None = None
        self._resolution: ResolutionPreset | None = None
        self._settings: GameSettings | None = None
        self._preset_index: int = 0
        self._request: int = 0
        self._status: Status | None = None
        self._texts: StatusTexts = StatusTexts(translator=lambda: self._translator)
        self.games: GamesPresenter = GamesPresenter(
            view=view,
            service=service,
            runners=runners,
            debouncer=debouncer,
            icons=icons,
            texts=self._texts,
            on_game=self._on_game,
            on_status=lambda status: self._set_status(status=status),
            save=self._save,
        )

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
        self._view.clear_settings(loading=False)
        self.games.start()
        self._runners.requests.submit(
            task=self._service.hardware_setup, on_done=self._on_setup, on_error=self._on_setup_error
        )
        self.games.load_folders()

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
        self._save(lambda: self._service.save_language(language=language))
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
        self._save(lambda: self._service.save_theme(theme=mode))
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
        self._save(lambda: self._service.save_auto_update(enabled=enabled))
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
        # A pick maps to this list even if a new database replaces the lists while the choice is open.
        self._offered_cpus = options
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
        self._offered_gpus = options
        self._view.offer_gpus(
            choice=ChoiceView(
                detected=tuple(gpu.name for gpu in self._setup.system.gpus),
                groups=(ChoiceGroup(title="", items=tuple(gpu.name for gpu in self._setup.gpus)),),
                selected=options.index(self._choice.gpu) if self._choice.gpu in options else None,
            )
        )

    def open_resolution_choice(self) -> None:
        """
        Offer the detected screen resolution, then the game's resolutions, the one in use selected.

        :return: None
        """
        if self._setup is None:
            return
        choice: ChoiceView = ResolutionChoice.build(
            setup=self._setup, presets=self._presets, in_use=self._resolution_name, translator=self._translator
        )
        # A pick maps to this list even if the game's presets arrive while the choice is open.
        self._offered_resolutions = choice.detected + choice.groups[0].items
        self._view.offer_resolutions(choice=choice)

    def choose_cpu(self, *, position: int) -> None:
        """
        Use the CPU the user picked, checking it with NVIDIA.

        :param position: position in the CPU choice
        :return: None
        """
        if 0 <= position < len(self._offered_cpus):
            self._choose(choice=replace(self._choice, cpu_name=self._offered_cpus[position]))

    def choose_gpu(self, *, position: int) -> None:
        """
        Use the GPU the user picked, checking it with NVIDIA.

        :param position: position in the GPU choice
        :return: None
        """
        if 0 <= position < len(self._offered_gpus):
            self._choose(choice=replace(self._choice, gpu=self._offered_gpus[position]))

    def choose_resolution(self, *, position: int) -> None:
        """
        Use the resolution the user picked, save it and show the settings of the game for it.

        :param position: position in the resolution choice
        :return: None
        """
        if self._setup is None or position >= len(self._offered_resolutions):
            return
        resolution: str = self._offered_resolutions[position]
        if resolution == self._resolution_name:
            return
        self._resolution_name = resolution
        self._save(lambda: self._service.save_resolution(resolution=resolution))
        self._render_hardware()
        if self._presets is not None:
            self._apply_resolution()

    def _on_game(self, game: Game | None) -> None:
        """
        Show the settings of another chosen game, requested once the choice rests.

        :param game: the game, None when the tab has none
        :return: None
        """
        if game is None:
            self._clear_game(loading=False)
            self._set_status(status=self._problem)
            return
        self._clear_game(loading=self._hardware is not None)
        if self._hardware is None:
            self._set_status(status=self._problem or self._texts.info(item=UiText.LOADING))
            return
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._debouncer.call(key=self._PRESETS, delay_ms=REQUEST_DELAY_MS, action=self._request_presets)

    def _save(self, task: Callable[[], None]) -> None:
        """
        Save a setting in the background; a failure is reported in the status line.

        :param task: the save
        :return: None
        """
        self._runners.saver.submit(
            task=task,
            on_done=lambda _: None,
            on_error=lambda error: self._set_status(status=self._texts.error(item=UiText.SAVE_FAILED, error=error)),
        )

    def _on_setup(self, setup: HardwareSetup) -> None:
        """
        Show the hardware and resolution in use and check the hardware.

        :param setup: detected hardware, bundled lists and what is in use
        :return: None
        """
        self._setup = setup
        self._choice = setup.choice
        self._resolution_name = setup.resolution
        self._render_hardware()
        choice: HardwareChoice = setup.choice
        self._runners.requests.submit(
            task=lambda: self._service.check_hardware(choice=choice),
            on_done=self._on_hardware,
            on_error=lambda error: self._on_check_error(previous=choice, error=error),
        )

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
        Show a new CPU and GPU pair at once and have NVIDIA check it; a check that fails to answer keeps the old pair.

        :param choice: the pair the user made
        :return: None
        """
        if choice == self._choice and self._hardware is not None:
            return
        previous: HardwareChoice = self._choice
        self._choice = choice
        self._render_hardware()
        self._runners.requests.submit(
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
            if self.games.game is not None:
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
        game: Game | None = self.games.game
        if game is None or self._hardware is None:
            return
        request: int = self._next_request()
        game_id: str = game.game_id
        hardware: Hardware = self._hardware
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._runners.requests.submit(
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
        game: Game | None = self.games.game
        if game is None or self._presets is None or self._resolution_name is None:  # pragma: no cover
            return
        request: int = self._next_request()
        self._resolution = self._presets.preset_for(resolution=self._resolution_name)
        self._settings = None
        if self._resolution is None:
            self._view.show_no_recommendation()
            self._set_status(status=self._texts.warning(item=UiText.NO_RECOMMENDATION))
            return
        self._view.clear_settings(loading=True)
        game_id: str = game.game_id
        presets: GamePresets = self._presets
        self._set_status(status=self._texts.info(item=UiText.LOADING))
        self._runners.requests.submit(
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
        self._runners.updater.submit(
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
            self._runners.requests.submit(
                task=self._service.hardware_setup, on_done=self._on_setup_refresh, on_error=lambda _: None
            )
        self.games.refresh(games=self._service.games())

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
        game: Game | None = self.games.game
        if self._settings is None or self._resolution is None or game is None:  # pragma: no cover
            return
        language: str = self._translator.nvidia_language
        optimal: bool = self._preset_index == self._resolution.preset_index
        rows: tuple[tuple[str, str], ...] = self._settings.rows(index=self._preset_index, language=language)
        recommended: tuple[tuple[str, str], ...] = self._settings.rows(
            index=self._resolution.preset_index, language=language
        )
        self._view.show_settings(
            settings=SettingsView(
                title=game.name,
                position=f"{self._preset_index} / {self._settings.count}",
                caption=self._translator.text(item=UiText.OPTIMAL_PRESET if optimal else UiText.PRESET),
                rows=tuple(
                    SettingRow(
                        name=name,
                        value=value,
                        changed=value != recommended_value,
                        hint=(
                            self._translator.text(item=UiText.CHANGED_HINT, value=recommended_value)
                            if value != recommended_value
                            else ""
                        ),
                    )
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
