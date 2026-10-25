"""Tests of the choice between the user profile folders and the portable ones."""

import tempfile
from pathlib import Path

import pytest

from app.infra.app_dirs import AppDirs

__all__: tuple = ()


class TestAppDirs:
    """Tests of AppDirs.detect with and without the portable marker."""

    _APP_NAME: str = "GamePresetPeek"

    @pytest.fixture(name="local_app_data")
    def _local_app_data(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """
        Point %LOCALAPPDATA% at a temporary folder.

        :param monkeypatch: pytest monkeypatch
        :param tmp_path: temporary directory of the test
        :return: the folder %LOCALAPPDATA% points at
        """
        folder: Path = tmp_path / "LocalAppData"
        monkeypatch.setenv(name="LOCALAPPDATA", value=str(folder))
        return folder

    def test_user_profile_without_marker(self, local_app_data: Path, tmp_path: Path) -> None:
        """
        Keeps the data in %LOCALAPPDATA% and the cache in the temporary folder when there is no marker.

        :param local_app_data: the folder %LOCALAPPDATA% points at
        :param tmp_path: temporary directory of the test, used as the program's folder
        :return: None
        """
        # Arrange & Act
        dirs: AppDirs = AppDirs.detect(app_dir=tmp_path, app_name=self._APP_NAME)
        # Assert
        assert dirs == AppDirs(
            data=local_app_data / self._APP_NAME,
            cache=Path(tempfile.gettempdir()) / self._APP_NAME,
            portable=False,
        )

    def test_portable_with_marker(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """
        Keeps the data and the cache under the program's folder when the marker is there, without %LOCALAPPDATA%.

        :param monkeypatch: pytest monkeypatch
        :param tmp_path: temporary directory of the test, used as the program's folder
        :return: None
        """
        # Arrange
        monkeypatch.delenv(name="LOCALAPPDATA", raising=False)
        (tmp_path / "portable.txt").write_text(data="", encoding="utf-8")
        # Act
        dirs: AppDirs = AppDirs.detect(app_dir=tmp_path, app_name=self._APP_NAME)
        # Assert
        assert dirs == AppDirs(data=tmp_path / "userdata", cache=tmp_path / "userdata" / "cache", portable=True)

    def test_marker_folder_is_not_a_marker(self, local_app_data: Path, tmp_path: Path) -> None:
        """
        Ignores a folder named like the marker: only a file switches the portable mode on.

        :param local_app_data: the folder %LOCALAPPDATA% points at
        :param tmp_path: temporary directory of the test, used as the program's folder
        :return: None
        """
        # Arrange
        (tmp_path / "portable.txt").mkdir()
        # Act
        dirs: AppDirs = AppDirs.detect(app_dir=tmp_path, app_name=self._APP_NAME)
        # Assert
        assert dirs.portable is False
        assert dirs.data == local_app_data / self._APP_NAME
