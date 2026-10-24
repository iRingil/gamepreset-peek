"""Tests of the warning about a folder the program can't write to."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.i18n.translator import Translator
from app.ui.read_only_folder import ReadOnlyFolder

__all__: tuple = ()


class TestReadOnlyFolder:
    """Tests of ReadOnlyFolder."""

    def test_warn(self, qt_app: QApplication, locale_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Shows a warning naming the folder and how to fix it, with no window behind it.

        :param qt_app: Qt application
        :param locale_dir: compiled catalogs
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        warning: MagicMock = MagicMock()
        monkeypatch.setattr(target=QMessageBox, name="warning", value=warning)
        folder: Path = Path("C:/Program Files/GamePreset Peek/app/data")
        # Act
        ReadOnlyFolder.warn(translator=Translator(language="en", locale_dir=locale_dir), folder=folder)
        # Assert
        parent: object
        title: str
        text: str
        parent, title, text = warning.call_args.args
        assert (parent, title, str(folder) in text, "Program Files, or" in text) == (
            None,
            "GamePreset Peek",
            True,
            True,
        )
        assert qt_app is not None
