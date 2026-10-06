"""Application constants: names and paths."""

import os
from pathlib import Path

__all__: tuple[str, ...] = ("APP_NAME", "APP_DATA_DIR", "LOG_FILE")

APP_NAME: str = "GamePresetPeek"
APP_DATA_DIR: Path = Path(os.environ["LOCALAPPDATA"]) / APP_NAME
LOG_FILE: Path = APP_DATA_DIR / "logs" / "gamepreset-peek.log"
