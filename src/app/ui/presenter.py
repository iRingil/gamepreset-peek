"""UI logic of the main window: user actions -> service calls in the background -> what the window shows."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Protocol, Sequence

from app.config import LOCALE_DIR
from app.core.models import (
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
from app.ui.worker import TaskRunner

__all__: tuple[str, ...] = (
    "ChoiceGroup",
    "ChoiceView",
    "HardwareView",
    "Hint",
    "MainView",
    "Presenter",
    "ResolutionRow",
    "SettingRow",
    "SettingsView",
)


@dataclass(frozen=True, slots=True)
class Hint:
    """A popup hint: a short title over a one-sentence text."""

    title: str
    text: str


@dataclass(frozen=True, slots=True)
class HardwareView:
    """The hardware block, translated: CPU and GPU in use (the texts of their choice links) and memory sizes."""

    cpu: str
    gpu: str
    memory: str
    video_memory: str


@dataclass(frozen=True, slots=True)
class ChoiceGroup:
    """A part of a choice list below the line; with several groups each one is a tab named by its title."""

    title: str
    items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChoiceView:
    """A CPU or GPU choice: detected items above a line, bundled groups below it.

    Positions run through the detected items, then through the groups in order; selected is the one in use."""

    detected: tuple[str, ...]
    groups: tuple[ChoiceGroup, ...]
    selected: int | None


@dataclass(frozen=True, slots=True)
class ResolutionRow:
    """A row of the resolution list; warning is the hint of its warning sign, None when the row has no sign."""

    resolution: str
    warning: Hint | None


@dataclass(frozen=True, slots=True)
class SettingRow:
    """A row of the settings table; changed means the value differs from the one of the recommended preset."""

    name: str
    value: str
    changed: bool


@dataclass(frozen=True, slots=True)
class SettingsView:
    """What the settings panel shows for one preset, translated.

    The title is the game, the subtitle its resolution and target FPS; position ("16 / 19") and caption name the preset
    the slider is on."""

    title: str
    subtitle: str
    position: str
    caption: str
    rows: tuple[SettingRow, ...]
    count: int
    index: int
    optimal: bool


class MainView(Protocol):
    """The widgets the presenter fills; texts come translated."""

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the window: labels, buttons, headings.

        :param translator: translator of the UI language
        :return: None
        """

    def apply_theme(self, *, mode: ThemeMode) -> None:
        """
        Switch the colors of the window; AUTO follows the Windows app mode.

        :param mode: theme mode
        :return: None
        """

    def show_themes(self, *, names: Sequence[str], selected: int) -> None:
        """
        Fill the theme choice.

        :param names: theme names in list order
        :param selected: position of the theme in use
        :return: None
        """

    def show_hardware(self, *, hardware: HardwareView) -> None:
        """
        Show the CPU and GPU in use and the memory sizes.

        :param hardware: what to show
        :return: None
        """

    def offer_cpus(self, *, choice: ChoiceView) -> None:
        """
        Open the CPU choice; a pick is passed to Presenter.choose_cpu.

        :param choice: CPUs to choose from
        :return: None
        """

    def offer_gpus(self, *, choice: ChoiceView) -> None:
        """
        Open the GPU choice; a pick is passed to Presenter.choose_gpu.

        :param choice: GPUs to choose from
        :return: None
        """

    def show_status(self, *, text: str) -> None:
        """
        Show progress, an error or a notice; an empty text clears the line.

        :param text: the line to show
        :return: None
        """

    def warn(self, *, text: str) -> None:
        """
        Show a warning in a dialog the user closes with OK.

        :param text: the warning
        :return: None
        """

    def show_load_games(self, *, visible: bool) -> None:
        """
        Show or hide the button that requests the game list again.

        :param visible: True to show the button
        :return: None
        """

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Fill the game list.

        :param names: display names in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """

    def show_resolutions(self, *, items: Sequence[ResolutionRow]) -> None:
        """
        Fill the resolution list; an empty sequence clears it.

        :param items: resolution rows in list order
        :return: None
        """

    def show_settings_button(self, *, visible: bool) -> None:
        """
        Show or hide the "Show settings" button.

        :param visible: True to show the button
        :return: None
        """

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """

    def clear_settings(self) -> None:
        """
        Hide the settings table and the slider.

        :return: None
        """


