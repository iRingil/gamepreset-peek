"""Tests of the warning about a folder the program can't write to."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.i18n.translator import Translator
from app.ui.read_only_folder import ReadOnlyFolder

__all__: tuple = ()


class TestReadOnlyFolder:
    """Tests of ReadOnlyFolder."""

    @pytest.mark.parametrize(
        argnames=("button", "restart"),
        argvalues=[("Run as administrator", True), ("Close", False)],
        ids=["restart", "close"],
    )
    def test_ask(  # pylint: disable=too-many-arguments
        self,
        qt_app: QApplication,
        locale_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        button: str,
        restart: bool,
    ) -> None:
        """
        Names the folder and tells which button the user pressed.

        :param qt_app: Qt application
        :param locale_dir: compiled catalogs
        :param monkeypatch: pytest monkeypatch
        :param button: text of the button pressed
        :param restart: whether starting again is expected
        :return: None
        """
        # Arrange
        shown: list[str] = []

        def press(box: QMessageBox) -> int:
            """
            Press a button of the box instead of waiting for the user.

            :param box: the message box
            :return: 0
            """
            shown.append(box.text())
            next(item for item in box.buttons() if item.text() == button).click()
            return 0

        monkeypatch.setattr(target=QMessageBox, name="exec", value=press)
        folder: Path = Path("C:/Program Files/GamePreset Peek/app/data")
        # Act
        answer: bool = ReadOnlyFolder.ask(translator=Translator(language="en", locale_dir=locale_dir), folder=folder)
        # Assert
        assert (answer, str(folder) in shown[0], qt_app is not None) == (restart, True, True)
