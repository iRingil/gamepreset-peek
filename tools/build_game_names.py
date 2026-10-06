"""Build the bundled game names file (slug -> display name) from the NVIDIA App ontology fingerprint.db.

Usage: python tools/build_game_names.py <path to fingerprint.db>"""

import argparse
import json

# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
from pathlib import Path

from loguru import logger

__all__: tuple = ()

_OUTPUT: Path = Path(__file__).resolve().parents[1] / "src" / "app" / "data" / "game_names.json"


class _GameNamesBuilder:
    """Reads display names from fingerprint.db and writes them as a sorted JSON object."""

    @classmethod
    def build(cls, *, source: Path, output: Path) -> None:
        """
        Read the display names of all games and write them to the output file.

        :param source: path to fingerprint.db
        :param output: path to the JSON file to write
        :return: None
        """
        names: dict[str, str] = cls._read(source=source)
        output.parent.mkdir(parents=True, exist_ok=True)
        text: str = json.dumps(obj=dict(sorted(names.items())), ensure_ascii=False, indent=2)
        output.write_text(data=text + "\n", encoding="utf-8", newline="\n")
        logger.info("Wrote {} game names to {}", len(names), output)

    @classmethod
    def _read(cls, *, source: Path) -> dict[str, str]:
        """
        Read the display name of every fingerprint that has one.

        :param source: path to fingerprint.db
        :return: display names by game slug
        """
        names: dict[str, str] = {}
        fingerprint: ET.Element
        for fingerprint in ET.parse(source=source).getroot().iter(tag="Fingerprint"):
            slug: str | None = fingerprint.get(key="name")
            # A fingerprint may repeat DisplayName: the first one is taken.
            display_name: str | None = fingerprint.findtext(path="DisplayName")
            if not slug or not display_name or not display_name.strip():
                logger.warning("Skipped fingerprint {!r}: no display name", slug)
                continue
            names[slug] = cls._clean(name=display_name)
        return names

    @staticmethod
    def _clean(*, name: str) -> str:
        """
        Strip surrounding whitespace and repair UTF-8 text that was decoded as Latin-1 ("Â®" -> "®").

        :param name: display name as stored in fingerprint.db
        :return: cleaned display name
        """
        name = name.strip()
        try:
            repaired: str = name.encode(encoding="latin-1").decode(encoding="utf-8")
        except UnicodeError:
            return name
        if repaired != name:
            logger.info("Repaired name {!r} -> {!r}", name, repaired)
        return repaired


if __name__ == "__main__":
    _parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Build game_names.json from fingerprint.db.")
    _parser.add_argument("source", type=Path, help="path to fingerprint.db of NVIDIA App")
    _GameNamesBuilder.build(source=_parser.parse_args().source, output=_OUTPUT)
