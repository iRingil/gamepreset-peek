"""Tests of the data classes."""

import pytest

from app.core.models import (
    GamePresets,
    GameSettings,
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Setting,
    SettingTranslation,
    Translations,
)

__all__: tuple = ()


class TestPresetsFile:
    """Tests of PresetsFile.values."""

    @pytest.fixture(name="presets_file")
    def _presets_file(self) -> PresetsFile:
        """
        Build presets of two settings.

        :return: two presets of an ENUM and a FLOAT setting
        """
        return PresetsFile(
            settings=(Setting(name="Shadows", type="ENUM"), Setting(name="Scale", type="FLOAT")),
            presets=(("Low", "0.750"), ("High", "1.000")),
        )

    def test_values_by_one_based_index(self, presets_file: PresetsFile) -> None:
        """
        Pairs each setting with its value in the preset of the 1-based index.

        :param presets_file: presets of two settings
        :return: None
        """
        # Arrange & Act
        values: tuple[tuple[Setting, str], ...] = presets_file.values(index=2)
        # Assert
        assert values == (
            (Setting(name="Shadows", type="ENUM"), "High"),
            (Setting(name="Scale", type="FLOAT"), "1.000"),
        )

    def test_values_out_of_range(self, presets_file: PresetsFile) -> None:
        """
        Raises IndexError for an index past the last preset.

        :param presets_file: presets of two settings
        :return: None
        """
        # Act & Assert
        with pytest.raises(IndexError):
            presets_file.values(index=3)


class TestTranslations:
    """Tests of Translations lookups and their fallbacks."""

    @pytest.fixture(name="translations")
    def _translations(self) -> Translations:
        """
        Build Russian translations of one setting, one of its values left untranslated.

        :return: translations
        """
        return Translations(
            languages={
                "ru_RU": {
                    "Shadows": SettingTranslation(name="Тени", values={"Low": "Низкое", "High": ""}),
                    "Scale": SettingTranslation(name="", values={}),
                }
            }
        )

    @pytest.mark.parametrize(
        argnames=("language", "setting", "expected"),
        argvalues=(
            ("ru_RU", "Shadows", "Тени"),
            ("ru_RU", "Scale", "Scale"),
            ("ru_RU", "Missing", "Missing"),
            ("de_DE", "Shadows", "Shadows"),
        ),
        ids=("translated", "empty-translation", "unknown-setting", "unknown-language"),
    )
    def test_setting_name(self, translations: Translations, language: str, setting: str, expected: str) -> None:
        """
        Translates a setting name, falling back to the name when there is no translation.

        :param translations: Russian translations
        :param language: language to translate to
        :param setting: setting name
        :param expected: expected result
        :return: None
        """
        # Arrange & Act
        name: str = translations.setting_name(language=language, setting=setting)
        # Assert
        assert name == expected

    @pytest.mark.parametrize(
        argnames=("language", "setting", "value", "expected"),
        argvalues=(
            ("ru_RU", "Shadows", "Low", "Низкое"),
            ("ru_RU", "Shadows", "High", "High"),
            ("ru_RU", "Scale", "0.750", "0.750"),
            ("ru_RU", "Missing", "Low", "Low"),
            ("de_DE", "Shadows", "Low", "Low"),
        ),
        ids=("translated", "empty-translation", "numeric", "unknown-setting", "unknown-language"),
    )
    def test_value_name(
        self, translations: Translations, language: str, setting: str, value: str, expected: str
    ) -> None:
        """
        Translates a value, falling back to the value itself when there is no translation.

        :param translations: Russian translations
        :param language: language to translate to
        :param setting: setting name
        :param value: setting value
        :param expected: expected result
        :return: None
        """
        # Arrange & Act
        name: str = translations.value_name(language=language, setting=setting, value=value)
        # Assert
        assert name == expected


class TestGameSettings:
    """Tests of GameSettings.count and rows."""

    @pytest.fixture(name="settings")
    def _settings(self) -> GameSettings:
        """
        Build two presets of an ENUM and a FLOAT setting with Russian translations.

        :return: game settings
        """
        return GameSettings(
            presets=PresetsFile(
                settings=(Setting(name="Shadows", type="ENUM"), Setting(name="Scale", type="FLOAT")),
                presets=(("Low", "0.750"), ("High", "1.000")),
            ),
            translations=Translations(
                languages={
                    "ru_RU": {
                        "Shadows": SettingTranslation(name="Тени", values={"Low": "Низкое", "High": "Высокое"}),
                        "Scale": SettingTranslation(name="Масштаб", values={}),
                    }
                }
            ),
        )

    def test_count(self, settings: GameSettings) -> None:
        """
        Counts the presets.

        :param settings: two presets
        :return: None
        """
        # Arrange & Act
        count: int = settings.count
        # Assert
        assert count == 2

    @pytest.mark.parametrize(
        argnames=("index", "expected"),
        argvalues=[(1, (("Тени", "Низкое"), ("Масштаб", "0.750"))), (2, (("Тени", "Высокое"), ("Масштаб", "1.000")))],
        ids=["lowest", "highest"],
    )
    def test_rows_translated(self, settings: GameSettings, index: int, expected: tuple[tuple[str, str], ...]) -> None:
        """
        Translates setting names and values of a preset, keeping values without a translation (numbers) as is.

        :param settings: two presets
        :param index: 1-based preset index
        :param expected: translated rows
        :return: None
        """
        # Arrange & Act
        rows: tuple[tuple[str, str], ...] = settings.rows(index=index, language="ru_RU")
        # Assert
        assert rows == expected


class TestGamePresets:
    """Tests of GamePresets."""

    def test_resolution_names(self) -> None:
        """
        Lists the resolutions of the game by pixel count, the largest first, whatever NVIDIA's order.

        :return: None
        """
        # Arrange
        presets: GamePresets = GamePresets(
            profile="regular",
            version="1",
            presets_file=RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1),
            resolutions=tuple(
                ResolutionPreset(resolution=name, preset_index=1, rate=40, below_min_spec=False)
                for name in ("1920x1200", "7680x4320", "1920x1080", "3840x2400", "3840x2160")
            ),
        )
        # Act
        names: tuple[str, ...] = presets.resolution_names
        # Assert
        assert names == ("7680x4320", "3840x2400", "3840x2160", "1920x1200", "1920x1080")
