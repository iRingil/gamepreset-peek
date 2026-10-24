"""Tests of the entry point's handling of errors raised in Qt slots."""

from types import TracebackType
from typing import Iterator
from unittest.mock import MagicMock

import pytest
from loguru import logger
from PySide6.QtWidgets import QApplication

# noinspection PyProtectedMember
from app.__main__ import _Application

__all__: tuple = ()


class TestLogUnhandled:
    """Tests of the exception hook the application installs for Qt slots."""

    @pytest.fixture(name="records")
    def _records(self) -> Iterator[list[str]]:
        """
        Collect the log lines as "LEVEL message", the traceback included.

        :return: collected lines
        """
        records: list[str] = []
        sink: int = logger.add(sink=records.append, format="{level} {message}\n{exception}")
        yield records
        logger.remove(sink)

    @pytest.fixture(name="quit_app")
    def _quit_app(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """
        Stand in for stopping the Qt event loop.

        :param monkeypatch: pytest monkeypatch
        :return: the stand-in
        """
        quit_app: MagicMock = MagicMock()
        monkeypatch.setattr(target=QApplication, name="quit", value=quit_app)
        return quit_app

    @staticmethod
    def _raised(*, error: BaseException) -> tuple[type[BaseException], BaseException, TracebackType | None]:
        """
        Raise an exception and catch it the way the exception hook receives it.

        :param error: exception to raise
        :return: type, exception and traceback
        """
        with pytest.raises(expected_exception=type(error)) as caught:
            raise error
        return caught.type, caught.value, caught.tb

    def test_error_logged(self, records: list[str], quit_app: MagicMock) -> None:
        """
        Logs an error with its traceback and keeps the application running.

        :param records: collected log lines
        :param quit_app: stand-in for stopping the event loop
        :return: None
        """
        # Arrange
        exc_type, exc_value, traceback = self._raised(error=ValueError("broken row"))
        # Act
        _Application._log_unhandled(exc_type, exc_value, traceback)  # pylint: disable=protected-access
        # Assert
        assert len(records) == 1
        assert records[0].startswith("ERROR Unhandled error in the window") and "ValueError: broken row" in records[0]
        quit_app.assert_not_called()

    def test_interrupt_stops(self, records: list[str], quit_app: MagicMock) -> None:
        """
        Stops the application on Ctrl+C, logging it as a normal stop without a traceback.

        :param records: collected log lines
        :param quit_app: stand-in for stopping the event loop
        :return: None
        """
        # Arrange
        exc_type, exc_value, traceback = self._raised(error=KeyboardInterrupt())
        # Act
        _Application._log_unhandled(exc_type, exc_value, traceback)  # pylint: disable=protected-access
        # Assert
        assert records == ["INFO Interrupted\n\n"]
        quit_app.assert_called_once_with()
