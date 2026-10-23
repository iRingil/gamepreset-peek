"""Generate the gettext template messages.pot from the UiText enum.

Usage: PYTHONPATH=src python tools/make_pot.py, then pybabel update and pybabel compile (see CLAUDE.md)."""

import re
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po
from loguru import logger

from app.config import APP_NAME, GETTEXT_DOMAIN, LOCALE_DIR
from app.i18n.ui_text import UiText

__all__: tuple = ()


class _PotMaker:
    """Writes every UiText member as a message of the template, its member name as the translator comment."""

    _PLACEHOLDER: re.Pattern[str] = re.compile(pattern=r"\{\w+\}")

    @classmethod
    def make(cls, *, output: Path) -> None:
        """
        Write the template.

        :param output: path of the .pot file
        :return: None
        """
        catalog: Catalog = Catalog(project=APP_NAME, domain=GETTEXT_DOMAIN, charset="utf-8")
        for item in UiText:
            catalog.add(
                id=item.value,
                auto_comments=[item.name],
                flags=["python-brace-format"] if cls._PLACEHOLDER.search(string=item.value) else [],
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open(mode="wb") as file:
            write_po(fileobj=file, catalog=catalog, width=120, omit_header=False, sort_output=False)
        logger.info("Wrote {} messages to {}", len(UiText), output)


if __name__ == "__main__":  # pragma: no cover
    _PotMaker.make(output=LOCALE_DIR / f"{GETTEXT_DOMAIN}.pot")
