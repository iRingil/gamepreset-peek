"""Tests of the game catalog read from the database."""

from pathlib import Path

import pytest

from app.config import APP_DB
from app.core.game_catalog import GameCatalog
from app.core.models import FileRole, Game, GameSource, RegistryValue, SourceFile
from tests.src.app.core.db_files import DbFiles

__all__: tuple = ()


class TestGames:
    """The games of a catalog."""

    def test_sorted_by_name(self) -> None:
        """
        Sorts the games by name ignoring case.

        :return: None
        """
        # Arrange & Act
        catalog: GameCatalog = GameCatalog(
            games=(Game(game_id="mordhau", name="MORDHAU"), Game(game_id="a_way_out", name="a Way Out"))
        )
        # Assert
        assert [game.game_id for game in catalog.games] == ["a_way_out", "mordhau"]

    @pytest.mark.parametrize(
        argnames=("game_id", "expected"),
        argvalues=[("mordhau", Game(game_id="mordhau", name="MORDHAU")), ("nba_2k27", None)],
        ids=["known", "unknown"],
    )
    def test_game_by_id(self, game_id: str, expected: Game | None) -> None:
        """
        Finds a game by its identifier, None for one the catalog lacks.

        :param game_id: identifier asked for
        :param expected: the game found
        :return: None
        """
        # Arrange
        catalog: GameCatalog = GameCatalog(games=(Game(game_id="mordhau", name="MORDHAU"),))
        # Act
        game: Game | None = catalog.game(game_id=game_id)
        # Assert
        assert game == expected


class TestLoad:
    """Loading the catalog from a database file."""

    @pytest.fixture(name="path")
    def _path(self, tmp_path: Path) -> Path:
        """
        Write a database with two games: one with two copies, one without box art or copies.

        :param tmp_path: temporary directory
        :return: the database file
        """
        return DbFiles.create(
            path=tmp_path / "app.db",
            statements=[
                (
                    "INSERT INTO games (game_id, name, box_art_url) VALUES (?, ?, ?)",
                    ("baldurs_gate_3", "Baldur's Gate 3", "https://img.example.test/bg3.jpg"),
                ),
                ("INSERT INTO games (game_id, name) VALUES (?, ?)", ("mordhau", "MORDHAU")),
                ("INSERT INTO game_sources VALUES (?, ?, ?, ?)", ("baldurs_gate_3", 2, "UWP", "Larian.BG3_x")),
                ("INSERT INTO game_sources VALUES (?, ?, ?, ?)", ("baldurs_gate_3", 1, "Steam", None)),
                ("INSERT INTO game_source_files VALUES (?, ?, ?, ?, ?)", ("baldurs_gate_3", 1, "gog.ico", "absent", 0)),
                (
                    "INSERT INTO game_source_files VALUES (?, ?, ?, ?, ?)",
                    ("baldurs_gate_3", 1, "bin\\bg3.exe", "executable", 0),
                ),
                ("INSERT INTO game_source_files VALUES (?, ?, ?, ?, ?)", ("baldurs_gate_3", 1, "Data", "present", 1)),
                (
                    "INSERT INTO game_source_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("baldurs_gate_3", 1, 2, "HKEY_CURRENT_USER\\Software\\B\\Path", None, 0, None, None),
                ),
                (
                    "INSERT INTO game_source_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("baldurs_gate_3", 1, 1, "HKEY_LOCAL_MACHINE\\Software\\A\\", 64, 2, "Game", '^"([^"]*)"'),
                ),
            ],
        )

    def test_games(self, path: Path) -> None:
        """
        Reads the games with their names and box art, sorted by name.

        :param path: database file
        :return: None
        """
        # Arrange & Act
        catalog: GameCatalog = GameCatalog.load(path=path)
        # Assert
        assert [(game.game_id, game.name, game.cover_url) for game in catalog.games] == [
            ("baldurs_gate_3", "Baldur's Gate 3", "https://img.example.test/bg3.jpg"),
            ("mordhau", "MORDHAU", None),
        ]

    def test_sources(self, path: Path) -> None:
        """
        Reads the copies in order of position, their files by path and their registry values in entry order.

        :param path: database file
        :return: None
        """
        # Arrange & Act
        catalog: GameCatalog = GameCatalog.load(path=path)
        # Assert
        assert catalog.sources == (
            GameSource(
                game_id="baldurs_gate_3",
                files=(
                    SourceFile(path="Data", role=FileRole.PRESENT, is_directory=True),
                    SourceFile(path="bin\\bg3.exe", role=FileRole.EXECUTABLE),
                    SourceFile(path="gog.ico", role=FileRole.ABSENT),
                ),
                registry=(
                    RegistryValue(
                        value_path="HKEY_LOCAL_MACHINE\\Software\\A\\",
                        view=64,
                        parent_levels=2,
                        suffix="Game",
                        value_regex='^"([^"]*)"',
                    ),
                    RegistryValue(value_path="HKEY_CURRENT_USER\\Software\\B\\Path"),
                ),
            ),
            GameSource(game_id="baldurs_gate_3", files=(), package_family="Larian.BG3_x"),
        )
        assert catalog.sources[0].executables == ("bin\\bg3.exe",)

    def test_bundled_db(self) -> None:
        """
        Loads the bundled database: every game has a name, and every copy belongs to a listed game.

        :return: None
        """
        # Arrange & Act
        catalog: GameCatalog = GameCatalog.load(path=APP_DB)
        # Assert
        assert catalog.game(game_id="baldurs_gate_3") is not None
        assert all(game.name and game.name == game.name.strip() for game in catalog.games)
        assert {source.game_id for source in catalog.sources} <= {game.game_id for game in catalog.games}
