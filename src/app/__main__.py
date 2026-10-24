"""Entry point: set up logging, wire the service and the window, run the Qt event loop."""

import ctypes
import sys
from types import TracebackType

from loguru import logger
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_ICON_FILE, APP_USER_MODEL_ID, SAVE_WAIT_SECONDS
from app.core.covers import CoverCache
from app.core.database import AppDatabase
from app.core.game_finder import GameFinder
from app.core.hardware import HardwareDetector
from app.core.ops_api import OpsApi
from app.core.service import PresetService
from app.core.user_settings import UserSettingsStore
from app.i18n.translator import Translator
from app.infra.elevation import Elevation
from app.infra.http_client import HttpClient
from app.infra.logger import LoggingManager
from app.ui.debouncer import QtDebouncer
from app.ui.exe_icons import ExeIcons
from app.ui.main_window import MainWindow
from app.ui.presenter import Presenter
from app.ui.read_only_folder import ReadOnlyFolder
from app.ui.single_instance import SingleInstance
from app.ui.theme import Theme
from app.ui.typography import Typography
from app.ui.worker import Runners, Worker

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
            database: AppDatabase = AppDatabase(http=http)
            service: PresetService = PresetService(
                api=OpsApi(http=http),
                database=database,
                data=database.load(),
                detector=HardwareDetector(),
                store=UserSettingsStore(),
                finder=GameFinder(),
                covers=CoverCache(http=http),
            )
            translator: Translator = Translator(language=Translator.pick_language(saved=service.saved_language()))
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
            application: QApplication = QApplication(sys.argv)
            application.setWindowIcon(QIcon(str(APP_ICON_FILE)))
            # The theme's first call sets the style, which restores the Windows fonts of lists and menus: install
            # the font after it and before any widget, since font changes reach widgets only once the loop runs.
            Theme.apply(mode=service.saved_theme())
            Typography.install()
            sys.excepthook = self._log_unhandled
            # Checked before the copy claims its name: a copy started as administrator must not find this one.
            if not database.writable():
                if ReadOnlyFolder.ask(translator=translator, folder=database.path.parent):
                    Elevation.relaunch()
                return
            instance: SingleInstance = SingleInstance()
            if not instance.claim():
                return
            window: MainWindow = MainWindow(log_lines=self._logging.lines)
            instance.activated.connect(window.bring_to_front)
            requests: Worker = Worker(name="requests")
            finder: Worker = Worker(name="finder")
            updater: Worker = Worker(name="updater")
            saver: Worker = Worker(name="saver")
            presenter: Presenter = Presenter(
                view=window,
                service=service,
                runners=Runners(requests=requests, finder=finder, updater=updater, saver=saver),
                debouncer=QtDebouncer(parent=window),
                icons=ExeIcons(),
                translator=translator,
                theme=service.saved_theme(),
                auto_update=service.saved_auto_update(),
            )
            window.attach(presenter=presenter)
            presenter.start()
            window.show()
            try:
                application.exec()
            finally:
                for worker in (requests, finder, updater, saver):
                    worker.close()
                # Settings changed just before the window closed are still written; a hung request is left behind.
                saver.join(timeout=SAVE_WAIT_SECONDS)

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
