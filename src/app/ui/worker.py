"""Background execution of blocking service calls, with their results handed back to the Tk thread."""

import threading
import tkinter as tk
from dataclasses import dataclass
from functools import partial
from queue import Empty, Queue
from typing import Any, Callable, Protocol

from loguru import logger

from app.config import WORKER_POLL_MS

__all__: tuple[str, ...] = ("TaskRunner", "Worker")


class TaskRunner(Protocol):  # pylint: disable=too-few-public-methods
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
class _Job:
    """A queued task with its callbacks."""

    task: Callable[[], Any]
    on_done: Callable[[Any], None]
    on_error: Callable[[Exception], None]


class Worker:
    """Runs tasks one at a time in a daemon thread; the Tk thread picks up their callbacks with root.after.

    Tk is not thread-safe, so the worker thread never touches widgets: it only fills a queue the Tk thread drains."""

    def __init__(self, *, root: tk.Misc, poll_ms: int = WORKER_POLL_MS) -> None:
        """
        Start the worker thread and the polling of its results.

        :param root: any widget of the Tk application, for after()
        :param poll_ms: milliseconds between two pickups of results
        """
        self._root: tk.Misc = root
        self._poll_ms: int = poll_ms
        self._jobs: Queue[_Job | None] = Queue()
        self._callbacks: Queue[Callable[[], None]] = Queue()
        self._closed: bool = False
        self._thread: threading.Thread = threading.Thread(target=self._run, name="worker", daemon=True)
        self._thread.start()
        self._root.after(ms=self._poll_ms, func=self._poll)

    def submit[T](
        self, *, task: Callable[[], T], on_done: Callable[[T], None], on_error: Callable[[Exception], None]
    ) -> None:
        """
        Queue a task; tasks run in the order they were submitted.

        :param task: blocking call
        :param on_done: called with the result in the Tk thread
        :param on_error: called with the error in the Tk thread
        :return: None
        """
        self._jobs.put(item=_Job(task=task, on_done=on_done, on_error=on_error))

    def close(self) -> None:
        """
        Stop taking results and let the thread end after the task it runs; a hung request doesn't block the exit.

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
            try:
                result: Any = job.task()
            except Exception as error:  # pylint: disable=broad-exception-caught
                logger.opt(exception=error).error("Background task failed")
                self._callbacks.put(item=partial(job.on_error, error))
            else:
                self._callbacks.put(item=partial(job.on_done, result))

    def _poll(self) -> None:
        """
        Call the callbacks of finished tasks, then schedule the next pickup unless the worker is closed.

        :return: None
        """
        try:
            while True:
                try:
                    callback: Callable[[], None] = self._callbacks.get_nowait()
                except Empty:
                    break
                callback()
        finally:
            # A failing callback goes to Tk's error report; the pickup must go on anyway.
            if not self._closed:
                self._root.after(ms=self._poll_ms, func=self._poll)
