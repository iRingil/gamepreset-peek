"""Application constants: names, paths, HTTP settings and NVIDIA endpoints."""

import os
from pathlib import Path

__all__: tuple[str, ...] = (
    "APP_NAME",
    "APP_DATA_DIR",
    "DEFAULT_LANGUAGE",
    "GAME_NAMES_FILE",
    "GETTEXT_DOMAIN",
    "GPU_RANKS_FILE",
    "GPUS_FILE",
    "HTTP_CONNECT_TIMEOUT",
    "HTTP_MAX_RETRIES",
    "HTTP_READ_TIMEOUT",
    "HTTP_RETRY_BACKOFF",
    "LANGUAGE_NAMES",
    "LOCALE_DIR",
    "LOG_FILE",
    "OPS_CATALOG_URL",
    "OPS_COMMON_FILES_URL",
    "OPS_COMPATIBILITY_URL",
    "OPS_PRESETS_URL",
    "SETTINGS_FILE",
    "TRANSLATION_LANGUAGES",
    "UI_LANGUAGES",
    "USER_AGENT_OS",
)

APP_NAME: str = "GamePresetPeek"
APP_DATA_DIR: Path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
LOG_FILE: Path = APP_DATA_DIR / "logs" / "gamepreset-peek.log"
SETTINGS_FILE: Path = APP_DATA_DIR / "settings.json"
# Bundled data files live next to the package code.
_DATA_DIR: Path = Path(__file__).parent / "data"
GAME_NAMES_FILE: Path = _DATA_DIR / "game_names.json"
GPUS_FILE: Path = _DATA_DIR / "gpus.json"
GPU_RANKS_FILE: Path = _DATA_DIR / "gpu_ranks.json"
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
