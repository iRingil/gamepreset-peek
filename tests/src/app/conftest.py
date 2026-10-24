"""Fixtures shared by the app tests: the UI catalogs, read from the source tree and compiled, and the Qt application."""

import os
from pathlib import Path
from typing import Iterator

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from PySide6.QtWidgets import QApplication

from app.config import GETTEXT_DOMAIN, LOCALE_DIR, UI_LANGUAGES

__all__: tuple = ()


@pytest.fixture(name="catalogs")
def _catalogs() -> dict[str, Catalog]:
    """
    Read the .po catalog of every UI language from the source tree.

    :return: catalogs by UI language
    """
    catalogs: dict[str, Catalog] = {}
    for language in UI_LANGUAGES:
        with (LOCALE_DIR / language / "LC_MESSAGES" / f"{GETTEXT_DOMAIN}.po").open(mode="rb") as file:
            catalogs[language] = read_po(fileobj=file, locale=language)
    return catalogs


@pytest.fixture(name="locale_dir")
def _locale_dir(tmp_path: Path, catalogs: dict[str, Catalog]) -> Path:
    """
    Compile the .po catalogs into a temporary locale folder: the .mo files are build output, not in the repository.

    :param tmp_path: temporary directory
    :param catalogs: catalogs by UI language
    :return: folder of <language>/LC_MESSAGES/<domain>.mo catalogs
    """
    for language, catalog in catalogs.items():
        path: Path = tmp_path / language / "LC_MESSAGES" / f"{GETTEXT_DOMAIN}.mo"
        path.parent.mkdir(parents=True)
        with path.open(mode="wb") as file:
            write_mo(fileobj=file, catalog=catalog)
    return tmp_path


@pytest.fixture(name="qt_app", scope="session")
def _qt_app() -> Iterator[QApplication]:
    """
    Create one Qt application for the session, drawing off-screen.

    :return: the application
    """
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application: QApplication = QApplication.instance() or QApplication([])  # type: ignore[assignment]
    yield application
