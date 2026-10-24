"""Tests of the saved user settings."""

from datetime import date
from pathlib import Path

import pytest

from app.core.models import Gpu, ThemeMode, UserSettings
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
            UserSettings(
                language="ru",
                detected_cpu="13th Gen Intel(R) Core(TM) i9-13900HX",
                detected_gpus=(
                    Gpu(name="NVIDIA GeForce RTX 4090", device_id="2684"),
                    Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507"),
                ),
                detected_resolution="2560x1600",
                chosen_cpu="Intel(R) Core(TM) i7-14700K",
                chosen_gpu=Gpu(name="NVIDIA GeForce RTX 3050", device_id="2507"),
                chosen_resolution="1920x1080",
                theme=ThemeMode.DARK,
                auto_update=False,
                database_updated=date(2026, 10, 23),
                game_folders=(r"D:\Games", r"E:\SteamLibrary"),
            ),
            UserSettings(language="de"),
            UserSettings(game_folders=()),
            UserSettings(),
        ],
        ids=["everything", "language only", "no game folders", "defaults"],
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
            '{"chosen_gpu": "NVIDIA GeForce RTX 3050"}',
            '{"chosen_gpu": {"name": "NVIDIA GeForce RTX 3050"}}',
            '{"chosen_gpu": {"name": "NVIDIA GeForce RTX 3050", "device_id": 9479}}',
            '{"chosen_cpu": 1}',
            '{"detected_cpu": 1}',
            '{"detected_gpus": {"name": "NVIDIA GeForce RTX 3050", "device_id": "2507"}}',
            '{"detected_gpus": ["NVIDIA GeForce RTX 3050"]}',
            '{"detected_resolution": 1920}',
            '{"chosen_resolution": ["1920x1080"]}',
            '{"theme": "sepia"}',
            '{"theme": 1}',
            '{"auto_update": "yes"}',
            '{"database_updated": "yesterday"}',
            '{"database_updated": 20261023}',
            '{"game_folders": "D:\\\\Games"}',
            '{"game_folders": [1]}',
        ],
        ids=[
            "not json",
            "not an object",
            "language not a string",
            "gpu not an object",
            "no device id",
            "int id",
            "chosen cpu not a string",
            "detected cpu not a string",
            "detected gpus not a list",
            "detected gpu not an object",
            "detected resolution not a string",
            "chosen resolution not a string",
            "unknown theme",
            "theme not a string",
            "auto update not a boolean",
            "update date not a date",
            "update date not a string",
            "game folders not a list",
            "game folder not a string",
        ],
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

    def test_file_without_theme(self, path: Path) -> None:
        """
        Reads a file saved before the theme, the database update and the game folders existed with their defaults.

        :param path: settings file path
        :return: None
        """
        # Arrange
        path.parent.mkdir(parents=True)
        path.write_text(data='{"language": "de", "chosen_gpu": null}', encoding="utf-8")
        # Act
        settings: UserSettings = UserSettingsStore(path=path).load()
        # Assert
        assert settings == UserSettings(
            language="de", theme=ThemeMode.AUTO, auto_update=True, database_updated=None, game_folders=None
        )
