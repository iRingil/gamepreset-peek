"""Tests of the saved user settings."""

from pathlib import Path

import pytest

from app.core.models import Gpu, UserSettings
from app.core.user_settings import UserSettingsStore

__all__: tuple = ()


class TestUserSettingsStore:
    """Loading and saving the settings file."""

    @pytest.fixture(name="path")
    def _path(self, tmp_path: Path) -> Path:
        """
        Place the settings file in a folder that does not exist yet.

        :param tmp_path: temporary directory
        :return: path of the settings file
        """
        return tmp_path / "GamePresetPeek" / "settings.json"

    def test_missing_file(self, path: Path) -> None:
        """
        Gives the defaults when nothing was saved.

        :param path: settings file path
        :return: None
        """
        # Arrange & Act
        settings: UserSettings = UserSettingsStore(path=path).load()
        # Assert
        assert settings == UserSettings()

    @pytest.mark.parametrize(
        argnames="settings",
        argvalues=[
            UserSettings(language="ru", gpu=Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507")),
            UserSettings(language="de"),
            UserSettings(),
        ],
        ids=["language and gpu", "language only", "defaults"],
    )
    def test_round_trip(self, path: Path, settings: UserSettings) -> None:
        """
        Loads what was saved, creating the folder on save.

        :param path: settings file path
        :param settings: settings to save
        :return: None
        """
        # Arrange
        store: UserSettingsStore = UserSettingsStore(path=path)
        # Act
        store.save(settings=settings)
        loaded: UserSettings = store.load()
        # Assert
        assert loaded == settings

    @pytest.mark.parametrize(
        argnames="content",
        argvalues=[
            "{not json",
            "[]",
            '{"language": 1}',
            '{"gpu": "NVIDIA GeForce RTX 3050"}',
            '{"gpu": {"name": "NVIDIA GeForce RTX 3050"}}',
            '{"gpu": {"name": "NVIDIA GeForce RTX 3050", "device_id": 9479}}',
        ],
        ids=["not json", "not an object", "language not a string", "gpu not an object", "no device id", "int id"],
    )
    def test_broken_file(self, path: Path, content: str) -> None:
        """
        Gives the defaults instead of failing on a broken file.

        :param path: settings file path
        :param content: content of the file
        :return: None
        """
        # Arrange
        path.parent.mkdir(parents=True)
        path.write_text(data=content, encoding="utf-8")
        # Act
        settings: UserSettings = UserSettingsStore(path=path).load()
        # Assert
        assert settings == UserSettings()
