"""Delayed calls in the UI thread: an action scheduled under a key replaces the one still waiting under that key."""

from typing import Callable, Protocol

from PySide6.QtCore import QObject, QTimer

__all__: tuple[str, ...] = ("Debouncer", "QtDebouncer")


class Debouncer(Protocol):  # pylint: disable=too-few-public-methods
    """Runs an action once a delay has passed without another call under the same key."""

    def call(self, *, key: str, delay_ms: int, action: Callable[[], None]) -> None:
        """
        Schedule an action, dropping the one waiting under the key.

        :param key: what the action is for, e.g. "presets"
        :param delay_ms: pause before the action runs
        :param action: the action, run in the UI thread
        :return: None
        """


class QtDebouncer(QObject):
    """Debouncer on single-shot Qt timers, one per key."""

    def __init__(self, *, parent: QObject | None = None) -> None:
        """
        Start with no action waiting.

        :param parent: object the timers belong to
        """
        super().__init__(parent)
        self._timers: dict[str, QTimer] = {}
        self._actions: dict[str, Callable[[], None]] = {}

    def call(self, *, key: str, delay_ms: int, action: Callable[[], None]) -> None:
        """
        Schedule an action, dropping the one waiting under the key.

        :param key: what the action is for, e.g. "presets"
        :param delay_ms: pause before the action runs
        :param action: the action, run in the UI thread
        :return: None
        """
        if key not in self._timers:
            timer: QTimer = QTimer(parent=self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._fire(key=key))
            self._timers[key] = timer
        self._actions[key] = action
        self._timers[key].start(delay_ms)

    def _fire(self, *, key: str) -> None:
        """
        Run the action waiting under a key.

        :param key: key of the timer that ran out
        :return: None
        """
        action: Callable[[], None] | None = self._actions.pop(key, None)
        if action is not None:
            action()
