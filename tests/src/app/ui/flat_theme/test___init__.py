"""Tests of app.ui.flat_theme."""

import ast
import inspect
import sys
from pathlib import Path

import app.ui.flat_theme

__all__: tuple = ()


class TestPackage:
    """Tests of the flat theme package as a whole."""

    def test_self_contained(self) -> None:
        """
        Imports only PySide6, shiboken6 and the standard library, so another app can copy the folder as is.

        :return: None
        """
        # Arrange
        folder: Path = Path(inspect.getfile(app.ui.flat_theme)).parent
        imported: set[str] = set()
        # Act
        for path in folder.glob(pattern="*.py"):
            for node in ast.walk(ast.parse(source=path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(str(node.module).split(".", maxsplit=1)[0])
                elif isinstance(node, ast.Import):
                    imported.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        # Assert
        assert imported - sys.stdlib_module_names <= {"PySide6", "shiboken6"}
