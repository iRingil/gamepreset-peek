"""Tests of the one running copy per user."""

import time
import uuid
from unittest.mock import MagicMock

import pytest
from PySide6.QtNetwork import QLocalServer
from PySide6.QtWidgets import QApplication

from app.ui.single_instance import SingleInstance

__all__: tuple = ()


class TestSingleInstance:
    """Tests of SingleInstance."""

    _WAIT_S: float = 3.0

    def test_first_copy_runs(self, qt_app: QApplication) -> None:
        """
        Lets the first copy run.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        instance: SingleInstance = SingleInstance(name=f"test-{uuid.uuid4().hex}")
        # Act
        claimed: bool = instance.claim()
        # Assert
        assert claimed and qt_app is not None

    def test_later_copy_hands_over(self, qt_app: QApplication) -> None:
        """
        Tells a later copy to quit and the running one to come to the front.

        :param qt_app: Qt application
        :return: None
        """
        # Arrange
        name: str = f"test-{uuid.uuid4().hex}"
        running: SingleInstance = SingleInstance(name=name)
        running.claim()
        activated: MagicMock = MagicMock()
        running.activated.connect(activated)
        # Act
        claimed: bool = SingleInstance(name=name).claim()
        deadline: float = time.monotonic() + self._WAIT_S
        while not activated.called and time.monotonic() < deadline:
            qt_app.processEvents()
        # Assert
        assert (claimed, activated.call_count) == (False, 1)

    def test_not_listening(self, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Still lets the copy run when it can't listen for later copies.

        :param qt_app: Qt application
        :param monkeypatch: pytest monkeypatch
        :return: None
        """
        # Arrange
        monkeypatch.setattr(target=QLocalServer, name="listen", value=lambda *_: False)
        # Act
        claimed: bool = SingleInstance(name=f"test-{uuid.uuid4().hex}").claim()
        # Assert
        assert claimed and qt_app is not None
