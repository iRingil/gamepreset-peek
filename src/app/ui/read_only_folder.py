"""The warning shown at start when the program's folder can't be written to, e.g. under Program Files."""

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QPushButton

from app.config import APP_TITLE
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText

__all__: tuple[str, ...] = ("ReadOnlyFolder",)


class ReadOnlyFolder:  # pylint: disable=too-few-public-methods
    """Asks whether to start again as administrator; the program doesn't run without writing to its folder."""

    @staticmethod
    def ask(*, translator: Translator, folder: Path) -> bool:
        """
        Explain that the folder can't be written to and offer to start again as administrator.

        :param translator: translator of the UI language
        :param folder: the program's folder
        :return: True when the user chose to start again as administrator, False to quit
        """
        box: QMessageBox = QMessageBox(
            QMessageBox.Icon.Warning, APP_TITLE, translator.text(item=UiText.READ_ONLY_FOLDER, folder=str(folder))
        )
        restart: QPushButton = box.addButton(
            translator.text(item=UiText.RUN_AS_ADMIN), QMessageBox.ButtonRole.AcceptRole
        )
        close: QPushButton = box.addButton(translator.text(item=UiText.CLOSE), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(restart)
        box.setEscapeButton(close)
        box.exec()
        return box.clickedButton() is restart
