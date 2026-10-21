"""Tests of the background worker."""

import threading
import tkinter as tk
from typing import Callable, cast

import pytest

from app.ui.worker import Worker

__all__: tuple = ()


class _FakeRoot:
    """Stands in for Tk's after(): keeps the scheduled calls for the test to run."""

    def __init__(self) -> None:
        """
        Start with nothing scheduled.
        """
        self.scheduled: list[Callable[[], None]] = []

    def after(self, ms: int, func: Callable[[], None]) -> str:
        """
        Keep a scheduled call like Tk's after().

        :param ms: delay, ignored
        :param func: the call
        :return: identifier of the scheduled call
        """
        self.scheduled.append(func)
        return f"after#{len(self.scheduled)}"


class TestWorker:
    """Tests of Worker."""

    @pytest.fixture(name="root")
    def _root(self) -> _FakeRoot:
        """
        Create the fake Tk root.

        :return: fake root
        """
        return _FakeRoot()

    @staticmethod
    def _unexpected(value: object) -> None:
        """
        Fail the test from a callback that must not be called.

        :param value: what the callback got
        :return: None
        """
        raise AssertionError(f"unexpected callback with {value!r}")

    @staticmethod
    def _finish(*, worker: Worker, root: _FakeRoot) -> None:
        """
        Let the worker run every submitted task, then pick up their callbacks once.

        :param worker: the worker
        :param root: fake root holding the scheduled pickup
        :return: None
        """
        worker.close()
        worker.join(timeout=5)
        root.scheduled[-1]()

    def test_results_in_order(self, root: _FakeRoot) -> None:
        """
        Hands the results to on_done in the order the tasks were submitted.

        :param root: fake root
        :return: None
        """
        # Arrange
        worker: Worker = Worker(root=cast(tk.Misc, root))
        results: list[int] = []
        for number in range(3):
            worker.submit(task=lambda value=number: value * 10, on_done=results.append, on_error=self._unexpected)
        # Act
        self._finish(worker=worker, root=root)
        # Assert
        assert results == [0, 10, 20]

    def test_error_to_on_error(self, root: _FakeRoot) -> None:
        """
        Hands a task's exception to on_error.

        :param root: fake root
        :return: None
        """
        # Arrange
        worker: Worker = Worker(root=cast(tk.Misc, root))
        errors: list[Exception] = []
        failure: ValueError = ValueError("broken")

        def task() -> None:
            """
            Fail.

            :return: None
            """
            raise failure

        worker.submit(task=task, on_done=self._unexpected, on_error=errors.append)
        # Act
        self._finish(worker=worker, root=root)
        # Assert
        assert errors == [failure]

    def test_tasks_off_the_calling_thread(self, root: _FakeRoot) -> None:
        """
        Runs tasks in its own thread, never in the one that submitted them.

        :param root: fake root
        :return: None
        """
        # Arrange
        worker: Worker = Worker(root=cast(tk.Misc, root))
        threads: list[threading.Thread] = []
        worker.submit(task=threading.current_thread, on_done=threads.append, on_error=self._unexpected)
        # Act
        self._finish(worker=worker, root=root)
        # Assert
        assert threads and threads[0] is not threading.current_thread()

    def test_pickup_goes_on_after_failing_callback(self, root: _FakeRoot) -> None:
        """
        Schedules the next pickup even when a callback raises.

        :param root: fake root
        :return: None
        """
        # Arrange
        worker: Worker = Worker(root=cast(tk.Misc, root))
        done: threading.Event = threading.Event()

        def fail(_: None) -> None:
            """
            Fail in the callback.

            :param _: task result
            :return: None
            """
            raise RuntimeError("callback failed")

        worker.submit(task=lambda: None, on_done=fail, on_error=self._unexpected)
        # The second task starts only after the first one's callback was queued.
        worker.submit(task=done.set, on_done=lambda _: None, on_error=self._unexpected)
        done.wait(timeout=5)
        scheduled: int = len(root.scheduled)
        # Act & Assert
        with pytest.raises(RuntimeError):
            root.scheduled[-1]()
        assert len(root.scheduled) == scheduled + 1
        worker.close()
