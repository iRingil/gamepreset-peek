"""Tests of the NVIDIA OPS endpoints client on answers saved from NVIDIA (mordhau)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import responses
from responses import matchers

from app.config import OPS_CATALOG_URL, OPS_COMMON_FILES_URL, OPS_COMPATIBILITY_URL, OPS_PRESETS_URL
from app.core.models import (
    Compatibility,
    GamePresets,
    Hardware,
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Setting,
    Translations,
)
from app.core.ops_api import OpsApi, OpsFormatError
from app.infra.http_client import HttpClientError

__all__: tuple = ()

_DATA: Path = Path(__file__).parent / "data"
_GAME: str = "mordhau"
_FILE_URL: str = "https://cdn.example.test/file"
_HARDWARE: Hardware = Hardware(
    cpu_name="13th Gen Intel(R) Core(TM) i9-13900HX",
    gpu_name="NVIDIA GeForce RTX 4060 Laptop GPU",
    gpu_device_id="28e0",
    memory_gb=16,
    os_version="10.0",
)
_HARDWARE_PARAMS: dict[str, str] = {
    "cpu.name": "13th Gen Intel(R) Core(TM) i9-13900HX",
    "gpu.name": "NVIDIA GeForce RTX 4060 Laptop GPU",
    "gpu.deviceID": "28e0",
    "memory.size": "16",
    "os.version": "10.0",
}


class _Data:
    """Saved NVIDIA answers and references to them."""

    @staticmethod
    def read(*, name: str) -> bytes:
        """
        Read a saved answer.

        :param name: file name in the data directory
        :return: content of the file
        """
        return (_DATA / name).read_bytes()

    @staticmethod
    def remote_file(*, body: bytes) -> RemoteFile:
        """
        Build a reference to a file with the given content.

        :param body: content of the file
        :return: file reference with the matching sha256
        """
        return RemoteFile(url=_FILE_URL, sha256=hashlib.sha256(body).hexdigest(), size=len(body))


class TestGames:
    """Tests of OpsApi.games."""

    def test_sorted_slugs(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Returns the catalog's game identifiers sorted.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=OPS_CATALOG_URL, body=_Data.read(name="catalog.json"))
        # Act
        games: tuple[str, ...] = api.games()
        # Assert
        assert games == ("2xko", "baldurs_gate_3", "mordhau")

    @pytest.mark.parametrize(
        argnames="body",
        argvalues=(b"<html>", b'{"version": "1"}', b'{"applications": []}'),
        ids=("not-json", "no-applications", "applications-not-object"),
    )
    def test_unexpected_answer(self, mock: responses.RequestsMock, api: OpsApi, body: bytes) -> None:
        """
        Raises OpsFormatError for an answer that is not a catalog.

        :param mock: requests mock
        :param api: API client
        :param body: answer body
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=OPS_CATALOG_URL, body=body)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.games()


