"""The warning shown at start when the program can't write to its folder and wasn't given administrator rights."""

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from app.config import APP_TITLE
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText

__all__: tuple[str, ...] = ("ReadOnlyFolder",)


class ReadOnlyFolder:  # pylint: disable=too-few-public-methods
    """Tells how to make the folder writable; the program quits once the warning is closed."""

    @staticmethod
    def warn(*, translator: Translator, folder: Path) -> None:
        """
        Explain that the folder can't be written to: reinstall the program elsewhere or run it as administrator.

        :param translator: translator of the UI language
        :param folder: the program's folder
        :return: None
        """
        QMessageBox.warning(None, APP_TITLE, translator.text(item=UiText.READ_ONLY_FOLDER, folder=str(folder)))
