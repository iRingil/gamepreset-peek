"""What the presenter shows: the view data of the window parts and the protocol of the window itself."""

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.core.models import ThemeMode
from app.i18n.translator import Translator

__all__: tuple[str, ...] = (
    "ChoiceGroup",
    "ChoiceView",
    "HardwareView",
    "MainView",
    "SettingRow",
    "SettingsView",
)


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

    Positions run through the detected items, then through the groups in order; selected is the one in use."""

    detected: tuple[str, ...]
    groups: tuple[ChoiceGroup, ...]
    selected: int | None


@dataclass(frozen=True, slots=True)
class SettingRow:
    """A row of the settings table; changed means the value differs from the one of the recommended preset."""

    name: str
    value: str
    changed: bool


@dataclass(frozen=True, slots=True)
class SettingsView:
    """What the settings panel shows for one preset, translated.

    The title is the game; position ("16 / 19") and caption name the preset the slider is on."""

    title: str
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
