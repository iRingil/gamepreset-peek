"""NVIDIA optimal playable settings (OPS) endpoints: requests and parsing of the answers into models."""

import hashlib
import json
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from typing import Any, Iterator

from loguru import logger

from app.config import (
    OPS_CATALOG_URL,
    OPS_COMMON_FILES_URL,
    OPS_COMPATIBILITY_URL,
    OPS_PRESETS_URL,
    TRANSLATION_LANGUAGES,
)
from app.core.models import (
    Compatibility,
    GamePresets,
    Hardware,
    PresetsFile,
    RemoteFile,
    ResolutionPreset,
    Setting,
    SettingTranslation,
    Translations,
)
from app.infra.http_client import HttpClient

__all__: tuple[str, ...] = ("OpsApi", "OpsFormatError")


class OpsFormatError(Exception):
    """Raised when an NVIDIA answer or file does not have the expected structure or checksum."""


class OpsApi:
    """Requests the game catalog, compatibility check, presets and translations from NVIDIA and parses them.

    HTTP failures propagate from HttpClient as they are; an answer of unexpected structure raises OpsFormatError."""

    def __init__(self, *, http: HttpClient) -> None:
        """
        Use the given HTTP client for all requests.

        :param http: HTTP client
        """
        self._http: HttpClient = http

    def games(self) -> tuple[str, ...]:
        """
        Request the catalog of games NVIDIA has presets for.

        :return: game identifiers (slugs), sorted
        """
        with self._parsing(what="game catalog"):
            catalog: Any = self._http.get_json(url=OPS_CATALOG_URL)
            games: tuple[str, ...] = tuple(sorted(self._typed(value=catalog["applications"], kind=dict)))
        logger.info("Catalog: {} games", len(games))
        return games

    def check_compatibility(self, *, hardware: Hardware) -> Compatibility:
        """
        Ask NVIDIA whether it supports the hardware.

        :param hardware: the user's hardware
        :return: overall result and the names of the failed components ("cpu", "gpu", "memory", "os")
        """
        with self._parsing(what="compatibility answer"):
            answer: Any = self._http.get_json(
                url=OPS_COMPATIBILITY_URL, params=self._hardware_params(hardware=hardware)
            )
            criteria: dict[str, Any] = self._typed(value=answer["criteria"], kind=dict)
            compatibility: Compatibility = Compatibility(
                ok=self._typed(value=criteria["overallState"], kind=bool),
                failed=tuple(
                    self._typed(value=state["name"], kind=str)
                    for state in self._typed(value=criteria.get("states", []), kind=list)
                    if not self._typed(value=state["state"], kind=bool)
                ),
            )
        logger.info("Compatibility: {}", compatibility)
        return compatibility

    def game_presets(self, *, game_id: str, hardware: Hardware) -> GamePresets:
        """
        Request the presets NVIDIA recommends for a game on the hardware.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param hardware: the user's hardware
        :return: profile, presets file and the preset of each resolution (none when NVIDIA has no recommendation)
        """
        with self._parsing(what=f"preset answer for {game_id}"):
            answer: dict[str, Any] = self._typed(
                value=self._http.get_json(
                    url=OPS_PRESETS_URL.format(game_id=game_id), params=self._hardware_params(hardware=hardware)
                ),
                kind=dict,
            )
            if len(answer) != 1:
                raise ValueError(f"expected one profile, got {sorted(answer)}")
            profile: str
            body: Any
            ((profile, body),) = answer.items()
            presets: GamePresets = GamePresets(
                profile=profile,
                version=self._typed(value=body["version"], kind=str),
                presets_file=self._remote_file(entry=body["pops"]),
                resolutions=tuple(
                    ResolutionPreset(
                        resolution=self._typed(value=entry["resolution"], kind=str),
                        preset_index=self._typed(value=entry["pops"], kind=int),
                        rate=self._typed(value=entry["rate"], kind=int),
                        below_min_spec=self._typed(value=entry["belowMinSpec"], kind=bool),
                    )
                    for entry in self._typed(value=body["ops"], kind=list)
                ),
            )
        logger.info("Presets of {}: profile {}, {} resolutions", game_id, profile, len(presets.resolutions))
        return presets

    def presets_file(self, *, file: RemoteFile) -> PresetsFile:
        """
        Download a game's presets file.

        :param file: presets file from GamePresets
        :return: settings and presets
        """
        body: bytes = self._download(file=file)
        with self._parsing(what=f"presets file {file.url}"):
            # Despite its .tsv name in NVIDIA App's cache, the file is JSON.
            document: Any = json.loads(s=body)
            settings: tuple[Setting, ...] = tuple(
                self._setting(entry=entry) for entry in self._typed(value=document["settings"], kind=list)
            )
            presets: tuple[tuple[str, ...], ...] = tuple(
                self._preset_values(values=self._typed(value=preset["values"], kind=dict), count=len(settings))
                for preset in self._typed(value=document["pops"], kind=list)
            )
        logger.info("Presets file: {} settings, {} presets", len(settings), len(presets))
        return PresetsFile(settings=settings, presets=presets)

    def translation_file(self, *, game_id: str, profile: str) -> RemoteFile:
        """
        Request the common files of a game and return its translation file.

        :param game_id: game identifier, e.g. "baldurs_gate_3"
        :param profile: profile from GamePresets
        :return: the game's translation file
        """
        with self._parsing(what=f"common files of {game_id}"):
            common: Any = self._http.get_json(url=OPS_COMMON_FILES_URL.format(game_id=game_id, profile=profile))
            translations: list[Any] = self._typed(value=common["translations"], kind=list)
            if len(translations) != 1:
                raise ValueError(f"expected one translation file, got {len(translations)}")
            return self._remote_file(entry=translations[0])

    def translations(self, *, file: RemoteFile) -> Translations:
        """
        Download a game's translation file and keep the UI languages of it.

        :param file: translation file from translation_file()
        :return: translated setting names and values
        """
        body: bytes = self._download(file=file)
        with self._parsing(what=f"translation file {file.url}"):
            root: ET.Element = ET.fromstring(text=body)
            languages: dict[str, dict[str, SettingTranslation]] = {
                language.attrib["name"]: {
                    setting.attrib["name"]: SettingTranslation(
                        name=setting.attrib["translation"],
                        values={
                            value.attrib["name"]: value.attrib["translation"]
                            for value in setting.iterfind(path="value")
                        },
                    )
                    for setting in language.iterfind(path="setting")
                }
                for language in root.iterfind(path="language")
                if language.attrib["name"] in TRANSLATION_LANGUAGES
            }
        logger.info("Translations: {}", sorted(languages))
        return Translations(languages=languages)

    def _download(self, *, file: RemoteFile) -> bytes:
        """
        Download a file and check its sha256.

        :param file: file to download
        :return: content of the file
        """
        body: bytes = self._http.get_bytes(url=file.url)
        if hashlib.sha256(body).hexdigest() != file.sha256.lower():
            raise OpsFormatError(f"sha256 mismatch for {file.url}")
        return body

    @classmethod
    def _remote_file(cls, *, entry: Any) -> RemoteFile:
        """
        Parse a file reference of an answer.

        :param entry: object with url, sha256 and size
        :return: the file reference
        """
        return RemoteFile(
            url=cls._typed(value=entry["url"], kind=str),
            sha256=cls._typed(value=entry["sha256"], kind=str),
            size=cls._typed(value=entry["size"], kind=int),
        )

    @classmethod
    def _setting(cls, *, entry: Any) -> Setting:
        """
        Parse an entry of the settings list of a presets file.

        :param entry: one-key object {name: {"type": type}}
        :return: the setting
        """
        name: str
        spec: Any
        ((name, spec),) = cls._typed(value=entry, kind=dict).items()
        return Setting(name=name, type=cls._typed(value=spec["type"], kind=str))

    @classmethod
    def _preset_values(cls, *, values: dict[str, Any], count: int) -> tuple[str, ...]:
        """
        Order the values of a preset by setting.

        :param values: values keyed by the 1-based position of a setting as a string
        :param count: number of settings
        :return: one value per setting, in the order of settings
        """
        return tuple(cls._typed(value=values[str(position)], kind=str) for position in range(1, count + 1))

    @staticmethod
    def _hardware_params(*, hardware: Hardware) -> dict[str, str]:
        """
        Build the query string parameters NVIDIA identifies the hardware by.

        :param hardware: the user's hardware
        :return: query string parameters
        """
        return {
            "cpu.name": hardware.cpu_name,
            "gpu.name": hardware.gpu_name,
            "gpu.deviceID": hardware.gpu_device_id,
            "memory.size": str(hardware.memory_gb),
            "os.version": hardware.os_version,
        }

    @staticmethod
    def _typed[T](*, value: Any, kind: type[T]) -> T:
        """
        Check the type of a parsed JSON value; a bool is not accepted as an int.

        :param value: value to check
        :param kind: expected type
        :return: the value
        """
        if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
            raise TypeError(f"expected {kind.__name__}, got {value!r}")
        return value

    @staticmethod
    @contextmanager
    def _parsing(*, what: str) -> Iterator[None]:
        """
        Turn the errors of parsing an answer into OpsFormatError.

        :param what: description of the answer for the error message
        :return: context manager
        """
        try:
            yield
        except (KeyError, IndexError, TypeError, ValueError, AttributeError, ET.ParseError) as error:
            raise OpsFormatError(f"Unexpected {what}: {error!r}") from error
