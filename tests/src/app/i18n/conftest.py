"""Fixtures shared by the i18n tests."""

from pathlib import Path

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

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
