"""Data classes of the NVIDIA presets data, of the user's hardware and of the saved user settings."""

from dataclasses import dataclass
from enum import StrEnum

__all__: tuple[str, ...] = (
    "Compatibility",
    "Game",
    "GamePresets",
    "GameSettings",
    "Gpu",
    "Hardware",
    "HardwareCheck",
    "HardwareState",
    "PresetsFile",
    "RemoteFile",
    "ResolutionPreset",
    "Setting",
    "SettingTranslation",
    "ThemeMode",
    "Translations",
    "UserSettings",
)


@dataclass(frozen=True, slots=True)
class Gpu:
    """An NVIDIA graphics card: name as Windows shows it and PCI device id as 4 lowercase hex digits, e.g. "28e0"."""

    name: str
    device_id: str


@dataclass(frozen=True, slots=True)
class Hardware:
    """The user's hardware as NVIDIA expects it in the query string."""

    cpu_name: str
    gpu_name: str
    gpu_device_id: str
    memory_gb: int
    os_version: str


class ThemeMode(StrEnum):
    """Color theme of the UI; AUTO follows the Windows app mode."""

    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


class HardwareState(StrEnum):
    """Outcome of finding the hardware to request presets with."""

    READY = "ready"
    NO_NVIDIA_GPU = "no_nvidia_gpu"
    CHOOSE_DETECTED_GPU = "choose_detected_gpu"
    CHOOSE_LISTED_GPU = "choose_listed_gpu"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class HardwareCheck:
    """Hardware ready for preset requests, or what the user has to do first.

    READY carries the hardware; CHOOSE_DETECTED_GPU and CHOOSE_LISTED_GPU the GPUs to choose from (detected ones the
    most powerful first); REJECTED the components NVIDIA rejected that no GPU choice can fix."""

    state: HardwareState
    hardware: Hardware | None = None
    gpus: tuple[Gpu, ...] = ()
    failed: tuple[str, ...] = ()


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
class Game:
    """A game of NVIDIA's catalog with its display name."""

    game_id: str
    name: str


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


@dataclass(frozen=True, slots=True)
class GameSettings:
    """All presets of a game with its translations, to show any preset in any UI language.

    The presets go from the lowest to the highest quality; NVIDIA App's quality slider moves between them."""

    presets: PresetsFile
    translations: Translations

    @property
    def count(self) -> int:
        """
        Count the presets.

        :return: number of presets, the highest 1-based preset index
        """
        return len(self.presets.presets)

    def rows(self, *, index: int, language: str) -> tuple[tuple[str, str], ...]:
        """
        Translate the settings of a preset and their values; a value missing from the translations is kept as is.

        :param index: 1-based preset index, as in ResolutionPreset.preset_index
        :param language: NVIDIA language code, e.g. "ru_RU"
        :return: setting name and value pairs, in the order of settings
        """
        return tuple(
            (
                self.translations.setting_name(language=language, setting=setting.name),
                self.translations.value_name(language=language, setting=setting.name, value=value),
            )
            for setting, value in self.presets.values(index=index)
        )


@dataclass(frozen=True, slots=True)
class UserSettings:
    """Settings kept between runs: UI language code, the GPU the user chose (None when not chosen yet) and the theme."""

    language: str | None = None
    gpu: Gpu | None = None
    theme: ThemeMode = ThemeMode.AUTO
