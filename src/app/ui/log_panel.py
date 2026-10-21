"""Read-only view of the application log at the bottom of the main window."""

from queue import Empty, Queue

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from app.config import LOG_PANEL_HEIGHT, LOG_PANEL_MAX_LINES, LOG_POLL_MS

__all__: tuple[str, ...] = ("LogPanel",)


class LogPanel(QPlainTextEdit):
    """A scrollable text that keeps appending the lines of the log queue, whether it is shown or not."""

    def __init__(self, *, lines: Queue[str], parent: QWidget | None = None) -> None:
        """
        Build the panel and start draining the queue.

        :param lines: formatted log lines, filled by the logging sink
        :param parent: widget the panel belongs to
        """
        super().__init__(parent)
        self._lines: Queue[str] = lines
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # The oldest lines are dropped beyond the limit.
        self.setMaximumBlockCount(LOG_PANEL_MAX_LINES)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        margins: int = round(self.document().documentMargin() * 2) + self.frameWidth() * 2
        self.setFixedHeight(self.fontMetrics().lineSpacing() * LOG_PANEL_HEIGHT + margins)
        self._timer: QTimer = QTimer(parent=self, interval=LOG_POLL_MS)
        self._timer.timeout.connect(self._drain)
        self._timer.start()
        self._drain()

    def _drain(self) -> None:
        """
        Append the queued lines; the view stays at the end when it was there.

        :return: None
        """
        lines: list[str] = []
        while True:
            try:
                lines.append(self._lines.get_nowait())
            except Empty:
                break
        if lines:
            self.appendPlainText("\n".join(lines))
