"""What the presenter shows: the view data of the window parts and the protocol of the window itself."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Sequence

from app.core.models import GamesTab, ThemeMode
from app.i18n.translator import Translator

__all__: tuple[str, ...] = (
    "ChoiceGroup",
    "ChoiceView",
    "HardwareView",
    "InstalledGameView",
    "MainView",
    "SettingRow",
    "SettingsView",
    "StatusLevel",
)


class StatusLevel(StrEnum):
    """How serious a status line is: it only informs, warns of something short of the request, or reports a failure."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class HardwareView:
    """The hardware block, translated: CPU, GPU and resolution in use (texts of their choice links), memory sizes."""

    cpu: str
    gpu: str
    resolution: str
    memory: str
    video_memory: str


@dataclass(frozen=True, slots=True)
class ChoiceGroup:
    """A part of a choice list below the line; with several groups each one is a tab named by its title."""

    title: str
    items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChoiceView:
    """A CPU, GPU or resolution choice: detected items above a line, bundled groups below it.

    Positions run through the detected items, then through the groups in order; selected is the one in use.

    Fitting bundled items, e.g. resolutions of the screen's shape, carry the fit mark with the fit hint on hover;
    warned items, e.g. resolutions too demanding for the hardware, carry the warning sign with the warn hint."""

    detected: tuple[str, ...]
    groups: tuple[ChoiceGroup, ...]
    selected: int | None
    fitting: frozenset[int] = frozenset()
    fit_mark: str = ""
    fit_hint: str = ""
    warned: frozenset[int] = frozenset()
    warn_hint: str = ""


@dataclass(frozen=True, slots=True)
class InstalledGameView:
    """A row of the installed games: the game's name and the executable its icon is taken from."""

    name: str
    executable: Path


@dataclass(frozen=True, slots=True)
class SettingRow:
    """A row of the settings table; changed means the value differs from the one of the recommended preset.

    The hint, shown on hover, gives a changed row the value of the recommended preset."""

    name: str
    value: str
    changed: bool
    hint: str = ""


@dataclass(frozen=True, slots=True)
class SettingsView:
    """What the settings panel shows for one preset, translated.

    The title is the game; position ("16 / 19") and caption name the preset the slider is on; recommended is the
    1-based index of the recommended preset."""

    title: str
    position: str
    caption: str
    rows: tuple[SettingRow, ...]
    count: int
    index: int
    recommended: int
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

    def show_auto_update(self, *, enabled: bool) -> None:
        """
        Show whether the database is updated automatically.

        :param enabled: True when it is
        :return: None
        """

    def show_hardware(self, *, hardware: HardwareView) -> None:
        """
        Show the CPU, GPU and resolution in use and the memory sizes.

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

    def offer_resolutions(self, *, choice: ChoiceView) -> None:
        """
        Open the resolution choice; a pick is passed to Presenter.choose_resolution.

        :param choice: resolutions to choose from
        :return: None
        """

    def show_status(self, *, text: str, level: StatusLevel) -> None:
        """
        Show progress, a warning or an error, colored by how serious it is; an empty text clears the line.

        :param text: the line to show
        :param level: how serious the line is
        :return: None
        """

    def warn(self, *, text: str) -> None:
        """
        Show a warning in a dialog the user closes with OK.

        :param text: the warning
        :return: None
        """

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Fill the list of all games.

        :param names: display names in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """

    def show_finding(self) -> None:
        """
        Show that the installed games are being searched for, until show_installed_games().

        :return: None
        """

    def show_installed_games(self, *, games: Sequence[InstalledGameView], selected: int | None) -> None:
        """
        Fill the list of installed games; an empty list invites the user to add a folder.

        :param games: installed games in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """

    def show_tab(self, *, tab: GamesTab) -> None:
        """
        Bring a game tab to the front.

        :param tab: the tab
        :return: None
        """

    def show_folders(self, *, folders: Sequence[str]) -> None:
        """
        Show the folders searched for games.

        :param folders: folders in the user's order
        :return: None
        """

    def show_cover(self, *, picture: Path | None) -> None:
        """
        Show the box art of the chosen game.

        :param picture: the picture file, None for a placeholder when the game has none
        :return: None
        """

    def clear_cover(self, *, loading: bool) -> None:
        """
        Show a placeholder shape instead of the box art.

        :param loading: True while the picture is on its way, False when no game is chosen
        :return: None
        """

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """

    def clear_settings(self, *, loading: bool) -> None:
        """
        Show placeholder shapes instead of the settings.

        :param loading: True while the settings are requested, False when there are none to wait for
        :return: None
        """

    def show_no_recommendation(self) -> None:
        """
        Show a big notice that NVIDIA has no recommendation, instead of the settings.

        :return: None
        """
