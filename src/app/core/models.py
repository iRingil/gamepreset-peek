"""Data classes of the NVIDIA presets data and of the user's hardware."""

from dataclasses import dataclass

__all__: tuple[str, ...] = (
    "Compatibility",
    "GamePresets",
    "Hardware",
    "PresetsFile",
    "RemoteFile",
    "ResolutionPreset",
    "Setting",
    "SettingTranslation",
    "Translations",
)


@dataclass(frozen=True, slots=True)
class Hardware:
    """The user's hardware as NVIDIA expects it in the query string."""

    cpu_name: str
    gpu_name: str
    gpu_device_id: str
    memory_gb: int
    os_version: str


@dataclass(frozen=True, slots=True)
class Compatibility:
    """Result of NVIDIA's hardware compatibility check."""

    ok: bool
    failed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RemoteFile:
    """A file on NVIDIA's CDN with its checksum."""

    url: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class ResolutionPreset:
    """Preset recommended for one screen resolution."""

    resolution: str
    preset_index: int
    rate: int
    below_min_spec: bool


@dataclass(frozen=True, slots=True)
class GamePresets:
    """NVIDIA's answer to the preset request of a game: profile, presets file and the preset of each resolution."""

    profile: str
    version: str
    presets_file: RemoteFile
    resolutions: tuple[ResolutionPreset, ...]


@dataclass(frozen=True, slots=True)
class Setting:
    """A game setting; type is NVIDIA's as is, e.g. "ENUM", "INT", "FLOAT", "DRVENUM"."""

    name: str
    type: str


@dataclass(frozen=True, slots=True)
class PresetsFile:
    """All presets of a game; each preset holds one value per setting, in the order of settings."""

    settings: tuple[Setting, ...]
    presets: tuple[tuple[str, ...], ...]

    def values(self, *, index: int) -> tuple[tuple[Setting, str], ...]:
        """
        Pair every setting with its value in one preset.

        :param index: 1-based preset index, as in ResolutionPreset.preset_index
        :return: settings with their values, in the order of settings
        """
        return tuple(zip(self.settings, self.presets[index - 1], strict=True))


@dataclass(frozen=True, slots=True)
class SettingTranslation:
    """Translated name of a setting and of its values, keyed by the value as NVIDIA names it."""

    name: str
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class Translations:
    """Translated setting names and values of a game, keyed by NVIDIA language code and setting name."""

    languages: dict[str, dict[str, SettingTranslation]]

    def setting_name(self, *, language: str, setting: str) -> str:
        """
        Translate a setting name, falling back to the name itself.

        :param language: NVIDIA language code, e.g. "ru_RU"
        :param setting: setting name as in the presets file
        :return: translated name
        """
        translation: SettingTranslation | None = self.languages.get(language, {}).get(setting)
        return translation.name if translation is not None and translation.name else setting

    def value_name(self, *, language: str, setting: str, value: str) -> str:
        """
        Translate a setting value, falling back to the value itself (numeric values are never translated).

        :param language: NVIDIA language code, e.g. "ru_RU"
        :param setting: setting name as in the presets file
        :param value: value as in the presets file
        :return: translated value
        """
        translation: SettingTranslation | None = self.languages.get(language, {}).get(setting)
        return (translation.values.get(value) if translation is not None else None) or value
