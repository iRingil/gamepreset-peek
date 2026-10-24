"""Status lines of the main window: texts that translate themselves when shown, with how serious they are."""

from dataclasses import dataclass
from typing import Callable

import requests

from app.core.models import HardwareCheck, HardwareState
from app.core.ops_api import OpsFormatError
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.infra.http_client import HttpClientError
from app.ui.views import StatusLevel

__all__: tuple[str, ...] = ("Status", "StatusTexts")


@dataclass(frozen=True, slots=True)
class Status:
    """A status line that translates itself into the UI language when shown, and how serious it is."""

    text: Callable[[], str]
    level: StatusLevel


class StatusTexts:
    """Makes the status lines; each one is translated with the translator in use at the time it is shown."""

    _COMPONENTS: dict[str, UiText] = {
        "cpu": UiText.COMPONENT_CPU,
        "gpu": UiText.COMPONENT_GPU,
        "memory": UiText.COMPONENT_MEMORY,
        "os": UiText.COMPONENT_OS,
    }

    def __init__(self, *, translator: Callable[[], Translator]) -> None:
        """
        Translate with the translator of the UI language.

        :param translator: gives the translator in use, which a language switch replaces
        """
        self._translator: Callable[[], Translator] = translator

    def info(self, *, item: UiText, **values: str) -> Status:
        """
        Make a line that only informs, e.g. of loading.

        :param item: the text
        :param values: placeholder values by name
        :return: the line
        """
        return self._status(item=item, level=StatusLevel.INFO, values=values)

    def warning(self, *, item: UiText, **values: str) -> Status:
        """
        Make a line that warns of something short of the request, e.g. a preset of another resolution.

        :param item: the text
        :param values: placeholder values by name
        :return: the line
        """
        return self._status(item=item, level=StatusLevel.WARNING, values=values)

    def error(self, *, item: UiText, error: Exception) -> Status:
        """
        Make the line of a failure, naming its cause in a few words; the details are in the logs.

        :param item: the text, with an {error} placeholder
        :param error: the failure
        :return: the line
        """
        cause: UiText
        values: dict[str, str]
        cause, values = self._cause(error=error)
        return Status(
            text=lambda: self._translator().text(item=item, error=self._translator().text(item=cause, **values)),
            level=StatusLevel.ERROR,
        )

    def problem(self, *, check: HardwareCheck) -> Status:
        """
        Explain why presets can't be requested with the hardware.

        :param check: a result other than READY
        :return: the line, an error
        """
        if check.state is HardwareState.NO_NVIDIA_GPU:
            return self._status(item=UiText.NO_NVIDIA_GPU, level=StatusLevel.ERROR, values={})
        if check.state is HardwareState.NO_CPU:
            return self._status(item=UiText.CPU_NOT_DETECTED, level=StatusLevel.ERROR, values={})
        if check.failed == ("cpu",):
            return self._status(item=UiText.CPU_REJECTED, level=StatusLevel.ERROR, values={})
        if check.failed == ("gpu",):
            return self._status(item=UiText.GPU_REJECTED, level=StatusLevel.ERROR, values={})
        failed: tuple[str, ...] = check.failed
        return Status(
            text=lambda: self._translator().text(
                item=UiText.HARDWARE_REJECTED,
                components=", ".join(
                    self._translator().text(item=self._COMPONENTS[name]) if name in self._COMPONENTS else name
                    for name in failed
                ),
            ),
            level=StatusLevel.ERROR,
        )

    @staticmethod
    def _cause(*, error: Exception) -> tuple[UiText, dict[str, str]]:
        """
        Name the cause of a failure as the user can act on it: the connection, the server, its answer, or the app.

        :param error: the failure
        :return: the text of the cause and its placeholder values
        """
        # A connect timeout is a ConnectionError as well; only a read timeout means the server went silent.
        if isinstance(error, requests.ConnectionError):
            return UiText.ERROR_NO_CONNECTION, {}
        if isinstance(error, requests.Timeout):
            return UiText.ERROR_NO_ANSWER, {}
        if isinstance(error, HttpClientError):
            return UiText.ERROR_HTTP, {"status": str(error.status)}
        if isinstance(error, OpsFormatError):
            return UiText.ERROR_BAD_ANSWER, {}
        return UiText.ERROR_UNEXPECTED, {}

    def _status(self, *, item: UiText, level: StatusLevel, values: dict[str, str]) -> Status:
        """
        Make a line translated at the time it is shown.

        :param item: the text
        :param level: how serious the line is
        :param values: placeholder values by name
        :return: the line
        """
        return Status(text=lambda: self._translator().text(item=item, **values), level=level)
