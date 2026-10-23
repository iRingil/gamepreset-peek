"""Data classes of the NVIDIA presets data, of the user's hardware and of the saved user settings."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

__all__: tuple[str, ...] = (
    "Compatibility",
    "DatabaseUpdate",
    "Game",
    "GamePresets",
    "GameSettings",
    "Gpu",
    "Hardware",
    "HardwareCheck",
    "HardwareChoice",
    "HardwareSetup",
    "HardwareState",
    "PresetsFile",
    "RemoteFile",
    "ResolutionPreset",
    "Setting",
    "SettingTranslation",
    "SystemHardware",
    "ThemeMode",
    "Translations",
    "UserSettings",
)


@dataclass(frozen=True, slots=True)
class Gpu:
    """An NVIDIA graphics card: name as Windows shows it and PCI device id as 4 lowercase hex digits, e.g. "28e0".

    Video memory in GiB is known for a detected card only; it doesn't take part in comparisons."""

    name: str
    device_id: str
    memory_gb: float | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class SystemHardware:
    """The hardware detected on this PC: CPU name, NVIDIA GPUs, memory, Windows version and the screen resolution.

    The CPU name and the resolution are None when not detected. The GPUs come the most powerful first."""

    cpu_name: str | None
    gpus: tuple[Gpu, ...]
    memory_gb: int
    os_version: str
    resolution: str | None


@dataclass(frozen=True, slots=True)
class HardwareChoice:
    """The CPU and the GPU presets are requested with; None when neither detected nor chosen."""

    cpu_name: str | None
    gpu: Gpu | None


@dataclass(frozen=True, slots=True)
class HardwareSetup:
    """What the hardware and resolution choices start from: detected values, bundled lists and what is in use.

    The bundled GPUs leave out the detected ones; the bundled CPUs are split by vendor; the bundled resolutions leave
    out the detected one. The resolution in use is the chosen one, else the detected one, else the default."""

    system: SystemHardware
    amd_cpus: tuple[str, ...]
    intel_cpus: tuple[str, ...]
    gpus: tuple[Gpu, ...]
    resolutions: tuple[str, ...]
    choice: HardwareChoice
    resolution: str


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


class DatabaseUpdate(StrEnum):
    """Outcome of a database update: not due, downloaded but equal to the database in use, or a new one in use."""

    SKIPPED = "skipped"
    UNCHANGED = "unchanged"
    UPDATED = "updated"


class HardwareState(StrEnum):
    """Outcome of finding the hardware to request presets with."""

    READY = "ready"
    NO_CPU = "no_cpu"
    NO_NVIDIA_GPU = "no_nvidia_gpu"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class HardwareCheck:
    """Hardware ready for preset requests, or why presets can't be requested with the CPU and GPU in use.

    READY carries the hardware; REJECTED the components NVIDIA rejected, empty when NVIDIA named none."""

    state: HardwareState
    hardware: Hardware | None = None
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

    The presets go from the lowest to the highest quality."""

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
    """Settings kept between runs: language, theme, detected and chosen hardware, the database update choice and date.

    The detected CPU, NVIDIA GPUs (the most powerful first) and screen resolution are written at every start. The
    chosen CPU, GPU and resolution are the ones the user picked in the lists, None when not picked: the detected ones
    are used then. The database update date is the day of the last download, None before the first one."""

    language: str | None = None
    detected_cpu: str | None = None
    detected_gpus: tuple[Gpu, ...] = ()
    detected_resolution: str | None = None
    chosen_cpu: str | None = None
    chosen_gpu: Gpu | None = None
    chosen_resolution: str | None = None
    theme: ThemeMode = ThemeMode.AUTO
    auto_update: bool = True
    database_updated: date | None = None
