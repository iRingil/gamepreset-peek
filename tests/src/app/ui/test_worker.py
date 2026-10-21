"""Tests of the background worker."""

import sys
import threading
from types import TracebackType

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.worker import Worker

__all__: tuple = ()


class TestWorker:
    """Tests of Worker; callbacks are delivered by processing the Qt events once the tasks are done."""

    @staticmethod
    def _unexpected(value: object) -> None:
        """
        Fail the test from a callback that must not be called.

        :param value: what the callback got
        :return: None
        """
        raise AssertionError(f"unexpected callback with {value!r}")

    @staticmethod
    def _finish(*, worker: Worker, qt_app: QApplication) -> None:
        """
        Wait until the worker ran every submitted task, then deliver their callbacks.

        :param worker: the worker
        :param qt_app: Qt application whose events carry the callbacks
        :return: None
        """
        done: threading.Event = threading.Event()
        worker.submit(task=done.set, on_done=lambda _: None, on_error=lambda _: None)
        done.wait(timeout=5)
        qt_app.processEvents()

    def test_results_in_order(self, qt_app: QApplication) -> None:
        """
        Hands the results to on_done in the order the tasks were submitted.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
        results: list[int] = []
        for number in range(3):
            worker.submit(task=lambda value=number: value * 10, on_done=results.append, on_error=self._unexpected)
        # Act
        self._finish(worker=worker, qt_app=qt_app)
        # Assert
        assert results == [0, 10, 20]

    def test_error_to_on_error(self, qt_app: QApplication) -> None:
        """
        Hands a task's exception to on_error.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
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
        self._finish(worker=worker, qt_app=qt_app)
        # Assert
        assert errors == [failure]

    def test_tasks_off_the_calling_thread(self, qt_app: QApplication) -> None:
        """
        Runs tasks in its own thread, never in the one that submitted them.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
        threads: list[threading.Thread] = []
        worker.submit(task=threading.current_thread, on_done=threads.append, on_error=self._unexpected)
        # Act
        self._finish(worker=worker, qt_app=qt_app)
        # Assert
        assert threads and threads[0] is not threading.current_thread()

    def test_callbacks_in_ui_thread(self, qt_app: QApplication) -> None:
        """
        Calls the callbacks in the thread of the Qt application.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
        threads: list[threading.Thread] = []
        worker.submit(task=lambda: None, on_done=lambda _: threads.append(threading.current_thread()), on_error=print)
        # Act
        self._finish(worker=worker, qt_app=qt_app)
        # Assert
        assert threads == [threading.current_thread()]

    def test_delivery_goes_on_after_failing_callback(
        self, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Delivers later results even when a callback raises; the error goes to the exception hook.

        :param qt_app: Qt application
        :param monkeypatch: replaces the exception hook
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
        hooked: list[BaseException] = []
        results: list[int] = []

        def hook(_: type[BaseException], error: BaseException, __: TracebackType | None) -> None:
            """
            Keep an unhandled error.

            :param _: exception type
            :param error: exception
            :param __: traceback
            :return: None
            """
            hooked.append(error)

        def fail(_: int) -> None:
            """
            Fail in the callback.

            :param _: task result
            :return: None
            """
            raise RuntimeError("callback failed")

        monkeypatch.setattr(target=sys, name="excepthook", value=hook)
        worker.submit(task=lambda: 1, on_done=fail, on_error=self._unexpected)
        worker.submit(task=lambda: 2, on_done=results.append, on_error=self._unexpected)
        # Act
        self._finish(worker=worker, qt_app=qt_app)
        # Assert
        assert (results, [str(error) for error in hooked]) == ([2], ["callback failed"])

    def test_nothing_delivered_after_close(self, qt_app: QApplication) -> None:
        """
        Drops the results of tasks that finish after close().

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        worker: Worker = Worker()
        results: list[int] = []
        worker.submit(task=lambda: 1, on_done=results.append, on_error=self._unexpected)
        # Act
        worker.close()
        worker.join(timeout=5)
        qt_app.processEvents()
        # Assert
        assert not results
