# ruff: noqa: S101
"""Tests of the Qt debouncer."""

import pytest
from PySide6.QtTest import QTest

from app.ui.debouncer import QtDebouncer

__all__: tuple[str, ...] = ()

_DELAY_MS: int = 20


class TestQtDebouncer:
    """Delayed actions, one per key."""

    @pytest.mark.usefixtures("qt_app")
    def test_last_action_of_key_runs_once(self) -> None:
        """
        Runs only the action scheduled last under a key, once, after the delay.

        :return: None
        """
        # Arrange
        debouncer: QtDebouncer = QtDebouncer()
        runs: list[str] = []
        # Act
        debouncer.call(key="search", delay_ms=_DELAY_MS, action=lambda: runs.append("first"))
        debouncer.call(key="search", delay_ms=_DELAY_MS, action=lambda: runs.append("second"))
        before: list[str] = list(runs)
        QTest.qWait(_DELAY_MS * 5)
        # Assert
        assert (before, runs) == ([], ["second"])

    @pytest.mark.usefixtures("qt_app")
    def test_keys_apart(self) -> None:
        """
        Runs the actions of different keys independently.

        :return: None
        """
        # Arrange
        debouncer: QtDebouncer = QtDebouncer()
        runs: list[str] = []
        # Act
        debouncer.call(key="search", delay_ms=_DELAY_MS, action=lambda: runs.append("search"))
        debouncer.call(key="presets", delay_ms=_DELAY_MS, action=lambda: runs.append("presets"))
        QTest.qWait(_DELAY_MS * 5)
        # Assert
        assert sorted(runs) == ["presets", "search"]
