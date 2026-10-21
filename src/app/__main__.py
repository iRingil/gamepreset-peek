"""Entry point: set up logging, wire the service and the window, run the Tk event loop."""

import ctypes
import tkinter as tk
from typing import Any

from loguru import logger

from app.core.game_names import GameNames
from app.core.hardware import GpuList, GpuRanks, HardwareDetector
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

    def __init__(self, *, logging_manager: LoggingManager) -> None:
        """
        Keep the logging setup whose lines the log panel shows.

        :param logging_manager: configured logging
        """
        self._logging: LoggingManager = logging_manager

    def run(self) -> None:
        """
        Wire everything and run the Tk event loop.

        :return: None
        """
        with HttpClient() as http:
            service: PresetService = PresetService(
                api=OpsApi(http=http),
                names=GameNames.load(),
                gpu_list=GpuList.load(),
                ranks=GpuRanks.load(),
                detector=HardwareDetector(),
                store=UserSettingsStore(),
            )
            translator: Translator = Translator(language=Translator.pick_language(saved=service.saved_language()))
            self._enable_dpi_awareness()
            root: tk.Tk = tk.Tk()
            window: MainWindow = MainWindow(root=root, log_lines=self._logging.lines)
            worker: Worker = Worker(root=root)
            presenter: Presenter = Presenter(
                view=window, service=service, runner=worker, translator=translator, theme=service.saved_theme()
            )
            window.connect(presenter=presenter)
            presenter.start()
            try:
                root.mainloop()
            finally:
                worker.close()

    @staticmethod
    def _enable_dpi_awareness() -> None:
        """
        Draw the window at the real screen resolution instead of letting Windows stretch it (blurry when scaled).

        :return: None
        """
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        set_awareness: Any = ctypes.WinDLL(name="shcore")["SetProcessDpiAwareness"]
        # 1 = system DPI aware: Tk reads the scale once at start.
        set_awareness(1)


if __name__ == "__main__":
    _logging: LoggingManager = LoggingManager(debug=True)
    logger.info("Starting")
    try:
        _Application(logging_manager=_logging).run()
    except Exception:
        logger.exception("Application failed")
        raise
    finally:
        logger.info("Stopped")
