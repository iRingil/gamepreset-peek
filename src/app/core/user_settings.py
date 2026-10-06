"""Settings kept between runs: UI language and the GPU the user chose, as JSON in the app data folder."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import SETTINGS_FILE
from app.core.models import Gpu, UserSettings

__all__: tuple[str, ...] = ("UserSettingsStore",)


class UserSettingsStore:
    """Loads and saves the user settings; a missing or broken file gives the defaults instead of an error."""

    def __init__(self, *, path: Path = SETTINGS_FILE) -> None:
        """
        Use the given settings file.

        :param path: JSON file of the settings
        """
        self._path: Path = path

    def load(self) -> UserSettings:
        """
        Read the saved settings.

        :return: saved settings, or the defaults when the file is missing or broken
        """
        if not self._path.exists():
            logger.debug("No settings file {}", self._path)
            return UserSettings()
        try:
            settings: UserSettings = self._parse(document=json.loads(s=self._path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, KeyError) as error:
            logger.warning("Ignored broken settings file {}: {!r}", self._path, error)
            return UserSettings()
        logger.info("Loaded settings: {}", settings)
        return settings

    def save(self, *, settings: UserSettings) -> None:
        """
        Write the settings, creating the folder if needed.

        :param settings: settings to save
        :return: None
        """
        document: dict[str, Any] = {
            "language": settings.language,
            "gpu": (None if settings.gpu is None else {"name": settings.gpu.name, "device_id": settings.gpu.device_id}),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(data=json.dumps(obj=document, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved settings: {}", settings)

    @classmethod
    def _parse(cls, *, document: Any) -> UserSettings:
        """
        Build the settings from the JSON document of the file.

        :param document: parsed JSON
        :return: the settings
        """
        if not isinstance(document, dict):
            raise TypeError(f"expected an object, got {document!r}")
        gpu: Any = document.get("gpu")
        return UserSettings(
            language=cls._optional_str(value=document.get("language")),
            gpu=(
                None
                if gpu is None
                else Gpu(name=cls._required_str(value=gpu["name"]), device_id=cls._required_str(value=gpu["device_id"]))
            ),
        )

    @classmethod
    def _optional_str(cls, *, value: Any) -> str | None:
        """
        Check that a value is a string or null.

        :param value: parsed JSON value
        :return: the value
        """
        return None if value is None else cls._required_str(value=value)

    @staticmethod
    def _required_str(*, value: Any) -> str:
        """
        Check that a value is a string.

        :param value: parsed JSON value
        :return: the value
        """
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {value!r}")
        return value
