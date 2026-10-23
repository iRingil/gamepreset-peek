"""Tests of the Qt debouncer."""

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.debouncer import QtDebouncer

__all__: tuple = ()

_DELAY_MS: int = 20


class TestQtDebouncer:
    """Delayed actions, one per key."""

    def test_last_action_of_key_runs_once(self, qt_app: QApplication) -> None:
        """
        Runs only the action scheduled last under a key, once, after the delay.

        :param qt_app: Qt application
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

    def test_keys_apart(self, qt_app: QApplication) -> None:
        """
        Runs the actions of different keys independently.

        :param qt_app: Qt application
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
