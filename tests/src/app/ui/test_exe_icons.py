"""Tests of the icons of executables kept in the cache."""

import ctypes
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from app.ui.exe_icons import ExeIcons

__all__: tuple = ()


class TestExeIcons:
    """Tests of ExeIcons."""

    def test_extracted(self, tmp_path: Path) -> None:
        """
        Extracts the icon of an executable into a picture file of the icon size.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        icons: ExeIcons = ExeIcons(folder=tmp_path / "icons", size=48)
        # Act
        path: Path | None = icons.get(executable=Path(sys.executable))
        # Assert
        assert path is not None and path.parent == tmp_path / "icons"
        assert QImage(str(path)).size().width() == 48

    def test_kept(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Gives the saved file again without reading the executable, whatever case the path is written in.

        :param tmp_path: temporary directory
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        icons: ExeIcons = ExeIcons(folder=tmp_path)
        first: Path | None = icons.get(executable=Path(sys.executable))
        monkeypatch.setattr(target=ctypes, name="WinDLL", value=lambda name: pytest.fail(reason="icon read again"))
        # Act
        second: Path | None = icons.get(executable=Path(sys.executable.upper()))
        # Assert
        assert first is not None and second == first

    def test_no_icon(self, tmp_path: Path) -> None:
        """
        Gives no file for a file without an icon.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        executable: Path = tmp_path / "game.exe"
        executable.write_bytes(data=b"not a program")
        # Act
        path: Path | None = ExeIcons(folder=tmp_path / "icons").get(executable=executable)
        # Assert
        assert (path, (tmp_path / "icons").exists()) == (None, False)

    def test_folder_not_created(self, tmp_path: Path) -> None:
        """
        Gives no file when the cache folder can't be created.

        :param tmp_path: temporary directory
        :return: None
        """
        # Arrange
        blocker: Path = tmp_path / "file"
        blocker.write_bytes(data=b"")
        # Act
        path: Path | None = ExeIcons(folder=blocker / "icons").get(executable=Path(sys.executable))
        # Assert
        assert path is None

    def test_not_saved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Gives no file when the picture can't be written.

        :param tmp_path: temporary directory
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=QImage, name="save", value=lambda *_: False)
        # Act
        path: Path | None = ExeIcons(folder=tmp_path).get(executable=Path(sys.executable))
        # Assert
        assert path is None
