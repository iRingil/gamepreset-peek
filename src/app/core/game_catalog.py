"""The games of the database: display names, box art and how each copy of a game is recognized on a computer."""

import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Self

from loguru import logger

from app.config import APP_DB
from app.core.app_db import AppDb
from app.core.models import FileRole, Game, GameSource, RegistryValue, SourceFile

__all__: tuple[str, ...] = ("GameCatalog",)


class GameCatalog:
    """The games NVIDIA has presets for, sorted by name, and the copies of each game."""

    def __init__(self, *, games: tuple[Game, ...], sources: tuple[GameSource, ...] = ()) -> None:
        """
        Use the given games and copies.

        :param games: games in any order
        :param sources: copies of the games
        """
        self._games: tuple[Game, ...] = tuple(sorted(games, key=lambda game: game.name.casefold()))
        self._sources: tuple[GameSource, ...] = sources
        self._by_id: dict[str, Game] = {game.game_id: game for game in games}

    @property
    def games(self) -> tuple[Game, ...]:
        """
        Get every game.

        :return: games sorted by display name, case-insensitive
        """
        return self._games

    @property
    def sources(self) -> tuple[GameSource, ...]:
        """
        Get the copies of every game.

        :return: copies in the order of the database
        """
        return self._sources

    def game(self, *, game_id: str) -> Game | None:
        """
        Find a game by its identifier.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :return: the game, None when the catalog doesn't have it
        """
        return self._by_id.get(game_id)

    @classmethod
    def load(cls, *, path: Path = APP_DB) -> Self:
        """
        Load the games and their copies from the database.

        :param path: database file
        :return: the catalog
        """
        with closing(AppDb.read(path=path)) as db:
            games: tuple[Game, ...] = tuple(
                Game(game_id=game_id, name=name, cover_url=cover_url, app_id=app_id)
                for game_id, name, cover_url, app_id in db.execute(
                    "SELECT game_id, name, box_art_url, app_id FROM games"
                )
            )
            sources: tuple[GameSource, ...] = cls._sources_of(db=db)
        logger.debug("Loaded {} games and {} game copies from {}", len(games), len(sources), path)
        return cls(games=games, sources=sources)

    @staticmethod
    def _sources_of(*, db: sqlite3.Connection) -> tuple[GameSource, ...]:
        """
        Read the copies of the games with their files and registry values.

        :param db: open database
        :return: copies in the order of game and position
        """
        files: defaultdict[tuple[str, int], list[SourceFile]] = defaultdict(list)
        for game_id, position, path, role, is_directory in db.execute(
            "SELECT game_id, position, path, role, is_directory FROM game_source_files"
            " ORDER BY game_id, position, path, role"
        ):
            files[(game_id, position)].append(
                SourceFile(path=path, role=FileRole(role), is_directory=bool(is_directory))
            )
        registry: defaultdict[tuple[str, int], list[RegistryValue]] = defaultdict(list)
        for game_id, position, value_path, view, parent_levels, suffix, value_regex in db.execute(
            "SELECT game_id, position, value_path, view, parent_levels, suffix, value_regex FROM game_source_registry"
            " ORDER BY game_id, position, entry"
        ):
            registry[(game_id, position)].append(
                RegistryValue(
                    value_path=value_path,
                    view=view,
                    parent_levels=parent_levels,
                    suffix=suffix,
                    value_regex=value_regex,
                )
            )
        return tuple(
            GameSource(
                game_id=game_id,
                files=tuple(files[(game_id, position)]),
                registry=tuple(registry[(game_id, position)]),
                package_family=package_family,
            )
            for game_id, position, package_family in db.execute(
                "SELECT game_id, position, package_family FROM game_sources ORDER BY game_id, position"
            )
        )
