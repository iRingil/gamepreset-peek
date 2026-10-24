"""Start of this program again with administrator rights, through the Windows UAC prompt."""

import ctypes
import subprocess
import sys
from typing import Any

from loguru import logger

__all__: tuple[str, ...] = ("Elevation",)


class Elevation:
    """Starts the program again as administrator, with the command line it was started with."""

    # ShellExecute answers a value above 32 on success; the program is shown as usual.
    _SUCCESS_ABOVE: int = 32
    _SHOW_NORMAL: int = 1

    @staticmethod
    def is_admin() -> bool:
        """
        Tell whether the program runs with administrator rights.

        :return: True when it does
        """
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        is_user_an_admin: Any = ctypes.WinDLL(name="shell32")["IsUserAnAdmin"]
        return bool(is_user_an_admin())

    @classmethod
    def relaunch(cls) -> bool:
        """
        Start the program again as administrator; the user confirms it in the UAC prompt.

        :return: True when the new copy started, False when the user declined, or it failed
        """
        parameters: str = subprocess.list2cmdline(sys.orig_argv[1:])
        # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
        shell_execute: Any = ctypes.WinDLL(name="shell32")["ShellExecuteW"]
        result: int = shell_execute(None, "runas", sys.executable, parameters, None, cls._SHOW_NORMAL)
        if result <= cls._SUCCESS_ABOVE:
            logger.warning("Not started as administrator (ShellExecute {})", result)
            return False
        logger.info("Started again as administrator")
        return True
