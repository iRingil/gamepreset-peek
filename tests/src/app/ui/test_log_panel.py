"""Tests of the log panel."""

from queue import Queue

import pytest
from PySide6.QtTest import QTest

from app.config import LOG_PANEL_MAX_LINES, LOG_POLL_MS
from app.ui.log_panel import LogPanel

__all__: tuple = ()


@pytest.mark.usefixtures("qt_app")
class TestLogPanel:
    """Tests of LogPanel."""

    def test_queued_lines_shown(self) -> None:
        """
        Shows the lines queued before it was built, read-only.

        :return: None
        """
        # Arrange
        lines: Queue[str] = Queue()
        for line in ("Starting", "Loaded settings"):
            lines.put(line)
        # Act
        panel: LogPanel = LogPanel(lines=lines)
        # Assert
        assert (panel.toPlainText(), panel.isReadOnly()) == ("Starting\nLoaded settings", True)

    def test_new_lines_appended(self) -> None:
        """
        Keeps appending the lines queued later, while hidden too.

        :return: None
        """
        # Arrange
        lines: Queue[str] = Queue()
        lines.put("Starting")
        panel: LogPanel = LogPanel(lines=lines)
        # Act
        lines.put("Stopped")
        QTest.qWait(LOG_POLL_MS * 3)
        # Assert
        assert (panel.toPlainText(), panel.isVisible()) == ("Starting\nStopped", False)

    def test_oldest_lines_dropped(self) -> None:
        """
        Drops the oldest lines beyond the limit.

        :return: None
        """
        # Arrange
        lines: Queue[str] = Queue()
        for number in range(LOG_PANEL_MAX_LINES + 5):
            lines.put(f"line {number}")
        # Act
        panel: LogPanel = LogPanel(lines=lines)
        # Assert
        assert (panel.blockCount(), panel.document().firstBlock().text()) == (LOG_PANEL_MAX_LINES, "line 5")
