"""Background execution of blocking service calls, with their results handed back to the UI thread."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from queue import Queue
from typing import Protocol

from loguru import logger
from PySide6.QtCore import QObject, Signal

__all__: tuple[str, ...] = ("Runners", "TaskRunner", "Worker")


class TaskRunner(Protocol):
    """Runs a task away from the UI and calls back with its result or error in the UI thread."""

    def submit[T](
        self, *, task: Callable[[], T], on_done: Callable[[T], None], on_error: Callable[[Exception], None]
    ) -> None:
        """
        Queue a task.

        :param task: blocking call
        :param on_done: called with the result in the UI thread
        :param on_error: called with the error in the UI thread
        :return: None
        """


@dataclass(frozen=True, slots=True)
class Runners:
    """
    The runners of the window, one per kind of work, so a slow task of one kind never holds up another.

    requests: hardware detection, NVIDIA requests and box art; finder: the search for installed games; updater: the
    database update; saver: settings writes, which the app lets finish when it closes.
    """

    requests: TaskRunner
    finder: TaskRunner
    updater: TaskRunner
    saver: TaskRunner


class Worker(QObject):
    """
    Runs tasks one at a time in a daemon thread; their callbacks reach the UI thread through a Qt signal.

    The worker object lives in the UI thread, so a signal emitted from the worker thread is queued to the UI event loop
    and widgets are only touched there.
    """

    _finished: Signal = Signal(object)

    def __init__(self, *, name: str = "worker") -> None:
        """
        Start the worker thread; create it in the UI thread.

        :param name: name of the thread, seen in the logs
        """
        super().__init__()
        # A job runs its task in the worker thread and gives the callback to deliver in the UI thread
        self._jobs: Queue[Callable[[], Callable[[], None]] | None] = Queue()
        self._closed: bool = False
        self._finished.connect(self._deliver)
        self._thread: threading.Thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit[T](
        self, *, task: Callable[[], T], on_done: Callable[[T], None], on_error: Callable[[Exception], None]
    ) -> None:
        """
        Queue a task; tasks run in the order they were submitted.

        :param task: blocking call
        :param on_done: called with the result in the UI thread
        :param on_error: called with the error in the UI thread
        :return: None
        """
        self._jobs.put(item=partial(self._execute, task=task, on_done=on_done, on_error=on_error))

    def close(self) -> None:
        """
        Stop delivering results and let the thread end after the task it runs; a hung request doesn't block the exit.

        :return: None
        """
        self._closed = True
        self._jobs.put(item=None)

    def join(self, *, timeout: float | None = None) -> None:
        """
        Wait for the thread to end after close().

        :param timeout: seconds to wait, None for no limit
        :return: None
        """
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        """
        Run the queued tasks until close().

        :return: None
        """
        while (job := self._jobs.get()) is not None:
            self._finished.emit(job())

    @staticmethod
    def _execute[T](
        *, task: Callable[[], T], on_done: Callable[[T], None], on_error: Callable[[Exception], None]
    ) -> Callable[[], None]:
        """
        Run a task and bind its result or error to the callback that gets it.

        :param task: blocking call
        :param on_done: called with the result in the UI thread
        :param on_error: called with the error in the UI thread
        :return: the callback with its argument
        """
        try:
            result: T = task()
        except Exception as error:  # noqa: BLE001 - any failure of a task goes to its error callback, not the thread
            logger.opt(exception=error).error("Background task failed")
            return partial(on_error, error)
        return partial(on_done, result)

    def _deliver(self, callback: Callable[[], None]) -> None:
        """
        Call the callback of a finished task in the UI thread, unless the worker is closed.

        :param callback: the callback with its argument bound
        :return: None
        """
        if not self._closed:
            callback()
