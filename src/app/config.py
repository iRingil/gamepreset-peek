"""Application constants: names, paths, HTTP settings and NVIDIA endpoints."""

import os
from pathlib import Path

__all__: tuple[str, ...] = (
    "APP_NAME",
    "APP_DATA_DIR",
    "APP_ICON_FILE",
    "APP_TITLE",
    "APP_USER_MODEL_ID",
    "DEFAULT_LANGUAGE",
    "GAME_NAMES_FILE",
    "GETTEXT_DOMAIN",
    "HARDWARE_DB",
    "HTTP_CONNECT_TIMEOUT",
    "HTTP_MAX_RETRIES",
    "HTTP_READ_TIMEOUT",
    "HTTP_RETRY_BACKOFF",
    "LANGUAGE_NAMES",
    "LOCALE_DIR",
    "LOG_FILE",
    "LOG_PANEL_HEIGHT",
    "LOG_PANEL_MAX_LINES",
    "LOG_POLL_MS",
    "OPS_CATALOG_URL",
    "OPS_COMMON_FILES_URL",
    "OPS_COMPATIBILITY_URL",
    "OPS_PRESETS_URL",
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
# Bundled data files live next to the package code.
_DATA_DIR: Path = Path(__file__).parent / "data"
GAME_NAMES_FILE: Path = _DATA_DIR / "game_names.json"
HARDWARE_DB: Path = _DATA_DIR / "hardware.db"
APP_ICON_FILE: Path = _DATA_DIR / "app.ico"
LOCALE_DIR: Path = Path(__file__).parent / "i18n" / "locale"
GETTEXT_DOMAIN: str = "messages"

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

# Operating systems a fake browser User-Agent is picked for, one per HTTP client.
USER_AGENT_OS: tuple[str, ...] = ("Windows",)
HTTP_CONNECT_TIMEOUT: float = 5.0
# Longest allowed pause between received bytes, not a limit on the whole response.
HTTP_READ_TIMEOUT: float = 15.0
HTTP_MAX_RETRIES: int = 2
# Delay before retry n (0-based) is HTTP_RETRY_BACKOFF * 2 ** n seconds.
HTTP_RETRY_BACKOFF: float = 0.5

_OPS_HOST: str = "https://ops-gx.nvidia.com"
OPS_CATALOG_URL: str = f"{_OPS_HOST}/v3/applications/applications-regular_rtx.json"
OPS_COMPATIBILITY_URL: str = f"{_OPS_HOST}/v4/ops-compatibility/"
# Templates filled with str.format.
OPS_PRESETS_URL: str = _OPS_HOST + "/v3/ops/{game_id}/"
OPS_COMMON_FILES_URL: str = _OPS_HOST + "/v3/applications/{game_id}/common-files-{profile}.json"
# Languages kept from a game's translation file: the ones the UI offers.
TRANSLATION_LANGUAGES: tuple[str, ...] = tuple(UI_LANGUAGES.values())