class TestCheckCompatibility:
    """Tests of OpsApi.check_compatibility."""

    def test_compatible(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Sends the hardware in the query and reports no failed components for a positive answer.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        mock.add(
            method=responses.GET,
            url=OPS_COMPATIBILITY_URL,
            json={"criteria": {"overallState": True}},
            match=(matchers.query_param_matcher(params=_HARDWARE_PARAMS),),
        )
        # Act
        compatibility: Compatibility = api.check_compatibility(hardware=_HARDWARE)
        # Assert
        assert compatibility == Compatibility(ok=True, failed=())

    def test_incompatible(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Lists the components NVIDIA reports as failed.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        states: list[dict[str, Any]] = [
            {"name": "cpu", "state": False},
            {"name": "gpu", "state": True},
            {"name": "memory", "state": True},
            {"name": "os", "state": False},
        ]
        mock.add(
            method=responses.GET,
            url=OPS_COMPATIBILITY_URL,
            json={"criteria": {"overallState": False, "states": states}},
        )
        # Act
        compatibility: Compatibility = api.check_compatibility(hardware=_HARDWARE)
        # Assert
        assert compatibility == Compatibility(ok=False, failed=("cpu", "os"))

    @pytest.mark.parametrize(
        argnames="answer",
        argvalues=({}, {"criteria": {"overallState": "true"}}, {"criteria": {"overallState": False, "states": [{}]}}),
        ids=("no-criteria", "state-not-bool", "state-without-name"),
    )
    def test_unexpected_answer(self, mock: responses.RequestsMock, api: OpsApi, answer: dict[str, Any]) -> None:
        """
        Raises OpsFormatError for an answer of unexpected structure.

        :param mock: requests mock
        :param api: API client
        :param answer: answer JSON
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=OPS_COMPATIBILITY_URL, json=answer)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.check_compatibility(hardware=_HARDWARE)


class TestGamePresets:
    """Tests of OpsApi.game_presets."""

    @pytest.fixture(name="answer")
    def _answer(self) -> dict[str, Any]:
        """
        Load the saved preset answer.

        :return: preset answer of mordhau for an RTX 4060 Laptop
        """
        answer: dict[str, Any] = json.loads(s=_Data.read(name="mordhau.ops.json"))
        return answer

    def test_parse(self, mock: responses.RequestsMock, api: OpsApi, answer: dict[str, Any]) -> None:
        """
        Requests the game's URL with the hardware in the query and parses the profile, file and resolutions.

        :param mock: requests mock
        :param api: API client
        :param answer: saved preset answer
        :return: None
        """
        # Arrange
        mock.add(
            method=responses.GET,
            url=OPS_PRESETS_URL.format(game_id=_GAME),
            json=answer,
            match=(matchers.query_param_matcher(params=_HARDWARE_PARAMS),),
        )
        # Act
        presets: GamePresets = api.game_presets(game_id=_GAME, hardware=_HARDWARE)
        # Assert
        assert presets.profile == "regular_rtx"
        assert presets.version == "1163492583.4151619460.138697779"
        assert presets.presets_file == RemoteFile(
            url="https://wpc-download.gfe.nvidia.com/static/8a78f2ea/pops/mordhau/ops_rtx.json",
            sha256="d7c567d0e3eed98b7fc9c4fe3e0ed01ba55988e147b8f05e2e748b83d06c4447",
            size=9389,
        )
        assert len(presets.resolutions) == 8
        assert presets.resolutions[1] == ResolutionPreset(
            resolution="1920x1080", preset_index=11, rate=40, below_min_spec=False
        )

    def test_no_recommendation(self, mock: responses.RequestsMock, api: OpsApi, answer: dict[str, Any]) -> None:
        """
        Returns no resolutions when NVIDIA has no recommendation for the game on the hardware.

        :param mock: requests mock
        :param api: API client
        :param answer: saved preset answer
        :return: None
        """
        # Arrange
        answer["regular_rtx"]["ops"] = []
        mock.add(method=responses.GET, url=OPS_PRESETS_URL.format(game_id=_GAME), json=answer)
        # Act
        presets: GamePresets = api.game_presets(game_id=_GAME, hardware=_HARDWARE)
        # Assert
        assert presets.resolutions == ()

    def test_two_profiles(self, mock: responses.RequestsMock, api: OpsApi, answer: dict[str, Any]) -> None:
        """
        Raises OpsFormatError when the answer holds more than one profile.

        :param mock: requests mock
        :param api: API client
        :param answer: saved preset answer
        :return: None
        """
        # Arrange
        answer["regular"] = answer["regular_rtx"]
        mock.add(method=responses.GET, url=OPS_PRESETS_URL.format(game_id=_GAME), json=answer)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.game_presets(game_id=_GAME, hardware=_HARDWARE)

    def test_bool_index(self, mock: responses.RequestsMock, api: OpsApi, answer: dict[str, Any]) -> None:
        """
        Raises OpsFormatError for a bool where a preset index is expected, though bool is an int subclass.

        :param mock: requests mock
        :param api: API client
        :param answer: saved preset answer
        :return: None
        """
        # Arrange
        answer["regular_rtx"]["ops"][0]["pops"] = True
        mock.add(method=responses.GET, url=OPS_PRESETS_URL.format(game_id=_GAME), json=answer)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.game_presets(game_id=_GAME, hardware=_HARDWARE)

    def test_http_error_propagates(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Lets HttpClientError through, as NVIDIA answers 404 to hardware it doesn't know.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=OPS_PRESETS_URL.format(game_id=_GAME), status=404)
        # Act & Assert
        with pytest.raises(HttpClientError):
            api.game_presets(game_id=_GAME, hardware=_HARDWARE)


class TestPresetsFile:
    """Tests of OpsApi.presets_file."""

    def test_parse(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Parses the settings with their types and orders each preset's values by setting.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        body: bytes = _Data.read(name="mordhau.pops.json")
        mock.add(method=responses.GET, url=_FILE_URL, body=body, content_type="binary/octet-stream")
        # Act
        presets: PresetsFile = api.presets_file(file=_Data.remote_file(body=body))
        # Assert
        assert len(presets.settings) == 18
        assert len(presets.presets) == 12
        assert presets.settings[11] == Setting(name="Resolution Scale", type="FLOAT")
        assert presets.settings[16] == Setting(name="Vertical Sync", type="DRVENUM")
        assert presets.presets[0][:3] == ("Off", "Off", "No Cloth")
        assert presets.presets[0][11] == "0.750"

    def test_checksum_mismatch(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Raises OpsFormatError when the downloaded file doesn't match its sha256.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        body: bytes = _Data.read(name="mordhau.pops.json")
        mock.add(method=responses.GET, url=_FILE_URL, body=body + b" ")
        # Act & Assert
        with pytest.raises(OpsFormatError, match="sha256"):
            api.presets_file(file=_Data.remote_file(body=body))

    @pytest.mark.parametrize(
        argnames="document",
        argvalues=(
            {"settings": [{"A": {"type": "ENUM"}}], "pops": [{"values": {"2": "Low"}}]},
            {"settings": [{"A": {"type": "ENUM"}, "B": {"type": "ENUM"}}], "pops": []},
            {"settings": [{"A": {"type": "ENUM"}}], "pops": [{"values": {"1": 1}}]},
            {"settings": [{"A": {}}], "pops": []},
        ),
        ids=("value-missing", "two-settings-in-entry", "value-not-string", "no-type"),
    )
    def test_unexpected_file(self, mock: responses.RequestsMock, api: OpsApi, document: dict[str, Any]) -> None:
        """
        Raises OpsFormatError for a presets file of unexpected structure.

        :param mock: requests mock
        :param api: API client
        :param document: presets file JSON
        :return: None
        """
        # Arrange
        body: bytes = json.dumps(obj=document).encode()
        mock.add(method=responses.GET, url=_FILE_URL, body=body)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.presets_file(file=_Data.remote_file(body=body))


class TestTranslationFile:
    """Tests of OpsApi.translation_file."""

    def test_parse(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Requests the common files of the game's profile and returns the translation file.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        mock.add(
            method=responses.GET,
            url=OPS_COMMON_FILES_URL.format(game_id=_GAME, profile="regular_rtx"),
            body=_Data.read(name="mordhau.common.json"),
        )
        # Act
        file: RemoteFile = api.translation_file(game_id=_GAME, profile="regular_rtx")
        # Assert
        assert file == RemoteFile(
            url="https://wpc-download.gfe.nvidia.com/static/eabfa929/translations/mordhau.translation",
            sha256="7fd3664218d4e053ef68a6c448e4032ddb825c7240cdeccd14fbc994952e0f35",
            size=151472,
        )

    def test_no_translation(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Raises OpsFormatError when the common files list no translation file.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        mock.add(
            method=responses.GET,
            url=OPS_COMMON_FILES_URL.format(game_id=_GAME, profile="regular"),
            json={"translations": [], "wrappers": [], "version": "1"},
        )
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.translation_file(game_id=_GAME, profile="regular")


class TestTranslations:
    """Tests of OpsApi.translations."""

    def test_parse(self, mock: responses.RequestsMock, api: OpsApi) -> None:
        """
        Keeps only the UI languages of the file and their setting and value translations.

        :param mock: requests mock
        :param api: API client
        :return: None
        """
        # Arrange
        body: bytes = _Data.read(name="mordhau.translation")
        mock.add(method=responses.GET, url=_FILE_URL, body=body)
        # Act
        translations: Translations = api.translations(file=_Data.remote_file(body=body))
        # Assert
        assert sorted(translations.languages) == ["en_US", "ru_RU"]
        assert translations.setting_name(language="ru_RU", setting="Vertical Sync") == "Вертикальная синхронизация"
        assert translations.value_name(language="ru_RU", setting="Ambient Occlusion", value="Off") == "Выкл."
        assert translations.value_name(language="ru_RU", setting="Resolution Scale", value="0.750") == "0.750"

    @pytest.mark.parametrize(
        argnames="body",
        argvalues=(
            b"<game><language name='ru_RU'>",
            b"<game><language name='ru_RU'><setting translation='X'/></language></game>",
            b"<game><language translation=''/></game>",
        ),
        ids=("broken-xml", "setting-without-name", "language-without-name"),
    )
    def test_unexpected_file(self, mock: responses.RequestsMock, api: OpsApi, body: bytes) -> None:
        """
        Raises OpsFormatError for a translation file of unexpected structure.

        :param mock: requests mock
        :param api: API client
        :param body: translation file content
        :return: None
        """
        # Arrange
        mock.add(method=responses.GET, url=_FILE_URL, body=body)
        # Act & Assert
        with pytest.raises(OpsFormatError):
            api.translations(file=_Data.remote_file(body=body))