class Presenter:  # pylint: disable=too-many-instance-attributes
    """Drives the main window: every blocking service call runs through the task runner.

    Each request for presets or settings gets a number; an answer to a request made before the user changed the game
    or the resolution is dropped. Texts are kept as functions, so a language switch re-renders them.

    Why no presets can be requested stays in the status line until NVIDIA accepts the hardware."""

    _THEMES: dict[ThemeMode, UiText] = {
        ThemeMode.AUTO: UiText.THEME_AUTO,
        ThemeMode.LIGHT: UiText.THEME_LIGHT,
        ThemeMode.DARK: UiText.THEME_DARK,
    }
    _COMPONENTS: dict[str, UiText] = {
        "cpu": UiText.COMPONENT_CPU,
        "gpu": UiText.COMPONENT_GPU,
        "memory": UiText.COMPONENT_MEMORY,
        "os": UiText.COMPONENT_OS,
    }
    # Tabs of the bundled CPUs: vendor names, not translated.
    _AMD: str = "AMD"
    _INTEL: str = "Intel"

    def __init__(
        self,
        *,
        view: MainView,
        service: PresetService,
        runner: TaskRunner,
        translator: Translator,
        theme: ThemeMode,
        locale_dir: Path = LOCALE_DIR,
    ) -> None:
        """
        Wire the presenter; nothing is requested before start().

        :param view: the window
        :param service: service the requests go to
        :param runner: runs service calls in the background
        :param translator: translator of the initial UI language
        :param theme: initial theme mode
        :param locale_dir: folder of the compiled catalogs, for language switches
        """
        self._view: MainView = view
        self._service: PresetService = service
        self._runner: TaskRunner = runner
        self._translator: Translator = translator
        self._locale_dir: Path = locale_dir
        self._theme: ThemeMode = theme
        self._setup: HardwareSetup | None = None
        self._choice: HardwareChoice = HardwareChoice(cpu_name=None, gpu=None)
        self._hardware: Hardware | None = None
        self._problem: Callable[[], str] | None = None
        self._games: tuple[Game, ...] = ()
        self._search: str = ""
        self._shown_games: tuple[Game, ...] = ()
        self._game: Game | None = None
        self._presets: GamePresets | None = None
        self._resolutions: tuple[ResolutionPreset, ...] = ()
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
        self._render_themes()
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
        Show the resolutions of a game, requesting its presets.

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
        self._request_presets()

    def select_resolution(self, *, index: int) -> None:
        """
        Pick a resolution: the settings shown before are cleared and the "Show settings" button comes back.

        :param index: position of the resolution in the list
        :return: None
        """
        resolution: ResolutionPreset = self._resolutions[index]
        # The window reports its own selection of the chosen resolution too, e.g. after a language switch.
        if resolution is self._resolution:
            return
        self._resolution = resolution
        self._next_request()
        self._clear_settings()
        self._view.show_settings_button(visible=True)
        self._set_status(text=None)

    def show_settings(self) -> None:
        """
        Show the recommended preset of the chosen resolution, requesting the game's presets unless cached.

        :return: None
        """
        if self._game is None or self._presets is None or self._resolution is None:
            return
        request: int = self._next_request()
        game_id: str = self._game.game_id
        presets: GamePresets = self._presets
        self._view.show_settings_button(visible=False)
        self._set_status(text=self._text(item=UiText.LOADING))
        self._runner.submit(
            task=lambda: self._service.game_settings(game_id=game_id, presets=presets),
            on_done=lambda settings: self._on_settings(request=request, settings=settings),
            on_error=lambda error: self._on_request_error(request=request, error=error),
        )

    def search_games(self, *, text: str) -> None:
        """
        Show only the games whose name contains the text, ignoring case.

        :param text: text typed by the user; empty shows every game
        :return: None
        """
        self._search = text.strip().casefold()
        self._render_games()

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
        self._render_themes()
        self._render_hardware()
        self._set_status(text=self._status)
        self._render_resolutions()
        if self._settings is not None:
            self._render_settings()

    def change_theme(self, *, index: int) -> None:
        """
        Switch the theme and save it.

        :param index: position of the theme in the theme choice
        :return: None
        """
        theme: ThemeMode = list(self._THEMES)[index]
        if theme is self._theme:
            return
        self._theme = theme
        self._runner.submit(
            task=lambda: self._service.save_theme(theme=theme), on_done=lambda _: None, on_error=lambda _: None
        )
        self._view.apply_theme(mode=theme)

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
        Show the hardware in use and check it; warn when a CPU or GPU is neither chosen nor detected.

        :param setup: detected hardware, bundled lists and the CPU and GPU in use
        :return: None
        """
        self._setup = setup
        self._choice = setup.choice
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
            return
        self._choice = previous
        self._render_hardware()
        self._set_status(text=text)

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
        Show the resolutions of a game, the largest first.

        :param request: number of the request
        :param presets: presets of the game
        :return: None
        """
        if request != self._request:
            return
        self._presets = presets
        self._resolutions = tuple(
            sorted(presets.resolutions, key=lambda item: self._pixels(resolution=item.resolution), reverse=True)
        )
        self._set_status(text=None if self._resolutions else self._text(item=UiText.NO_RECOMMENDATION))
        self._render_resolutions()

    def _on_settings(self, *, request: int, settings: GameSettings) -> None:
        """
        Show the recommended preset of the chosen resolution.

        :param request: number of the request
        :param settings: all presets of the game
        :return: None
        """
        if request != self._request or self._resolution is None:
            return
        self._settings = settings
        self._preset_index = self._resolution.preset_index
        self._set_status(text=None)
        self._render_settings()

    def _on_request_error(self, *, request: int, error: Exception) -> None:
        """
        Report a failed presets or settings request; the "Show settings" button comes back to retry.

        :param request: number of the request
        :param error: the failure
        :return: None
        """
        if request != self._request:
            return
        self._set_status(text=self._text(item=UiText.REQUEST_FAILED, error=str(error)))
        if self._resolution is not None and self._settings is None:
            self._view.show_settings_button(visible=True)

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

    def _render_themes(self) -> None:
        """
        Fill the theme choice in the UI language.

        :return: None
        """
        self._view.show_themes(
            names=[self._translator.text(item=item) for item in self._THEMES.values()],
            selected=list(self._THEMES).index(self._theme),
        )

    def _render_hardware(self) -> None:
        """
        Show the CPU and GPU in use and the memory sizes; a missing component's link invites a choice.

        :return: None
        """
        if self._setup is None:
            loading: str = self._translator.text(item=UiText.LOADING)
            self._view.show_hardware(hardware=HardwareView(cpu=loading, gpu=loading, memory="", video_memory=""))
            return
        gpu: Gpu | None = self._choice.gpu
        self._view.show_hardware(
            hardware=HardwareView(
                cpu=self._choice.cpu_name or self._translator.text(item=UiText.CHOOSE_CPU),
                gpu=self._translator.text(item=UiText.CHOOSE_GPU) if gpu is None else gpu.name,
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

    def _render_resolutions(self) -> None:
        """
        Fill the resolution list, marking with a warning the resolutions the hardware is too weak for.

        :return: None
        """
        warning: Hint = Hint(
            title=self._translator.text(item=UiText.RESOLUTION_BELOW_MIN_SPEC),
            text=self._translator.text(item=UiText.RESOLUTION_BELOW_MIN_SPEC_HINT),
        )
        self._view.show_resolutions(
            items=[
                ResolutionRow(resolution=item.resolution, warning=warning if item.below_min_spec else None)
                for item in self._resolutions
            ]
        )

    def _render_settings(self) -> None:
        """
        Show the preset at the slider position.

        :return: None
        """
        if self._settings is None or self._resolution is None or self._game is None:
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
                subtitle=self._translator.text(
                    item=UiText.SETTINGS_SUBTITLE,
                    resolution=self._resolution.resolution,
                    rate=str(self._resolution.rate),
                ),
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
        Forget the presets, resolutions and settings shown for a game, dropping requests still running.

        :return: None
        """
        self._next_request()
        self._presets = None
        self._resolutions = ()
        self._resolution = None
        self._view.show_resolutions(items=[])
        self._view.show_settings_button(visible=False)
        self._clear_settings()

    def _clear_settings(self) -> None:
        """
        Hide the settings shown.

        :return: None
        """
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
    def _pixels(*, resolution: str) -> int:
        """
        Count the pixels of a resolution for sorting.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1080"
        :return: width times height, 0 for a malformed resolution
        """
        width: str
        height: str
        width, _, height = resolution.partition("x")
        return int(width) * int(height) if width.isdigit() and height.isdigit() else 0
