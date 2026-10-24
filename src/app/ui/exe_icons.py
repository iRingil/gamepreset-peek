"""Icons of the installed games' executables, extracted once into picture files of the cache."""

import ctypes
import hashlib
from pathlib import Path
from typing import Any

from loguru import logger
from PySide6.QtGui import QImage

from app.config import EXE_ICON_SIZE, EXE_ICONS_DIR

__all__: tuple[str, ...] = ("ExeIcons",)


class ExeIcons:
    """Extracts the icon of an executable into a PNG file once; an executable's icon never changes, so it is kept.

    Only QImage is used, which works off the UI thread: the icons are extracted during the search for games."""

    # SHDefExtractIcon answers S_OK with an icon, S_FALSE for a file without one.
    _S_OK: int = 0

    def __init__(self, *, folder: Path = EXE_ICONS_DIR, size: int = EXE_ICON_SIZE) -> None:
        """
        Keep the icon files in a folder.

        :param folder: folder of the icon files, created when the first icon is saved
        :param size: side of an icon in pixels
        """
        self._folder: Path = folder
        self._size: int = size

    def get(self, *, executable: Path) -> Path | None:
        """
        Get the icon file of an executable, extracting the icon the first time.

        :param executable: the executable
        :return: the PNG file, None when the executable has no icon or it can't be read
        """
        path: Path = self._folder / f"{hashlib.sha256(str(executable).casefold().encode()).hexdigest()[:32]}.png"
        if path.is_file():
            return path
        image: QImage | None = self._extract(executable=executable)
        if image is None:
            return None
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            logger.warning("Icon of {} not saved: {!r}", executable, error)
            return None
        if not image.save(str(path)):
            logger.warning("Icon of {} not saved to {}", executable, path)
            return None
        return path

    def _extract(self, *, executable: Path) -> QImage | None:
        """
        Read the first icon of an executable at the icon size.

        :param executable: the executable
        :return: the icon, None when there is none
        """
        icon: ctypes.c_void_p = ctypes.c_void_p()
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        extract_icon: Any = ctypes.WinDLL(name="shell32")["SHDefExtractIconW"]
        result: int = extract_icon(str(executable), 0, 0, ctypes.byref(icon), None, self._size)
        if result != self._S_OK or not icon.value:
            logger.debug("No icon in {} (result {})", executable, result)
            return None
        try:
            image: QImage = QImage.fromHICON(icon.value)
        finally:
            ctypes.WinDLL(name="user32")["DestroyIcon"](icon)
        return None if image.isNull() else image
