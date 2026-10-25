"""Fixtures shared by the flat theme tests: the Qt application, restored to its plain look after each test."""

import os
from typing import Iterator

import pytest
from PySide6.QtWidgets import QApplication

__all__: tuple = ()


@pytest.fixture(name="qt_app", scope="session")
def _qt_app() -> Iterator[QApplication]:
    """
    Create one Qt application for the session, drawing off-screen, or take the one already running.

    :return: the application
    """
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application: QApplication = QApplication.instance() or QApplication([])  # type: ignore[assignment]
    yield application


@pytest.fixture(name="plain_app")
def _plain_app(qt_app: QApplication) -> Iterator[QApplication]:
    """
    Give the application back its plain look after a test themes it.

    :param qt_app: Qt application
    :return: the application
    """
    yield qt_app
    qt_app.setStyleSheet("")
    qt_app.setPalette(qt_app.style().standardPalette())
