"""Search for installed games: in the game folders by their executables, and through the registry."""

import os
import re
import winreg
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import AbstractSet, Callable, Iterator, Sequence

from loguru import logger

from app.config import GAME_SEARCH_DEPTH
from app.core.game_catalog import GameCatalog
from app.core.models import FileRole, Game, GameSource, InstalledGame, RegistryValue

__all__: tuple[str, ...] = ("GameFinder", "WindowsRegistry")


class WindowsRegistry:
    """Reads string values of the Windows registry; a key part with a regex pattern matches any subkey it fits."""

    _HIVES: dict[str, int] = {
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
        "HKEY_USERS": winreg.HKEY_USERS,
    }
    _VIEWS: dict[int, int] = {32: winreg.KEY_WOW64_32KEY, 64: winreg.KEY_WOW64_64KEY}
    # Characters that make a key part a regex pattern; a lone "." is a plain dot, as in "R20.1".
    _PATTERN: re.Pattern[str] = re.compile(r"[*+?\[\]()|^$]")

    @classmethod
    def read(cls, *, value: RegistryValue) -> str | None:
        """
        Read a value, trying the 64-bit view first when the value names none.

        :param value: the value to read
        :return: the string, None when the key or value is missing or not a string
        """
        parts: list[str] = value.value_path.split(sep="\\")
        hive: int | None = cls._HIVES.get(parts[0].upper())
        if hive is None or len(parts) < 3:
            return None
        views: tuple[int, ...] = (value.view,) if value.view is not None and value.view in cls._VIEWS else (64, 32)
        for view in views:
            for key_path in cls._key_paths(hive=hive, parts=parts[1:-1], view=view):
                text: str | None = cls._string(hive=hive, key_path=key_path, name=parts[-1], view=view)
                if text is not None:
                    return text
        return None

    @classmethod
    def _key_paths(cls, *, hive: int, parts: Sequence[str], view: int) -> Iterator[str]:
        """
        List the existing key paths a key path with patterns stands for.

        :param hive: root key
        :param parts: key names, some of them maybe regex patterns
        :param view: 32 or 64
        :return: key paths, the plain path as it is
        """
        pattern_at: int | None = next((i for i, part in enumerate(parts) if cls._PATTERN.search(part)), None)
        if pattern_at is None:
            yield "\\".join(parts)
            return
        parent: str = "\\".join(parts[:pattern_at])
        try:
            pattern: re.Pattern[str] = re.compile(pattern=parts[pattern_at], flags=re.IGNORECASE)
            with winreg.OpenKey(hive, parent, 0, winreg.KEY_READ | cls._VIEWS[view]) as key:
                names: list[str] = [winreg.EnumKey(key, index) for index in range(winreg.QueryInfoKey(key)[0])]
        except (OSError, re.error):
            return
        for name in names:
            if pattern.fullmatch(name):
                yield from cls._key_paths(
                    hive=hive, parts=[*parts[:pattern_at], name, *parts[pattern_at + 1 :]], view=view
                )

    @classmethod
    def _string(cls, *, hive: int, key_path: str, name: str, view: int) -> str | None:
        """
        Read one string value.

        :param hive: root key
        :param key_path: key path below the root
        :param name: value name, empty for the default value
        :param view: 32 or 64
        :return: the string, None when missing or of another type
        """
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | cls._VIEWS[view]) as key:
                text: object = winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None
        return text if isinstance(text, str) and text.strip() else None


@dataclass(frozen=True, slots=True)
class _Candidate:
    """A copy of a game whose executable has the name of a file found, with the executable's path parts."""

    source: GameSource
    parts: tuple[str, ...]


