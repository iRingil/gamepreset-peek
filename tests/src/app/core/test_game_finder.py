"""Tests of the search for installed games and of the registry reader it uses."""

import winreg
from pathlib import Path
from typing import Iterator

import pytest

from app.core.game_catalog import GameCatalog
from app.core.game_finder import GameFinder, WindowsRegistry
from app.core.models import FileRole, Game, GameSource, InstalledGame, RegistryValue, SourceFile

__all__: tuple = ()

_BG3: Game = Game(game_id="baldurs_gate_3", name="Baldur's Gate 3")
_MORDHAU: Game = Game(game_id="mordhau", name="MORDHAU")
_OTHER: Game = Game(game_id="other_game", name="Another Game")
_BG3_STEAM: GameSource = GameSource(
    game_id="baldurs_gate_3",
    files=(
        SourceFile(path="bin\\bg3.exe", role=FileRole.EXECUTABLE),
        SourceFile(path="bin\\bg3_dx11.exe", role=FileRole.EXECUTABLE),
        SourceFile(path="Data", role=FileRole.PRESENT, is_directory=True),
        SourceFile(path="gog.ico", role=FileRole.ABSENT),
    ),
)
_MORDHAU_ANY: GameSource = GameSource(
    game_id="mordhau", files=(SourceFile(path="Mordhau.exe", role=FileRole.EXECUTABLE),)
)


class _Files:
    """Files of a fake installation."""

    @staticmethod
    def make(*, root: Path, paths: tuple[str, ...]) -> Path:
        """
        Create empty files, and folders for paths ending with a slash.

        :param root: folder the paths are relative to
        :param paths: relative paths
        :return: the root
        """
        for relative in paths:
            path: Path = root / relative
            if relative.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        return root


