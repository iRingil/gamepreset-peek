"""Tests of the status lines: their levels and their translation at the time they are shown."""

from pathlib import Path

import pytest
import requests

from app.core.models import HardwareCheck, HardwareState
from app.core.ops_api import OpsFormatError
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.infra.http_client import HttpClientError
from app.ui.status import Status, StatusTexts
from app.ui.views import StatusLevel

__all__: tuple = ()


class TestStatusTexts:
    """Tests of StatusTexts."""

    def test_levels(self, locale_dir: Path) -> None:
        """
        Makes informing lines, warnings and errors, an error carrying the failure.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        texts: StatusTexts = StatusTexts(translator=lambda: Translator(language="en", locale_dir=locale_dir))
        # Act
        lines: list[Status] = [
            texts.info(item=UiText.LOADING),
            texts.warning(item=UiText.NO_RECOMMENDATION),
            texts.error(item=UiText.REQUEST_FAILED, error=requests.ConnectionError("refused")),
        ]
        # Assert
        assert [(line.text(), line.level) for line in lines] == [
            ("Loading…", StatusLevel.INFO),
            (
                "No recommendations (there are none, or your hardware is too weak for this resolution and game)",
                StatusLevel.WARNING,
            ),
            ("Could not get data from NVIDIA: no connection, check your internet", StatusLevel.ERROR),
        ]

    @pytest.mark.parametrize(
        argnames=("error", "cause"),
        argvalues=[
            (requests.ConnectionError("refused"), "no connection, check your internet"),
            (requests.ConnectTimeout("connect timeout"), "no connection, check your internet"),
            (requests.ReadTimeout("read timeout"), "the server is not answering, try again later"),
            (
                HttpClientError(status=503, url="https://ops.example.test/?cpu.name=x", body=""),
                "the server answered with error 503",
            ),
            (OpsFormatError("Unexpected presets file"), "the server sent data in an unexpected format"),
            (OSError("access denied"), "unexpected error, see the logs"),
        ],
        ids=["connection", "connect timeout", "read timeout", "http", "format", "other"],
    )
    def test_error_cause(self, locale_dir: Path, error: Exception, cause: str) -> None:
        """
        Names the cause of a failure in a few words instead of the exception text, which stays in the logs.

        :param locale_dir: compiled catalogs
        :param error: the failure
        :param cause: the expected cause
        :return: None
        """
        # Arrange
        texts: StatusTexts = StatusTexts(translator=lambda: Translator(language="en", locale_dir=locale_dir))
        # Act
        line: Status = texts.error(item=UiText.REQUEST_FAILED, error=error)
        # Assert
        assert line.text() == f"Could not get data from NVIDIA: {cause}"

    def test_translated_when_shown(self, locale_dir: Path) -> None:
        """
        Translates a line with the translator in use when it is shown, not when it was made.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        translator: list[Translator] = [Translator(language="en", locale_dir=locale_dir)]
        line: Status = StatusTexts(translator=lambda: translator[0]).info(item=UiText.LOADING)
        english: str = line.text()
        # Act
        translator[0] = Translator(language="ru", locale_dir=locale_dir)
        # Assert
        assert english != line.text()

    @pytest.mark.parametrize(
        argnames=("check", "expected"),
        argvalues=[
            (HardwareCheck(state=HardwareState.NO_CPU), "CPU_NOT_DETECTED"),
            (HardwareCheck(state=HardwareState.REJECTED, failed=("cpu",)), "CPU_REJECTED"),
            (HardwareCheck(state=HardwareState.REJECTED, failed=("memory", "bus")), "HARDWARE_REJECTED"),
        ],
        ids=["no cpu", "cpu rejected", "several rejected"],
    )
    def test_problem(self, locale_dir: Path, check: HardwareCheck, expected: str) -> None:
        """
        Explains a hardware problem as an error, naming the rejected components it knows and the others as they are.

        :param locale_dir: compiled catalogs
        :param check: the hardware check
        :param expected: name of the expected text
        :return: None
        """
        # Arrange
        translator: Translator = Translator(language="en", locale_dir=locale_dir)
        memory: str = translator.text(item=UiText.COMPONENT_MEMORY)
        known: dict[str, str] = {
            "CPU_NOT_DETECTED": translator.text(item=UiText.CPU_NOT_DETECTED),
            "CPU_REJECTED": translator.text(item=UiText.CPU_REJECTED),
            "HARDWARE_REJECTED": translator.text(item=UiText.HARDWARE_REJECTED, components=f"{memory}, bus"),
        }
        # Act
        line: Status = StatusTexts(translator=lambda: translator).problem(check=check)
        # Assert
        assert (line.text(), line.level) == (known[expected], StatusLevel.ERROR)
