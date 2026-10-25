"""A flat light and dark Qt theme for PySide6 on Windows, reworked from PyQtDarkTheme (licenses in LICENSE.txt).

The package imports nothing from the app around it: an app passes its colors, its QSS and a folder for icon files."""

from .theme import FlatTheme

__all__: tuple[str, ...] = ("FlatTheme",)
