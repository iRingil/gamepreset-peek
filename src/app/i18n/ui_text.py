"""Every text the UI shows, as English source strings translated through gettext."""

from enum import StrEnum

__all__: tuple[str, ...] = ("UiText",)


def _msg(text: str) -> str:
    """
    Mark a UI text for pybabel extract; gettext translates it when the text is shown.

    :param text: English source string
    :return: the text unchanged
    """
    return text


class UiText(StrEnum):
    """A UI text; the value is the English source and the gettext message id.

    Placeholders use str.format syntax ({error}); a translation keeps every placeholder of its source."""

    MY_GAMES = _msg("My games")
    ALL_GAMES = _msg("All games")
    GAME_FOLDERS = _msg("Where to look for games")
    ADD_FOLDER = _msg("Add a folder")
    CHANGE_FOLDER = _msg("Change the folder")
    REMOVE_FOLDER = _msg("Remove the folder")
    FIND_AGAIN = _msg("Search again")
    FIND_AGAIN_HINT = _msg("Search the folders in the list for installed games again")
    CHOOSE_FOLDER = _msg("Choose a folder with games")
    NO_GAMES_FOUND = _msg("No games found. Add the folder your games are installed in.")
    FIND_FAILED = _msg("Could not search for games: {error}")
    RESOLUTION = _msg("Resolution:")
    LANGUAGE = _msg("Language")
    THEME = _msg("Theme")
    THEME_AUTO = _msg("Auto")
    THEME_LIGHT = _msg("Light")
    THEME_DARK = _msg("Dark")
    SETTINGS = _msg("Settings")
    AUTO_UPDATE = _msg("Auto-update")
    AUTO_UPDATE_HINT = _msg("Downloads the latest lists of processors, graphics cards and games once a week.")
    SEARCH = _msg("Search")
    DETECTED = _msg("Detected")
    FITS_SCREEN = _msg("Same shape as your screen ({ratio}): fills it with no black bars or stretching.")
    SETTING = _msg("Setting")
    VALUE = _msg("Value")
    SHOW_LOGS = _msg("Show logs")
    HIDE_LOGS = _msg("Hide logs")
    LOADING = _msg("Loading…")
    CPU = _msg("CPU:")
    GPU = _msg("GPU:")
    RAM = _msg("RAM:")
    VRAM = _msg("VRAM:")
    SIZE_GB = _msg("{size} GB")
    UNKNOWN = _msg("unknown")
    CHOOSE_CPU = _msg("Choose a processor")
    CHOOSE_GPU = _msg("Choose a graphics card")
    CPU_HINT = _msg("Choose another processor")
    GPU_HINT = _msg("Choose another graphics card")
    RESOLUTION_HINT = _msg("Choose another screen resolution")
    REQUEST_FAILED = _msg("Could not get data from NVIDIA: {error}")
    SAVE_FAILED = _msg("Could not save the settings: {error}")
    ERROR_NO_CONNECTION = _msg("no connection, check your internet")
    ERROR_NO_ANSWER = _msg("the server is not answering, try again later")
    ERROR_HTTP = _msg("the server answered with error {status}")
    ERROR_BAD_ANSWER = _msg("the server sent data in an unexpected format")
    ERROR_UNEXPECTED = _msg("unexpected error, see the logs")
    NO_RECOMMENDATION_TITLE = _msg("No recommendations")
    NO_RECOMMENDATION = _msg(
        "No recommendations (there are none, or your hardware is too weak for this resolution and game)"
    )
    RESOLUTION_FALLBACK = _msg("No preset for {chosen}: showing the one for {shown}.")
    RESOLUTION_BELOW_MIN_SPEC = _msg(
        "Too demanding for this PC: even the lowest settings may stutter at this resolution."
    )
    PERFORMANCE = _msg("Performance")
    QUALITY = _msg("Quality")
    PRESET = _msg("preset")
    OPTIMAL_PRESET = _msg("optimal preset")
    OPTIMAL = _msg("Optimal")
    OPTIMAL_HINT = _msg("Go back to the preset NVIDIA recommends")
    SLIDER_HINT = _msg("Other presets NVIDIA has for this game; the dot marks the recommended one")
    CHANGED_HINT = _msg("Differs from the recommended preset ({value})")
    NO_NVIDIA_GPU = _msg(
        "No NVIDIA graphics card found. Choose yours from the list: the app works with NVIDIA cards only."
    )
    NOTHING_DETECTED = _msg("Could not detect the processor or an NVIDIA graphics card. Choose both from the lists.")
    CPU_NOT_DETECTED = _msg("Could not detect the processor. Choose yours from the list.")
    CPU_REJECTED = _msg("NVIDIA does not know your processor. Choose it from the list.")
    GPU_REJECTED = _msg("NVIDIA does not know your graphics card. Choose the closest one from the list.")
    HARDWARE_FAILED = _msg("Could not detect the hardware: {error}")
    READ_ONLY_FOLDER = _msg(
        "GamePreset Peek can't write to its folder:\n{folder}\n\nIt needs to, to keep its lists of games and hardware"
        " up to date. Reinstall it outside Program Files, or run it as administrator."
    )
    HARDWARE_REJECTED = _msg("NVIDIA does not support this computer: {components}.")
    COMPONENT_CPU = _msg("processor")
    COMPONENT_GPU = _msg("graphics card")
    COMPONENT_MEMORY = _msg("memory")
    COMPONENT_OS = _msg("Windows version")