class TestFolders:
    """Finding games by walking the game folders."""

    @pytest.fixture(name="finder")
    def _finder(self) -> GameFinder:
        """
        Make a finder with an empty registry and a search depth of 3.

        :return: finder under test
        """
        return GameFinder(registry=lambda _: None, depth=3)

    def test_found_by_executable_and_files(self, tmp_path: Path, finder: GameFinder) -> None:
        """
        Finds a copy whose executable sits at its relative path and whose needed files are there, sorted by name.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Games" / "Baldurs Gate 3", paths=("bin/bg3.exe", "Data/"))
        _Files.make(root=tmp_path / "Games" / "Mordhau", paths=("Mordhau.exe",))
        catalog: GameCatalog = GameCatalog(games=(_BG3, _MORDHAU), sources=(_MORDHAU_ANY, _BG3_STEAM))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path / "Games"])
        # Assert
        assert games == (
            InstalledGame(game=_BG3, executable=tmp_path / "Games" / "Baldurs Gate 3" / "bin" / "bg3.exe"),
            InstalledGame(game=_MORDHAU, executable=tmp_path / "Games" / "Mordhau" / "Mordhau.exe"),
        )

    @pytest.mark.parametrize(
        argnames="paths",
        argvalues=[
            ("bin/bg3.exe",),
            ("bin/bg3.exe", "Data"),
            ("bin/bg3.exe", "Data/", "gog.ico"),
            ("bg3.exe", "Data/"),
            ("other/bin/bg3.exe", "Data/"),
        ],
        ids=["needed folder missing", "needed folder is a file", "unwanted file there", "not in bin", "deeper bin"],
    )
    def test_not_matching(self, tmp_path: Path, finder: GameFinder, paths: tuple[str, ...]) -> None:
        """
        Finds nothing when a needed file is missing, an unwanted one is there or the executable sits elsewhere.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :param paths: files of the installation
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Baldurs Gate 3", paths=paths)
        catalog: GameCatalog = GameCatalog(games=(_BG3,), sources=(_BG3_STEAM,))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path])
        # Assert
        assert not games

    def test_one_entry_per_game(self, tmp_path: Path, finder: GameFinder) -> None:
        """
        Lists a game once when several of its executables or copies are found.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "A", paths=("bin/bg3.exe", "bin/bg3_dx11.exe", "Data/"))
        _Files.make(root=tmp_path / "B", paths=("bin/bg3.exe", "Data/"))
        catalog: GameCatalog = GameCatalog(games=(_BG3,), sources=(_BG3_STEAM,))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path])
        # Assert
        assert [item.game for item in games] == [_BG3]

    def test_most_specific_wins(self, tmp_path: Path, finder: GameFinder) -> None:
        """
        Gives a shared executable name to the game whose copy is checked by more files.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Game", paths=("launcher.exe", "game.pak"))
        catalog: GameCatalog = GameCatalog(
            games=(_MORDHAU, _OTHER),
            sources=(
                GameSource(game_id="mordhau", files=(SourceFile(path="launcher.exe", role=FileRole.EXECUTABLE),)),
                GameSource(
                    game_id="other_game",
                    files=(
                        SourceFile(path="launcher.exe", role=FileRole.EXECUTABLE),
                        SourceFile(path="game.pak", role=FileRole.PRESENT),
                    ),
                ),
            ),
        )
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path])
        # Assert
        assert [item.game for item in games] == [_OTHER]

    def test_tie_skipped(self, tmp_path: Path, finder: GameFinder) -> None:
        """
        Takes none of the games an executable fits equally well.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Game", paths=("launcher.exe",))
        catalog: GameCatalog = GameCatalog(
            games=(_MORDHAU, _OTHER),
            sources=tuple(
                GameSource(game_id=game_id, files=(SourceFile(path="launcher.exe", role=FileRole.EXECUTABLE),))
                for game_id in ("mordhau", "other_game")
            ),
        )
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path])
        # Assert
        assert not games

    @pytest.mark.parametrize(
        argnames=("source", "games"),
        argvalues=[
            (GameSource(game_id="mordhau", files=_MORDHAU_ANY.files, package_family="Triternion.Mordhau_x"), ()),
            (GameSource(game_id="missing", files=_MORDHAU_ANY.files), ()),
        ],
        ids=["store copy", "game not in catalog"],
    )
    def test_skipped_copies(
        self, tmp_path: Path, finder: GameFinder, source: GameSource, games: tuple[InstalledGame, ...]
    ) -> None:
        """
        Skips Microsoft Store copies and copies of games the catalog doesn't list.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :param source: the copy
        :param games: expected result
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Mordhau", paths=("Mordhau.exe",))
        catalog: GameCatalog = GameCatalog(games=(_MORDHAU,), sources=(source,))
        # Act
        found: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path])
        # Assert
        assert found == games

    def test_depth_and_missing_folder(self, tmp_path: Path, finder: GameFinder) -> None:
        """
        Searches as deep as the depth allows and passes over a folder that doesn't exist.

        :param tmp_path: temporary directory
        :param finder: finder under test
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "a" / "b" / "c", paths=("Mordhau.exe",))
        _Files.make(root=tmp_path / "a" / "b" / "c" / "d", paths=("bin/bg3.exe", "Data/"))
        catalog: GameCatalog = GameCatalog(games=(_BG3, _MORDHAU), sources=(_BG3_STEAM, _MORDHAU_ANY))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[tmp_path / "gone", tmp_path])
        # Assert
        assert [item.game for item in games] == [_MORDHAU]


class TestRegistry:
    """Finding games through the registry values of their copies."""

    @staticmethod
    def _source(*, value: RegistryValue) -> GameSource:
        """
        Make a copy of Mordhau found through one registry value.

        :param value: the value
        :return: the copy
        """
        return GameSource(game_id="mordhau", files=_MORDHAU_ANY.files, registry=(value,))

    @pytest.mark.parametrize(
        argnames=("value", "text"),
        argvalues=[
            (RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path"), "{root}\\Mordhau"),
            (RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path"), '"{root}\\Mordhau" '),
            (
                RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\", parent_levels=1, value_regex='^"([^"]*)"'),
                '"{root}\\Mordhau\\Mordhau.exe" %1',
            ),
            (RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path", value_regex=".+"), "{root}\\Mordhau"),
            (
                RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path", parent_levels=1, suffix="Mordhau"),
                "{root}\\Launcher",
            ),
        ],
        ids=["folder", "quoted folder", "command line", "pattern without group", "up and down"],
    )
    def test_found(self, tmp_path: Path, value: RegistryValue, text: str) -> None:
        """
        Gets the installation folder from the value: cut by the pattern, gone up, the suffix appended.

        :param tmp_path: temporary directory
        :param value: the registry value of the copy
        :param text: what the registry holds
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Mordhau", paths=("Mordhau.exe",))
        finder: GameFinder = GameFinder(registry=lambda _: text.format(root=tmp_path))
        catalog: GameCatalog = GameCatalog(games=(_MORDHAU,), sources=(self._source(value=value),))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(catalog=catalog, folders=[])
        # Assert
        assert games == (InstalledGame(game=_MORDHAU, executable=tmp_path / "Mordhau" / "Mordhau.exe"),)

    def test_environment_variable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Expands an environment variable in the value.

        :param tmp_path: temporary directory
        :param monkeypatch: sets the variable
        :return: None
        """
        # Arrange
        monkeypatch.setenv(name="GAMES_ROOT", value=str(tmp_path))
        _Files.make(root=tmp_path / "Mordhau", paths=("Mordhau.exe",))
        finder: GameFinder = GameFinder(registry=lambda _: "%GAMES_ROOT%\\Mordhau")
        source: GameSource = self._source(value=RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path"))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(
            catalog=GameCatalog(games=(_MORDHAU,), sources=(source,)), folders=[]
        )
        # Assert
        assert [item.game for item in games] == [_MORDHAU]

    @pytest.mark.parametrize(
        argnames=("regex", "text"),
        argvalues=[
            (None, None),
            (None, "   "),
            ('^"([^"]*)"', "{root}\\Mordhau"),
            ("([", "{root}\\Mordhau"),
            ('^(")?C:', "C:\\Games"),
            (None, "{root}\\Elsewhere"),
        ],
        ids=["missing", "blank", "pattern not fitting", "bad pattern", "group not matched", "no executable there"],
    )
    def test_not_found(self, tmp_path: Path, regex: str | None, text: str | None) -> None:
        """
        Finds nothing for a missing or blank value, one not fitting its pattern, or a folder without the game.

        :param tmp_path: temporary directory
        :param regex: pattern of the value
        :param text: what the registry holds, None when nothing
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Mordhau", paths=("Mordhau.exe",))
        finder: GameFinder = GameFinder(registry=lambda _: None if text is None else text.format(root=tmp_path))
        source: GameSource = self._source(
            value=RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path", value_regex=regex)
        )
        # Act
        games: tuple[InstalledGame, ...] = finder.find(
            catalog=GameCatalog(games=(_MORDHAU,), sources=(source,)), folders=[]
        )
        # Assert
        assert not games

    def test_registry_before_folders(self, tmp_path: Path) -> None:
        """
        Keeps the copy found through the registry when the folders hold another one.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        _Files.make(root=tmp_path / "Registry" / "Mordhau", paths=("Mordhau.exe",))
        _Files.make(root=tmp_path / "Games" / "Mordhau", paths=("Mordhau.exe",))
        finder: GameFinder = GameFinder(registry=lambda _: str(tmp_path / "Registry" / "Mordhau"))
        source: GameSource = self._source(value=RegistryValue(value_path="HKEY_CURRENT_USER\\Mordhau\\Path"))
        # Act
        games: tuple[InstalledGame, ...] = finder.find(
            catalog=GameCatalog(games=(_MORDHAU,), sources=(source,)), folders=[tmp_path / "Games"]
        )
        # Assert
        assert [item.executable for item in games] == [tmp_path / "Registry" / "Mordhau" / "Mordhau.exe"]


class TestWindowsRegistry:
    """Reading values of the real registry under a key of the current user made for the test."""

    _KEY: str = "Software\\GamePresetPeekTests"

    @pytest.fixture(name="key", autouse=True)
    def _key(self) -> Iterator[str]:
        """
        Write test values: a folder, a default value, a number and a versioned subkey; remove them afterward.

        :return: the key path under HKEY_CURRENT_USER
        """
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._KEY) as key:
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, "D:\\Games\\Mordhau")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, '"D:\\Games\\Mordhau\\Mordhau.exe" %1')
            winreg.SetValueEx(key, "Count", 0, winreg.REG_DWORD, 3)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._KEY + "\\Mordhau 1.2") as key:
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, "E:\\Mordhau")
        yield self._KEY
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self._KEY + "\\Mordhau 1.2")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self._KEY)

    @pytest.mark.parametrize(
        argnames=("value", "expected"),
        argvalues=[
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\InstallPath"), "D:\\Games\\Mordhau"),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\InstallPath", view=32), "D:\\Games\\Mordhau"),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\"), '"D:\\Games\\Mordhau\\Mordhau.exe" %1'),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\Mordhau .*\\InstallPath"), "E:\\Mordhau"),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\Count"), None),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\Missing"), None),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\Other .*\\InstallPath"), None),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}\\Gone\\(\\InstallPath"), None),
            (RegistryValue(value_path=f"HKEY_CURRENT_USER\\{_KEY}Gone\\.*\\InstallPath"), None),
            (RegistryValue(value_path="HKEY_NOWHERE\\Software\\InstallPath"), None),
            (RegistryValue(value_path="HKEY_CURRENT_USER\\InstallPath"), None),
        ],
        ids=[
            "string",
            "32-bit view",
            "default value",
            "pattern subkey",
            "not a string",
            "missing value",
            "no subkey fits",
            "bad pattern",
            "pattern under a missing key",
            "unknown root",
            "no key",
        ],
    )
    def test_read(self, value: RegistryValue, expected: str | None) -> None:
        """
        Reads a string value, None for anything missing or not a string.

        :param value: the value to read
        :param expected: its text
        :return: None
        """
        # Arrange & Act
        text: str | None = WindowsRegistry.read(value=value)
        # Assert
        assert text == expected
