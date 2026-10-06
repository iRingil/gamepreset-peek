"""Application constants: names, paths and HTTP settings."""

import os
from pathlib import Path

__all__: tuple[str, ...] = (
    "APP_NAME",
    "APP_DATA_DIR",
    "HTTP_CONNECT_TIMEOUT",
    "HTTP_MAX_RETRIES",
    "HTTP_READ_TIMEOUT",
    "HTTP_RETRY_BACKOFF",
    "LOG_FILE",
    "USER_AGENT_OS",
)

APP_NAME: str = "GamePresetPeek"
APP_DATA_DIR: Path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
LOG_FILE: Path = APP_DATA_DIR / "logs" / "gamepreset-peek.log"

# Operating systems a fake browser User-Agent is picked for, one per HTTP client.
USER_AGENT_OS: tuple[str, ...] = ("Windows",)
HTTP_CONNECT_TIMEOUT: float = 5.0
# Longest allowed pause between received bytes, not a limit on the whole response.
HTTP_READ_TIMEOUT: float = 15.0
HTTP_MAX_RETRIES: int = 2
# Delay before retry n (0-based) is HTTP_RETRY_BACKOFF * 2 ** n seconds.
HTTP_RETRY_BACKOFF: float = 0.5
