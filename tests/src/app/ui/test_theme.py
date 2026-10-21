"""Tests of the theme: the Windows app mode for AUTO and the palette and fonts on a real Tk root."""

import tkinter as tk
import winreg
from contextlib import contextmanager
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Iterator

import pytest

from app.core.models import ThemeMode
from app.ui.theme import Theme

__all__: tuple = ()


class TestResolve:
    """Tests of Theme.resolve."""

    @staticmethod
    def _registry(*, monkeypatch: pytest.MonkeyPatch, value: Any) -> None:
        """
        Fake the Windows app mode setting.

        :param monkeypatch: pytest monkeypatch
        :param value: AppsUseLightTheme value, None when the setting is missing
        :return: None
        """

        class _Key:
            """An open registry key as a context manager."""

            def __enter__(self) -> "_Key":
                """
                Enter the key.

                :return: the key
                """
                return self

            def __exit__(self, *args: object) -> None:
                """
                Close the key.

                :param args: exception details
                :return: None
                """

        def query(key: _Key, name: str) -> tuple[Any, int]:
            """
            Read the faked value.

            :param key: open key
            :param name: value name
            :return: value and type
            """
            if value is None:
                raise FileNotFoundError(name)
            return value, winreg.REG_DWORD

        monkeypatch.setattr(target=winreg, name="OpenKey", value=lambda root, path: _Key())
        monkeypatch.setattr(target=winreg, name="QueryValueEx", value=query)

    @pytest.mark.parametrize(
        argnames=("value", "expected"),
        argvalues=[(0, ThemeMode.DARK), (1, ThemeMode.LIGHT), (None, ThemeMode.LIGHT)],
        ids=["windows dark", "windows light", "setting missing"],
    )
    def test_auto(self, monkeypatch: pytest.MonkeyPatch, value: Any, expected: ThemeMode) -> None:
        """
        Takes the Windows app mode for AUTO, light when it can't be read.

        :param monkeypatch: pytest monkeypatch
        :param value: AppsUseLightTheme value
        :param expected: resolved mode
        :return: None
        """
        # Arrange
        self._registry(monkeypatch=monkeypatch, value=value)
        # Act
        mode: ThemeMode = Theme.resolve(mode=ThemeMode.AUTO)
        # Assert
        assert mode is expected

    @pytest.mark.parametrize(argnames="mode", argvalues=[ThemeMode.LIGHT, ThemeMode.DARK])
    def test_explicit(self, monkeypatch: pytest.MonkeyPatch, mode: ThemeMode) -> None:
        """
        Keeps an explicit mode whatever Windows uses.

        :param monkeypatch: pytest monkeypatch
        :param mode: chosen mode
        :return: None
        """
        # Arrange
        self._registry(monkeypatch=monkeypatch, value=0 if mode is ThemeMode.LIGHT else 1)
        # Act
        resolved: ThemeMode = Theme.resolve(mode=mode)
        # Assert
        assert resolved is mode


class TestApply:
    """Tests of Theme.apply and Theme.color on a hidden Tk root.

    The root is made inside each test: pytest swaps the standard file descriptors between fixture setup and the
    test, and a Tcl interpreter created before the swap fails to read files after it."""

    @staticmethod
    @contextmanager
    def _hidden_root() -> Iterator[tk.Tk]:
        """
        Create a hidden Tk root for the duration of a block.

        :return: context manager giving the root, destroyed at the end
        """
        root: tk.Tk = tk.Tk()
        root.withdraw()
        try:
            yield root
        finally:
            root.destroy()

    @pytest.mark.parametrize(
        argnames=("mode", "expected"),
        argvalues=[
            (ThemeMode.DARK, ("#15171c", "#d6dae1", "#4fb3ff")),
            (ThemeMode.LIGHT, ("#dcdfe4", "#20242b", "#1d6fb8")),
        ],
        ids=["dark", "light"],
    )
    def test_palette_applied(self, mode: ThemeMode, expected: tuple[str, str, str]) -> None:
        """
        Styles the widgets in the palette of the mode and gives its colors.

        :param mode: theme mode
        :param expected: background, text and accent colors
        :return: None
        """
        with self._hidden_root() as root:
            # Arrange
            theme: Theme = Theme(root=root)
            # Act
            applied: ThemeMode = theme.apply(mode=mode)
            colors: tuple[str, str, str] = (
                theme.color(name="bg"),
                theme.color(name="fg"),
                theme.color(name="accent"),
            )
            styled: tuple[str, str] = (
                str(ttk.Style(master=root).lookup(style="TLabel", option="background")),
                str(ttk.Style(master=root).theme_use()),
            )
        # Assert
        assert (applied, colors, styled) == (mode, expected, (expected[0], "clam"))

    def test_fonts_created(self) -> None:
        """
        Creates the named fonts the styles refer to, in points so that Tk scales them to the screen.

        :return: None
        """
        with self._hidden_root() as root:
            # Arrange & Act
            theme: Theme = Theme(root=root)
            size: Any = tkfont.nametofont(name=Theme.STRONG_FONT, root=root).cget(option="size")
        # Assert
        assert (size, theme.scale > 0) == (10, True)
