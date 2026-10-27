"""Data classes of the NVIDIA presets data, of the user's hardware and of the saved user settings."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

__all__: tuple[str, ...] = (
    "Compatibility",
    "DatabaseUpdate",
    "FileRole",
    "Game",
    "GameChoice",
    "GamesTab",
    "GameSource",
    "GamePresets",
    "GameSettings",
    "Gpu",
    "Hardware",
    "HardwareCheck",
    "HardwareChoice",
    "HardwareSetup",
    "HardwareState",
    "InstalledGame",
    "PresetsFile",
    "RegistryValue",
    "RemoteFile",
    "ResolutionPreset",
    "Setting",
    "SettingTranslation",
    "SourceFile",
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

    @property
    def detected_cpus(self) -> tuple[str, ...]:
        """
        List the detected CPU.

        :return: the detected CPU name, nothing when none was detected
        """
        return () if self.system.cpu_name is None else (self.system.cpu_name,)

    @property
    def cpu_options(self) -> tuple[str, ...]:
        """
        List the CPUs in the order of the choice.

        :return: the detected CPU, then the AMD and the Intel ones
        """
        return self.detected_cpus + self.amd_cpus + self.intel_cpus

    @property
    def gpu_options(self) -> tuple[Gpu, ...]:
        """
        List the GPUs in the order of the choice.

        :return: the detected GPUs, then the bundled ones
        """
        return self.system.gpus + self.gpus

    @property
    def detected_resolutions(self) -> tuple[str, ...]:
        """
        List the detected screen resolution.

        :return: the detected resolution, nothing when none was detected
        """
        return () if self.system.resolution is None else (self.system.resolution,)


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


class GamesTab(StrEnum):
    """Tab of the game lists: the games installed on this computer or all games."""

    INSTALLED = "installed"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class GameChoice:
    """The game tab in use and the identifier of the game chosen in each tab, None until a game is chosen there."""

    tab: GamesTab = GamesTab.INSTALLED
    installed_game_id: str | None = None
    catalog_game_id: str | None = None


class DatabaseUpdate(StrEnum):
    """Outcome of a database update: not due, downloaded but equal to the database in use, or a new one in use."""

    SKIPPED = "skipped"
    UNCHANGED = "unchanged"
    UPDATED = "updated"


class HardwareState(StrEnum):
    """Outcome of finding the hardware to request presets with."""

    READY = "ready"
    MISSING = "missing"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class HardwareCheck:
    """Hardware ready for preset requests, or why presets can't be requested with the CPU and GPU in use.

    READY carries the hardware; MISSING the components neither chosen nor detected ("cpu", "gpu" for an NVIDIA one);
    REJECTED the components NVIDIA rejected, empty when NVIDIA named none."""

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
    """A game NVIDIA has presets for, with its display name and the URL of its vertical box art, if it has one.

    The application id names the game in NVIDIA's image service; a box art URL that stopped working is found again
    through it."""

    game_id: str
    name: str
    cover_url: str | None = field(default=None, compare=False)
    app_id: str | None = field(default=None, compare=False)


class FileRole(StrEnum):
    """What a file of a game copy tells: the game's executable, a file that must be there, or one that must not."""

    EXECUTABLE = "executable"
    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A file or folder of a game copy, its path relative to the installation folder, e.g. "bin\bg3.exe"."""

    path: str
    role: FileRole
    is_directory: bool = False


@dataclass(frozen=True, slots=True)
class RegistryValue:
    """A registry value holding the installation folder of a game copy, and how to get the folder from it.

    The path is the key path with the value name as its last part (empty for the default value); view is the 32- or
    64-bit registry view, None for either. The regex's first group cuts the path out of the value; then the folder
    goes up parent_levels times and the suffix is appended."""

    value_path: str
    view: int | None = None
    parent_levels: int = 0
    suffix: str | None = None
    value_regex: str | None = None


@dataclass(frozen=True, slots=True)
class GameSource:
    """One copy of a game (a store or distribution), recognized by its files and found through the registry.

    A Microsoft Store copy has its package family name: it lives in a folder the app can't search."""

    game_id: str
    files: tuple[SourceFile, ...]
    registry: tuple[RegistryValue, ...] = ()
    package_family: str | None = None

    @property
    def executables(self) -> tuple[str, ...]:
        """
        Get the executables of the copy, any of which starts the game.

        :return: paths relative to the installation folder, in the catalog's order
        """
        return tuple(file.path for file in self.files if file.role is FileRole.EXECUTABLE)


@dataclass(frozen=True, slots=True)
class InstalledGame:
    """A game found on this computer and the executable it was recognized by."""

    game: Game
    executable: Path


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

    @property
    def resolution_names(self) -> tuple[str, ...]:
        """
        List the resolutions NVIDIA has a preset for.

        :return: the resolutions, the largest first
        """
        return tuple(
            sorted(
                (item.resolution for item in self.resolutions),
                key=lambda name: self._pixels(resolution=name),
                reverse=True,
            )
        )

    def preset_for(self, *, resolution: str) -> ResolutionPreset | None:
        """
        Find the preset of a resolution, or of the closest smaller one; the smallest when none is as small.

        :param resolution: resolution in use, e.g. "2560x1600"
        :return: the preset, None when NVIDIA gave none
        """
        by_size: list[ResolutionPreset] = sorted(
            self.resolutions, key=lambda item: self._pixels(resolution=item.resolution)
        )
        if not by_size:
            return None
        exact: ResolutionPreset | None = next((item for item in by_size if item.resolution == resolution), None)
        if exact is not None:
            return exact
        limit: int = self._pixels(resolution=resolution)
        smaller: list[ResolutionPreset] = [
            item for item in by_size if self._pixels(resolution=item.resolution) <= limit
        ]
        return smaller[-1] if smaller else by_size[0]

    @staticmethod
    def _pixels(*, resolution: str) -> int:
        """
        Count the pixels of a resolution for comparison.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1080"
        :return: width times height, 0 for a malformed resolution
        """
        width: str
        height: str
        width, _, height = resolution.partition("x")
        return int(width) * int(height) if width.isdigit() and height.isdigit() else 0


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
    """Settings kept between runs: language, theme, detected and chosen hardware, the database update choice and time.

    The detected CPU, NVIDIA GPUs (the most powerful first) and screen resolution are written at every start. The
    chosen CPU, GPU and resolution are the ones the user picked in the lists, None when not picked: the detected ones
    are used then.

    The database check time comes from the manifest of the database in use: when its source data were last checked;
    None before the first update.

    The game folders are where installed games are searched for; None until the list is first saved. The game choice
    keeps the tab in use and the game chosen in each tab."""

    language: str | None = None
    detected_cpu: str | None = None
    detected_gpus: tuple[Gpu, ...] = ()
    detected_resolution: str | None = None
    chosen_cpu: str | None = None
    chosen_gpu: Gpu | None = None
    chosen_resolution: str | None = None
    theme: ThemeMode = ThemeMode.AUTO
    auto_update: bool = True
    database_checked: datetime | None = None
    game_folders: tuple[str, ...] | None = None
    game_choice: GameChoice = GameChoice()
