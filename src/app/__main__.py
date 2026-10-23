"""Entry point: set up logging, wire the service and the window, run the Qt event loop."""

import ctypes
import sys
from types import TracebackType

from loguru import logger
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON_FILE, APP_USER_MODEL_ID
from app.core.game_names import GameNames
from app.core.hardware import CpuList, GpuList, GpuRanks, HardwareDetector
from app.core.ops_api import OpsApi
from app.core.service import PresetService
from app.core.user_settings import UserSettingsStore
from app.i18n.translator import Translator
from app.infra.http_client import HttpClient
from app.infra.logger import LoggingManager
from app.ui.main_window import MainWindow
from app.ui.presenter import Presenter
from app.ui.worker import Worker

__all__: tuple = ()


class _Application:  # pylint: disable=too-few-public-methods
    """Builds the application and runs it until the window is closed."""

    def __init__(self, *, logging_manager: LoggingManager) -> None:  # pragma: no cover
        """
        Keep the logging setup whose lines the log panel shows.

        :param logging_manager: configured logging
        """
        self._logging: LoggingManager = logging_manager

    def run(self) -> None:  # pragma: no cover
        """
        Wire everything and run the Qt event loop.

        :return: None
        """
        with HttpClient() as http:
            service: PresetService = PresetService(
                api=OpsApi(http=http),
                names=GameNames.load(),
                cpu_list=CpuList.load(),
                gpu_list=GpuList.load(),
                ranks=GpuRanks.load(),
                detector=HardwareDetector(),
                store=UserSettingsStore(),
            )
            translator: Translator = Translator(language=Translator.pick_language(saved=service.saved_language()))
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
            application: QApplication = QApplication(sys.argv)
            application.setWindowIcon(QIcon(str(APP_ICON_FILE)))
            sys.excepthook = self._log_unhandled
            window: MainWindow = MainWindow(log_lines=self._logging.lines)
            worker: Worker = Worker()
            presenter: Presenter = Presenter(
                view=window, service=service, runner=worker, translator=translator, theme=service.saved_theme()
            )
            window.attach(presenter=presenter)
            presenter.start()
            window.show()
            try:
                application.exec()
            finally:
                worker.close()

    @staticmethod
    def _log_unhandled(
        exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType | None
    ) -> None:
        """
        Log an error raised in a Qt slot, which would otherwise go to the missing stderr; stop the loop on Ctrl+C.

        :param exc_type: exception type
        :param exc_value: exception
        :param traceback: traceback
        :return: None
        """
        # Ctrl+C (also the IDE's Stop button) is a normal stop; PySide ends the process on SystemExit by itself.
        if issubclass(exc_type, KeyboardInterrupt):
            logger.info("Interrupted")
            QApplication.quit()
            return
        logger.opt(exception=(exc_type, exc_value, traceback)).error("Unhandled error in the window")


if __name__ == "__main__":  # pragma: no cover
    _logging: LoggingManager = LoggingManager(debug=True)
    logger.info("Starting")
    try:
        _Application(logging_manager=_logging).run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception:
        logger.exception("Application failed")
        raise
    finally:
        logger.info("Stopped")