class GameFinder:
    """Finds the games of the catalog installed on this computer.

    The registry is read first: a copy whose value leads to a folder holding its executable and files is found. Then
    the game folders are walked: a file named like a copy's executable, at the end of the same relative path, makes
    its folder a candidate. A copy matches when every file it needs is there and none it must not have is.

    When several games match one file, the copy checked by the most files wins; a tie between games is ambiguous
    (a "launcher.exe" alone tells nothing) and none of them is taken. Microsoft Store copies are skipped: their
    folder can't be read."""

    def __init__(
        self,
        *,
        registry: Callable[[RegistryValue], str | None] = lambda value: WindowsRegistry.read(value=value),
        depth: int = GAME_SEARCH_DEPTH,
    ) -> None:
        """
        Use the given registry reader.

        :param registry: reads a registry value, None when it is missing
        :param depth: folder levels below a game folder that are searched
        """
        self._registry: Callable[[RegistryValue], str | None] = registry
        self._depth: int = depth

    def find(self, *, catalog: GameCatalog, folders: Sequence[Path]) -> tuple[InstalledGame, ...]:
        """
        Find the installed games.

        :param catalog: the games and their copies
        :param folders: folders to search
        :return: one entry per game, sorted by display name, case-insensitive
        """
        sources: list[GameSource] = [
            source for source in catalog.sources if source.package_family is None and source.executables
        ]
        found: dict[str, Path] = {}
        for source in sources:
            if source.game_id not in found:
                executable: Path | None = self._from_registry(source=source)
                if executable is not None:
                    found[source.game_id] = executable
        index: dict[str, list[_Candidate]] = self._index(sources=sources)
        for folder in folders:
            for file in self._files(folder=folder, names=index.keys()):
                game_id: str | None = self._match(file=file, candidates=index[file.name.lower()])
                if game_id is not None:
                    found.setdefault(game_id, file)
        games: list[InstalledGame] = []
        for found_id, found_file in found.items():
            game: Game | None = catalog.game(game_id=found_id)
            if game is not None:
                games.append(InstalledGame(game=game, executable=found_file))
        logger.info("Found {} installed games in {}", len(games), ", ".join(str(folder) for folder in folders))
        return tuple(sorted(games, key=lambda item: item.game.name.casefold()))

    def _from_registry(self, *, source: GameSource) -> Path | None:
        """
        Find a copy through its registry values.

        :param source: the copy
        :return: its executable, None when no value leads to the copy
        """
        for value in source.registry:
            folder: Path | None = self._registry_folder(value=value)
            if folder is None or not self._fits(source=source, root=folder):
                continue
            for executable in source.executables:
                path: Path = folder / executable
                if path.is_file():
                    logger.debug("Found {} through the registry: {}", source.game_id, path)
                    return path
        return None

    def _registry_folder(self, *, value: RegistryValue) -> Path | None:
        """
        Get the installation folder a registry value leads to.

        :param value: the value
        :return: the folder, None when the value is missing or doesn't fit its pattern
        """
        read: str | None = self._registry(value)
        if read is None:
            return None
        text: str = read
        if value.value_regex is not None:
            try:
                match: re.Match[str] | None = re.search(pattern=value.value_regex, string=text)
            except re.error:
                logger.debug("Bad registry value pattern {!r}", value.value_regex)
                return None
            if match is None:
                return None
            # A group that took no part in the match gives None.
            text = (match.group(1) if match.re.groups else match.group(0)) or ""
        text = os.path.expandvars(path=text.strip().strip('"'))
        if not text:
            return None
        folder: PureWindowsPath = PureWindowsPath(text)
        for _ in range(value.parent_levels):
            folder = folder.parent
        if value.suffix:
            folder = folder / value.suffix
        return Path(folder)

    @staticmethod
    def _index(*, sources: Sequence[GameSource]) -> dict[str, list[_Candidate]]:
        """
        Index the copies by the file names of their executables.

        :param sources: copies with executables
        :return: candidates by lower-case file name
        """
        index: defaultdict[str, list[_Candidate]] = defaultdict(list)
        for source in sources:
            for executable in source.executables:
                parts: tuple[str, ...] = tuple(part.lower() for part in PureWindowsPath(executable).parts)
                index[parts[-1]].append(_Candidate(source=source, parts=parts))
        return dict(index)

    def _files(self, *, folder: Path, names: AbstractSet[str]) -> Iterator[Path]:
        """
        Walk a folder and yield the files with one of the names, skipping links and folders that can't be read.

        :param folder: folder to walk
        :param names: lower-case file names wanted
        :return: the files
        """
        stack: list[tuple[str, int]] = [(str(folder), 0)]
        while stack:
            path, depth = stack.pop()
            try:
                with os.scandir(path=path) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            # A junction or symbolic link may loop or lead to another drive.
                            if depth < self._depth and not entry.is_junction() and not entry.is_symlink():
                                stack.append((entry.path, depth + 1))
                        elif entry.name.lower() in names:
                            yield Path(entry.path)
            except OSError:
                continue

    def _match(self, *, file: Path, candidates: Sequence[_Candidate]) -> str | None:
        """
        Decide which game a found file belongs to.

        :param file: the file
        :param candidates: copies with an executable of that name
        :return: the game identifier, None when no copy fits or several games fit equally
        """
        lowered: tuple[str, ...] = tuple(part.lower() for part in file.parts)
        scores: dict[str, int] = {}
        for candidate in candidates:
            if lowered[-len(candidate.parts) :] != candidate.parts or len(lowered) <= len(candidate.parts):
                continue
            root: Path = Path(*file.parts[: -len(candidate.parts)])
            if self._fits(source=candidate.source, root=root):
                checks: int = len(candidate.parts) + sum(
                    listed.role is not FileRole.EXECUTABLE for listed in candidate.source.files
                )
                game_id: str = candidate.source.game_id
                scores[game_id] = max(scores.get(game_id, 0), checks)
        if not scores:
            return None
        best: int = max(scores.values())
        winners: list[str] = [game_id for game_id, score in scores.items() if score == best]
        if len(winners) > 1:
            logger.debug("Skipped {}: it fits {} equally", file, ", ".join(sorted(winners)))
            return None
        return winners[0]

    @staticmethod
    def _fits(*, source: GameSource, root: Path) -> bool:
        """
        Check the files of a copy in a folder.

        :param source: the copy
        :param root: the folder it would be installed in
        :return: True when every file it needs is there and none it must not have is
        """
        for file in source.files:
            path: Path = root / file.path
            if file.role is FileRole.PRESENT and not (path.is_dir() if file.is_directory else path.exists()):
                return False
            if file.role is FileRole.ABSENT and path.exists():
                return False
        return True
