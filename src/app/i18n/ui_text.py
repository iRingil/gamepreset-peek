"""Every text the UI shows, as English source strings translated through gettext."""

from enum import StrEnum

__all__: tuple[str, ...] = ("UiText",)


class UiText(StrEnum):
    """A UI text; the value is the English source and the gettext message id.

    Placeholders use str.format syntax ({error}); a translation keeps every placeholder of its source."""

    GAME = "Game"
    RESOLUTION = "Resolution"
    LANGUAGE = "Language"
    SETTING = "Setting"
    VALUE = "Value"
    LOAD_GAMES = "Load games"
    SHOW_SETTINGS = "Show settings"
    SHOW_LOGS = "Show logs"
    HIDE_LOGS = "Hide logs"
    CHANGE_GPU = "Change graphics card"
    OK = "OK"
    CANCEL = "Cancel"
    LOADING = "Loading…"
    GAMES_FAILED = "Could not load the game list: {error}"
    REQUEST_FAILED = "Could not get data from NVIDIA: {error}"
    NO_RECOMMENDATION = "NVIDIA has no recommended settings for this game on your hardware."
    BELOW_MIN_SPEC = "below minimum requirements"
    NO_NVIDIA_GPU = "No NVIDIA graphics card found. NVIDIA recommends settings for NVIDIA graphics cards only."
    HARDWARE_REJECTED = "NVIDIA does not support this computer: {components}."
    COMPONENT_CPU = "processor"
    COMPONENT_GPU = "graphics card"
    COMPONENT_MEMORY = "memory"
    COMPONENT_OS = "Windows version"
    CHOOSE_GPU_TITLE = "Graphics card"
    CHOOSE_DETECTED_GPU = "Several NVIDIA graphics cards found. Choose the one you play on."
    CHOOSE_LISTED_GPU = "NVIDIA does not know your graphics card. Choose the closest one from the list."
