"""Tests of the logging setup."""

import logging
import sys
import threading
from pathlib import Path
from queue import Empty
from typing import Iterator, NoReturn

import pytest
from loguru import logger

from app.infra import logger as logger_module
from app.infra.logger import LoggingManager

__all__: tuple = ()


class TestLoggingManager:
    """Tests of LoggingManager sinks, standard logging interception and the thread exception hook."""

    @pytest.fixture(name="log_file", autouse=True)
    def _log_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
        """
        Redirect the log file to a temporary directory and undo the global changes of LoggingManager.

        :param monkeypatch: pytest monkeypatch
        :param tmp_path: temporary directory of the test
        :return: path of the log file
        """
        log_file: Path = tmp_path / "logs" / "test.log"
        root_logger: logging.Logger = logging.getLogger()
        monkeypatch.setattr(target=logger_module, name="LOG_FILE", value=log_file)
        monkeypatch.setattr(target=threading, name="excepthook", value=threading.excepthook)
        monkeypatch.setattr(target=root_logger, name="handlers", value=root_logger.handlers)
        monkeypatch.setattr(target=root_logger, name="level", value=root_logger.level)
        yield log_file
        logger.remove()

    @staticmethod
    def _drain(manager: LoggingManager) -> list[str]:
        """
        Take all lines collected for the UI log panel.

        :param manager: logging manager under test
        :return: collected lines in logging order
        """
        lines: list[str] = []
        while True:
            try:
                lines.append(manager.lines.get_nowait())
            except Empty:
                return lines

    @staticmethod
    def _raise_runtime_error() -> NoReturn:
        """
        Fail the way a broken worker thread does.

        :return: never returns
        """
        raise RuntimeError("worker failed")

    @staticmethod
    def _raise_system_exit() -> NoReturn:
        """
        Exit a thread through SystemExit.

        :return: never returns
        """
        raise SystemExit()

    def test_panel_line(self) -> None:
        """
        Puts a formatted line without the trailing newline into the panel queue.

        :return: None
        """
        # Arrange
        manager: LoggingManager = LoggingManager(debug=False)
        # Act
        logger.info("Loaded {} games", 3)
        # Assert
        lines: list[str] = self._drain(manager=manager)
        assert len(lines) == 1
        assert lines[0].endswith("| INFO     | Loaded 3 games")
        assert not lines[0].endswith("\n")

    @pytest.mark.parametrize(
        argnames=("debug", "expected"), argvalues=[(True, 1), (False, 0)], ids=["debug", "release"]
    )
    def test_debug_level(self, debug: bool, expected: int) -> None:
        """
        Passes DEBUG records only in debug mode.

        :param debug: debug mode of the manager
        :param expected: number of panel lines expected for one DEBUG record
        :return: None
        """
        # Arrange
        manager: LoggingManager = LoggingManager(debug=debug)
        # Act
        logger.debug("Detail")
        # Assert
        assert len(self._drain(manager=manager)) == expected

    def test_file_sink(self, log_file: Path) -> None:
        """
        Writes records to the log file, creating its directory.

        :param log_file: temporary log file path
        :return: None
        """
        # Arrange
        LoggingManager(debug=False)
        # Act
        logger.info("Written to file")
        # Assert
        assert "| INFO     | " in log_file.read_text(encoding="utf-8")
        assert "Written to file" in log_file.read_text(encoding="utf-8")

    def test_stdlib_record_intercepted(self) -> None:
        """
        Redirects a standard logging record to loguru.

        :return: None
        """
        # Arrange
        manager: LoggingManager = LoggingManager(debug=False)
        # Act
        logging.getLogger(name="third.party").warning(msg="Retrying request")
        # Assert
        lines: list[str] = self._drain(manager=manager)
        assert len(lines) == 1
        assert lines[0].endswith("| WARNING  | Retrying request")

    def test_stdlib_record_attributed_to_caller(self, log_file: Path) -> None:
        """
        Attributes an intercepted standard logging record to its real caller, not to the logging module.

        :param log_file: temporary log file path
        :return: None
        """
        # Arrange
        LoggingManager(debug=False)
        # Act
        logging.getLogger(name="third.party").info(msg="Connected")
        # Assert
        assert ":test_stdlib_record_attributed_to_caller:" in log_file.read_text(encoding="utf-8")

    def test_thread_exception_logged(self) -> None:
        """
        Logs an exception that escaped a thread, with the thread name and the traceback.

        :return: None
        """
        # Arrange
        manager: LoggingManager = LoggingManager(debug=False)
        thread: threading.Thread = threading.Thread(target=self._raise_runtime_error, name="worker")
        # Act
        thread.start()
        thread.join()
        # Assert
        lines: list[str] = self._drain(manager=manager)
        assert len(lines) == 1
        assert lines[0].splitlines()[0].endswith("| ERROR    | Unhandled error in thread worker")
        assert "RuntimeError: worker failed" in lines[0]

    def test_thread_system_exit_ignored(self) -> None:
        """
        Logs nothing for a thread that ended through SystemExit.

        :return: None
        """
        # Arrange
        manager: LoggingManager = LoggingManager(debug=False)
        thread: threading.Thread = threading.Thread(target=self._raise_system_exit, name="worker")
        # Act
        thread.start()
        thread.join()
        # Assert
        assert not self._drain(manager=manager)

    def test_no_stderr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Works without stderr, as in a windowed exe.

        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=sys, name="stderr", value=None)
        # Act
        manager: LoggingManager = LoggingManager(debug=False)
        logger.info("No console")
        # Assert
        assert len(self._drain(manager=manager)) == 1
