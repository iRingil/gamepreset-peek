"""One running copy per user: a second copy hands over to the first one, which comes to the front."""

import ctypes
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from app.config import INSTANCE_NAME

__all__: tuple[str, ...] = ("SingleInstance",)


class SingleInstance(QObject):
    """Claims a local socket name for this copy; a copy started later connects to it and quits.

    Windows lets only the foreground process raise a window, so the later copy, which the user has just started and
    which is in the foreground, allows any process to take the foreground; the running copy comes to the front when
    the later one hangs up after that."""

    activated: Signal = Signal()

    # AllowSetForegroundWindow: every process.
    _ANY_PROCESS: int = -1
    _WAIT_MS: int = 500

    def __init__(self, *, name: str = INSTANCE_NAME) -> None:
        """
        Use a socket name; nothing is claimed before claim().

        :param name: local socket name, the same for every copy of one user
        """
        super().__init__()
        self._name: str = name
        self._server: QLocalServer = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)

    def claim(self) -> bool:
        """
        Become the running copy, or ask the running one to come to the front.

        :return: True when this copy runs on, False when another one runs and this one should quit
        """
        socket: QLocalSocket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(self._WAIT_MS):
            # Looked up by name: attribute access to DLL functions is dynamic and unresolvable for type checkers.
            allow_foreground: Any = ctypes.WinDLL(name="user32")["AllowSetForegroundWindow"]
            allow_foreground(self._ANY_PROCESS)
            socket.disconnectFromServer()
            # The pipe is mostly closed at once; waiting is for the rare write still in flight.
            if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:  # pragma: no cover
                socket.waitForDisconnected(self._WAIT_MS)
            logger.info("Another copy is running: brought it to the front")
            return False
        # A copy that crashed may have left its name behind.
        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            logger.warning("Copies not watched for: {}", self._server.errorString())
        return True

    def _on_connection(self) -> None:
        """
        Tell that a copy started later wants this one in front, once it has hung up.

        :return: None
        """
        connection: QLocalSocket | None = self._server.nextPendingConnection()
        if connection is None:  # pragma: no cover
            return
        if connection.state() == QLocalSocket.LocalSocketState.UnconnectedState:  # pragma: no cover
            connection.deleteLater()
            self.activated.emit()
            return
        connection.disconnected.connect(self.activated.emit)
        connection.disconnected.connect(connection.deleteLater)
