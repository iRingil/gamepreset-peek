"""Application constants: names, paths, HTTP settings and NVIDIA endpoints."""

import os
from pathlib import Path

__all__: tuple[str, ...] = (
    "APP_NAME",
    "APP_DATA_DIR",
    "APP_DB",
    "APP_ICON_FILE",
    "APP_TITLE",
    "COVER_WIDTH",
    "COVERS_DIR",
    "APP_USER_MODEL_ID",
    "ASPECT_TOLERANCE",
    "DB_UPDATE_DAYS",
    "DB_UPDATE_URL",
    "DEFAULT_GAME_FOLDERS",
    "DEFAULT_LANGUAGE",
    "DEFAULT_RESOLUTION",
    "FLAGS_DIR",
    "FONT_FILE",
    "GAME_SEARCH_DEPTH",
    "GETTEXT_DOMAIN",
    "HTTP_CONNECT_TIMEOUT",
    "HTTP_MAX_RETRIES",
    "HTTP_READ_TIMEOUT",
    "HTTP_RETRY_BACKOFF",
    "ICONS_DIR",
    "LANGUAGE_NAMES",
    "LOCALE_DIR",
    "LOG_FILE",
    "LOG_PANEL_HEIGHT",
    "LOG_PANEL_MAX_LINES",
    "LOG_POLL_MS",
    "OPS_COMMON_FILES_URL",
    "OPS_COMPATIBILITY_URL",
    "OPS_PRESETS_URL",
    "REQUEST_DELAY_MS",
    "SCREEN_RESOLUTIONS",
    "SEARCH_DELAY_MS",
    "SETTINGS_FILE",
    "TRANSLATION_LANGUAGES",
    "UI_LANGUAGES",
    "USER_AGENT_OS",
    "WINDOW_MIN_SIZE",
    "WINDOW_SIZE",
)

APP_NAME: str = "GamePresetPeek"
APP_TITLE: str = "GamePreset Peek"
# Own taskbar identity, so the window shows its icon instead of python.exe's when run from source.
APP_USER_MODEL_ID: str = "GamePresetPeek.App"
APP_DATA_DIR: Path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
LOG_FILE: Path = APP_DATA_DIR / "logs" / "gamepreset-peek.log"
SETTINGS_FILE: Path = APP_DATA_DIR / "settings.json"
COVERS_DIR: Path = APP_DATA_DIR / "cache" / "covers"
# Width of a downloaded box art picture in pixels: twice the cover column, sharp at 200 % scale.
COVER_WIDTH: int = 440
# Bundled data files live next to the package code.
_DATA_DIR: Path = Path(__file__).parent / "data"
APP_DB: Path = _DATA_DIR / "app.db"
APP_ICON_FILE: Path = _DATA_DIR / "app.ico"
ICONS_DIR: Path = _DATA_DIR / "icons"
FLAGS_DIR: Path = _DATA_DIR / "flags"
FONT_FILE: Path = _DATA_DIR / "fonts" / "GolosText.ttf"
LOCALE_DIR: Path = Path(__file__).parent / "i18n" / "locale"
GETTEXT_DOMAIN: str = "messages"
# The latest database; a download replaces APP_DB in place (the build is a folder, so the file is writable).
DB_UPDATE_URL: str = "https://raw.githubusercontent.com/iRingil/gamepreset-peek/master/src/app/data/app.db"
# Days after a database update before the next one is downloaded.
DB_UPDATE_DAYS: int = 7

# UI languages and the NVIDIA translation language of each.
UI_LANGUAGES: dict[str, str] = {"en": "en_US", "ru": "ru_RU", "de": "de_DE", "fr": "fr_FR", "es": "es_ES"}
DEFAULT_LANGUAGE: str = "en"
# Shown in the language dropdown in the language itself, so a user finds theirs in any UI language.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}

# Main window: initial and smallest width and height, in pixels at 100 % scale.
# The smallest size fits a 1280x720 logical screen (1920x1080 at 150 %) under the taskbar and the title bar.
WINDOW_MIN_SIZE: tuple[int, int] = (1264, 640)
WINDOW_SIZE: tuple[int, int] = WINDOW_MIN_SIZE
# Visible lines of the log panel and the lines it keeps before dropping the oldest ones.
LOG_PANEL_HEIGHT: int = 15
LOG_PANEL_MAX_LINES: int = 2000
LOG_POLL_MS: int = 200
# Pause after the last change of the game selection before its presets are requested, and after the last key typed
# in the game search before the list is filtered: stepping through the list with the arrow keys sends no burst.
REQUEST_DELAY_MS: int = 300
SEARCH_DELAY_MS: int = 250

# Screen resolutions NVIDIA recommends presets for, the largest first; the detected one is offered on top of them.
SCREEN_RESOLUTIONS: tuple[str, ...] = (
    "7680x4320",
    "3840x2400",
    "3840x2160",
    "3440x1440",
    "2560x1600",
    "2560x1440",
    "2560x1080",
    "1920x1200",
    "1920x1080",
    "1680x1050",
    "1600x900",
    "1440x900",
    "1366x768",
    "1360x768",
    "1280x1024",
    "1280x720",
    "1024x768",
)
# Two resolutions have the same shape when their width-to-height ratios differ by at most this share (1366x768 is 16:9).
ASPECT_TOLERANCE: float = 0.03
# Used when the screen resolution is neither detected nor chosen.
DEFAULT_RESOLUTION: str = "1920x1080"

# Folders searched for installed games until the user changes the list; the ones missing on a computer are dropped.
DEFAULT_GAME_FOLDERS: tuple[str, ...] = (
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"D:\Games",
    r"C:\Games",
)
# Folder levels searched below a game folder: Steam\steamapps\common\<game> plus the deepest executable path.
GAME_SEARCH_DEPTH: int = 10

# Operating systems a fake browser User-Agent is picked for, one per HTTP client.
USER_AGENT_OS: tuple[str, ...] = ("Windows",)
HTTP_CONNECT_TIMEOUT: float = 5.0
# Longest allowed pause between received bytes, not a limit on the whole response.
HTTP_READ_TIMEOUT: float = 15.0
HTTP_MAX_RETRIES: int = 2
# Delay before retry n (0-based) is HTTP_RETRY_BACKOFF * 2 ** n seconds.
HTTP_RETRY_BACKOFF: float = 0.5

_OPS_HOST: str = "https://ops-gx.nvidia.com"
OPS_COMPATIBILITY_URL: str = f"{_OPS_HOST}/v4/ops-compatibility/"
# Templates filled with str.format.
OPS_PRESETS_URL: str = _OPS_HOST + "/v3/ops/{game_id}/"
OPS_COMMON_FILES_URL: str = _OPS_HOST + "/v3/applications/{game_id}/common-files-{profile}.json"
# Languages kept from a game's translation file: the ones the UI offers.
TRANSLATION_LANGUAGES: tuple[str, ...] = tuple(UI_LANGUAGES.values())
