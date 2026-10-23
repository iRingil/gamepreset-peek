"""Settings kept between runs: language, theme, hardware, resolution and database updates; JSON in app data."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import SETTINGS_FILE
from app.core.models import Gpu, ThemeMode, UserSettings

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
            "theme": settings.theme.value,
            "detected_cpu": settings.detected_cpu,
            "detected_gpus": [self._gpu_document(gpu=gpu) for gpu in settings.detected_gpus],
            "detected_resolution": settings.detected_resolution,
            "chosen_cpu": settings.chosen_cpu,
            "chosen_gpu": None if settings.chosen_gpu is None else self._gpu_document(gpu=settings.chosen_gpu),
            "chosen_resolution": settings.chosen_resolution,
            "auto_update": settings.auto_update,
            "database_updated": None if settings.database_updated is None else settings.database_updated.isoformat(),
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
        detected_gpus: Any = document.get("detected_gpus", [])
        if not isinstance(detected_gpus, list):
            raise TypeError(f"expected a list, got {detected_gpus!r}")
        chosen_gpu: Any = document.get("chosen_gpu")
        return UserSettings(
            language=cls._optional_str(value=document.get("language")),
            theme=ThemeMode(cls._required_str(value=document.get("theme", ThemeMode.AUTO.value))),
            detected_cpu=cls._optional_str(value=document.get("detected_cpu")),
            detected_gpus=tuple(cls._gpu(document=gpu) for gpu in detected_gpus),
            detected_resolution=cls._optional_str(value=document.get("detected_resolution")),
            chosen_cpu=cls._optional_str(value=document.get("chosen_cpu")),
            chosen_gpu=None if chosen_gpu is None else cls._gpu(document=chosen_gpu),
            chosen_resolution=cls._optional_str(value=document.get("chosen_resolution")),
            auto_update=cls._bool(value=document.get("auto_update", True)),
            database_updated=cls._optional_date(value=document.get("database_updated")),
        )

    @staticmethod
    def _gpu_document(*, gpu: Gpu) -> dict[str, str]:
        """
        Make the JSON object of a GPU; its video memory is not saved.

        :param gpu: the GPU
        :return: name and device id
        """
        return {"name": gpu.name, "device_id": gpu.device_id}

    @classmethod
    def _gpu(cls, *, document: Any) -> Gpu:
        """
        Build a GPU from its JSON object.

        :param document: parsed JSON value
        :return: the GPU
        """
        if not isinstance(document, dict):
            raise TypeError(f"expected an object, got {document!r}")
        return Gpu(
            name=cls._required_str(value=document["name"]), device_id=cls._required_str(value=document["device_id"])
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

    @staticmethod
    def _bool(*, value: Any) -> bool:
        """
        Check that a value is a boolean.

        :param value: parsed JSON value
        :return: the value
        """
        if not isinstance(value, bool):
            raise TypeError(f"expected a boolean, got {value!r}")
        return value

    @classmethod
    def _optional_date(cls, *, value: Any) -> date | None:
        """
        Read a date written as "2026-10-23", or null.

        :param value: parsed JSON value
        :return: the date
        """
        return None if value is None else date.fromisoformat(cls._required_str(value=value))
