"""Tests of the start again as administrator."""

import ctypes
import sys
from typing import Any

import pytest

from app.infra.elevation import Elevation

__all__: tuple = ()


class TestElevation:
    """Tests of Elevation."""

    @pytest.mark.parametrize(argnames=("result", "started"), argvalues=[(42, True), (5, False)], ids=["yes", "no"])
    def test_relaunch(self, monkeypatch: pytest.MonkeyPatch, result: int, started: bool) -> None:
        """
        Asks Windows to start the program as administrator with its command line; a refusal starts nothing.

        :param monkeypatch: pytest monkeypatch
        :param result: what ShellExecute answers
        :param started: whether a new copy is reported started
        :return: None
        """
        # Arrange
        calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(target=sys, name="orig_argv", value=["python.exe", "-m", "app", "--flag x"])

        def shell_execute(*args: Any) -> int:
            """
            Record the call like ShellExecuteW.

            :param args: arguments of the call
            :return: the result of the parametrization
            """
            calls.append(args)
            return result

        monkeypatch.setattr(target=ctypes, name="WinDLL", value=lambda name: {"ShellExecuteW": shell_execute})
        # Act
        relaunched: bool = Elevation.relaunch()
        # Assert
        assert relaunched == started
        assert calls == [(None, "runas", sys.executable, '-m app "--flag x"', None, 1)]

    @pytest.mark.parametrize(argnames=("answer", "admin"), argvalues=[(1, True), (0, False)], ids=["admin", "user"])
    def test_is_admin(self, monkeypatch: pytest.MonkeyPatch, answer: int, admin: bool) -> None:
        """
        Tells whether the program runs as administrator, as Windows answers.

        :param monkeypatch: pytest monkeypatch
        :param answer: what IsUserAnAdmin answers
        :param admin: the expected result
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=ctypes, name="WinDLL", value=lambda name: {"IsUserAnAdmin": lambda: answer})
        # Act
        result: bool = Elevation.is_admin()
        # Assert
        assert result == admin
