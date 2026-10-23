"""Every text the UI shows, as English source strings translated through gettext."""

from enum import StrEnum

__all__: tuple[str, ...] = ("UiText",)


class UiText(StrEnum):
    """A UI text; the value is the English source and the gettext message id.

    Placeholders use str.format syntax ({error}); a translation keeps every placeholder of its source."""

    GAME = "Game"
    RESOLUTION = "Resolution:"
    LANGUAGE = "Language"
    THEME = "Theme"
    THEME_AUTO = "Auto"
    THEME_LIGHT = "Light"
    THEME_DARK = "Dark"
    SEARCH = "Search"
    SETTING = "Setting"
    VALUE = "Value"
    LOAD_GAMES = "Load games"
    SHOW_LOGS = "Show logs"
    HIDE_LOGS = "Hide logs"
    LOADING = "Loading…"
    CPU = "CPU:"
    GPU = "GPU:"
    RAM = "RAM:"
    VRAM = "VRAM:"
    SIZE_GB = "{size} GB"
    UNKNOWN = "unknown"
    CHOOSE_CPU = "Choose a processor"
    CHOOSE_GPU = "Choose a graphics card"
    GAMES_FAILED = "Could not load the game list: {error}"
    REQUEST_FAILED = "Could not get data from NVIDIA: {error}"
    NO_RECOMMENDATION = "No recommendations"
    RESOLUTION_FALLBACK = "No preset for {chosen}: showing the one for {shown}."
    RESOLUTION_BELOW_MIN_SPEC = "Too demanding for this PC: even the lowest settings may stutter at this resolution."
    PERFORMANCE = "Performance"
    QUALITY = "Quality"
    PRESET = "preset"
    OPTIMAL_PRESET = "optimal preset"
    BACK_TO_OPTIMAL = "Back to optimal"
    NO_NVIDIA_GPU = "No NVIDIA graphics card found. This app recommends settings for NVIDIA graphics cards only."
    UNSUPPORTED_HARDWARE = (
        "GamePreset Peek works only with NVIDIA graphics cards and AMD or Intel processors."
        " Choose your processor and graphics card in the links at the top."
    )
    CPU_NOT_DETECTED = "Could not detect the processor. Choose yours from the list."
    CPU_REJECTED = "NVIDIA does not know your processor. Choose it from the list."
    GPU_REJECTED = "NVIDIA does not know your graphics card. Choose the closest one from the list."
    HARDWARE_FAILED = "Could not detect the hardware: {error}"
    HARDWARE_REJECTED = "NVIDIA does not support this computer: {components}."
    COMPONENT_CPU = "processor"
    COMPONENT_GPU = "graphics card"
    COMPONENT_MEMORY = "memory"
    COMPONENT_OS = "Windows version"
