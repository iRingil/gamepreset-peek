"""Logging setup: console, rotating file and the queue the UI log panel reads."""

import logging
import sys
import threading
from queue import Queue
from typing import TYPE_CHECKING

from loguru import logger

from app.config import LOG_FILE

if TYPE_CHECKING:  # pragma: no cover
    from loguru import Message

__all__: tuple[str, ...] = ("LoggingManager",)


class _InterceptHandler(logging.Handler):
    """Redirects standard logging records (requests, urllib3) to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """
        Redirect a standard logging record to loguru, attributed to its real caller.

        :param record: standard logging record
        :return: None
        """
        try:
            level: str | int = logger.level(name=record.levelname).name
        except ValueError:
            level = record.levelno
        # Start at emit()'s caller: emit() itself is inside logging, depth 1 counts that hop.
        frame, depth = logging.currentframe().f_back, 1
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class LoggingManager:
    """Configures loguru for the application and collects log lines for the UI log panel.

    The panel drains ``lines`` periodically; lines logged before the window exists wait in the queue."""

    def __init__(self, *, debug: bool) -> None:
        """
        Set up all sinks, standard logging interception and the thread exception hook.

        :param debug: log DEBUG records and caller details if True
        """
        self.lines: Queue[str] = Queue()
        logger.remove()
        log_level: int = logging.DEBUG if debug else logging.INFO
        caller_format: str = "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | " if debug else ""
        console_format: str = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            + caller_format
            + "<level>{message}</level>"
        )
        # A windowed exe has no console, sys.stderr is None there.
        if sys.stderr is not None:
            logger.add(sink=sys.stderr, level=log_level, format=console_format, colorize=True)
        logger.add(
            sink=LOG_FILE,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="00:00",
            retention="7 days",
            encoding="utf-8",
            backtrace=True,
            diagnose=debug,
        )
        logger.add(sink=self._to_panel, level=log_level, format="{time:HH:mm:ss} | {level: <8} | {message}")
        self._setup_intercept_handler(log_level=log_level)
        threading.excepthook = self._log_thread_exception

    def _to_panel(self, message: "Message") -> None:
        """
        Put a formatted log line into the queue of the UI log panel.

        :param message: formatted log record, ending with a newline
        :return: None
        """
        self.lines.put(item=message.rstrip("\n"))

    @staticmethod
    def _setup_intercept_handler(*, log_level: int) -> None:
        """
        Route standard logging to loguru.

        :param log_level: minimal level of the standard root logger
        :return: None
        """
        standard_logger: logging.Logger = logging.getLogger()
        standard_logger.handlers = [_InterceptHandler()]
        standard_logger.setLevel(level=log_level)

    @staticmethod
    def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
        """
        Log an exception that escaped a thread, which would otherwise go to the missing stderr.

        :param args: exception and thread details
        :return: None
        """
        if issubclass(args.exc_type, SystemExit):
            return
        thread: threading.Thread | None = args.thread
        thread_name: str = thread.name if thread is not None else "unknown"
        logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).error(
            "Unhandled error in thread {}", thread_name
        )
