"""Folders the program keeps its settings, log and cache in: the user profile, or its own folder when portable."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

__all__: tuple[str, ...] = ("AppDirs",)


@dataclass(frozen=True, slots=True)
class AppDirs:
    """Data and cache folders of the program, chosen by the portable marker file in the program's folder.

    With the marker everything stays under the program's folder, so a copy on a USB stick leaves nothing on the
    computer; without it the data goes to %LOCALAPPDATA% and the cache to the temporary folder."""

    data: Path
    cache: Path
    portable: bool

    _PORTABLE_MARKER: ClassVar[str] = "portable.txt"
    _USER_DATA: ClassVar[str] = "userdata"
    _CACHE: ClassVar[str] = "cache"

    @classmethod
    def detect(cls, *, app_dir: Path, app_name: str) -> "AppDirs":
        """
        Choose the folders by the presence of the portable marker in the program's folder.

        :param app_dir: the program's folder: the executable's folder in the build, src when run from source
        :param app_name: folder name of the program in %LOCALAPPDATA% and the temporary folder
        :return: folders of the program
        """
        if (app_dir / cls._PORTABLE_MARKER).is_file():
            user_data: Path = app_dir / cls._USER_DATA
            return cls(data=user_data, cache=user_data / cls._CACHE, portable=True)
        return cls(
            data=Path(os.environ["LOCALAPPDATA"]) / app_name,
            cache=Path(tempfile.gettempdir()) / app_name,
            portable=False,
        )
