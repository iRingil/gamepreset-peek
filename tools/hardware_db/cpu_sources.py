"""CPU names of the sources: host dumps of BOINC projects and the CPUID dumps of InstLatx64."""

import gzip
import io
import re
import struct
from dataclasses import dataclass
from typing import Iterable, Iterator

import requests
from loguru import logger

from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple[str, ...] = ("BoincHosts", "Cpu", "Downloaded", "InstLatDumps")

_INTEL: str = "GenuineIntel"
_AMD: str = "AuthenticAMD"
_VENDORS: dict[str, str] = {_INTEL: "intel", _AMD: "amd"}


@dataclass(frozen=True, slots=True)
class Cpu:
    """A CPU name as Windows reports it, with its vendor: "amd" or "intel"."""

    name: str
    vendor: str


@dataclass(frozen=True, slots=True)
class Downloaded:
    """CPUs of a source, and the URLs that couldn't be read: a source down this time is read on the next update."""

    cpus: set[Cpu]
    failed: tuple[str, ...]


# Failures of a download or of reading what came: the source is skipped this time.
_SOURCE_ERRORS: tuple[type[Exception], ...] = (requests.RequestException, HttpClientError, OSError, EOFError, KeyError)


class _Names:
    """Cleaning of CPU names the way Windows stores them in ProcessorNameString."""

    # BOINC appends the CPUID signature: " [Family 6 Model 183 Stepping 1]", " [Intel64 Family 6 ...]".
    _TAIL: re.Pattern[str] = re.compile(pattern=r"\s*\[.*$")

    @classmethod
    def clean(cls, *, name: str) -> str:
        """
        Drop the CPUID signature, NUL padding and repeated spaces.

        :param name: raw name
        :return: name as NVIDIA matches it, empty for a blank one
        """
        return " ".join(cls._TAIL.sub(repl="", string=name.replace("\x00", "")).split())


class BoincHosts:
    """Host dumps of BOINC projects: every volunteer computer with its CPU name and operating system.

    Only Intel and AMD CPUs of Windows 10 and 11 hosts are taken: older Windows versions have no current NVIDIA
    drivers, and servers or other systems would bring in CPUs no gamer uses."""

    URLS: tuple[str, ...] = (
        "https://asteroidsathome.net/boinc/stats/host.gz",
        "https://numberfields.asu.edu/NumberFields/stats/host.gz",
    )
    _WINDOWS: tuple[str, ...] = ("Microsoft Windows 10", "Microsoft Windows 11")
    _FIELD: re.Pattern[str] = re.compile(pattern=r"<(p_vendor|p_model|os_name)>(.*?)</\1>")

    @classmethod
    def download(cls, *, http: HttpClient) -> Downloaded:
        """
        Download every dump and collect its CPUs; a dump that can't be read is skipped with a warning.

        :param http: HTTP client
        :return: CPUs of the dumps read and the URLs of the others
        """
        cpus: set[Cpu] = set()
        failed: list[str] = []
        for url in cls.URLS:
            try:
                body: bytes = http.get_bytes(url=url)
                with gzip.open(filename=io.BytesIO(initial_bytes=body), mode="rt", encoding="iso-8859-1") as lines:
                    found: set[Cpu] = cls.cpus(lines=lines)
            except _SOURCE_ERRORS as error:
                logger.warning("Skipped {}: {!r}", url, error)
                failed.append(url)
                continue
            logger.info("{}: {} MB, {} CPUs", url, len(body) // 2**20, len(found))
            cpus |= found
        return Downloaded(cpus=cpus, failed=tuple(failed))

    @classmethod
    def cpus(cls, *, lines: Iterable[str]) -> set[Cpu]:
        """
        Collect the CPUs of the Windows 10 and 11 hosts of a dump.

        :param lines: lines of the dump's XML, one field per line as BOINC writes it
        :return: CPUs found
        """
        cpus: set[Cpu] = set()
        for host in cls._hosts(lines=lines):
            vendor: str | None = _VENDORS.get(host.get("p_vendor", ""))
            name: str = _Names.clean(name=host.get("p_model", ""))
            if vendor is not None and name and host.get("os_name", "").strip() in cls._WINDOWS:
                cpus.add(Cpu(name=name, vendor=vendor))
        return cpus

    @classmethod
    def _hosts(cls, *, lines: Iterable[str]) -> Iterator[dict[str, str]]:
        """
        Read the fields of each host.

        :param lines: lines of the dump's XML
        :return: vendor, model and operating system of each host, the ones it has
        """
        host: dict[str, str] = {}
        for line in lines:
            if "<host>" in line:
                host = {}
            elif "</host>" in line:
                yield host
            else:
                match: re.Match[str] | None = cls._FIELD.search(string=line)
                if match is not None:
                    host[match.group(1)] = match.group(2)


class InstLatDumps:
    """CPUID dumps of the InstLatx64 project on GitHub: few per CPU generation, but the newest CPUs come there first.

    The CPU name is the brand string of CPUID leaves 0x80000002-0x80000004."""

    TREE_URL: str = "https://api.github.com/repos/InstLatx64/InstLatx64/git/trees/master?recursive=1"
    RAW_URL: str = "https://raw.githubusercontent.com/InstLatx64/InstLatx64/master/"
    _DUMP_PATH: re.Pattern[str] = re.compile(pattern=r"^(GenuineIntel|AuthenticAMD)/[^/]*CPUID[^/]*\.txt$")
    # "CPUID 80000002: 68743331-6E654720-746E4920-52286C65 [13th Gen Intel(R]": EAX-EBX-ECX-EDX.
    _BRAND_LEAF: re.Pattern[str] = re.compile(
        pattern=r"CPUID (8000000[234]): ([0-9A-F]{8})-([0-9A-F]{8})-([0-9A-F]{8})-([0-9A-F]{8})"
    )
    _BRAND_LEAVES: int = 3

    @classmethod
    def download(cls, *, http: HttpClient) -> Downloaded:
        """
        Download the Intel and AMD CPUID dumps and read their CPUs; a dump that can't be read is skipped with a warning.

        :param http: HTTP client
        :return: CPUs of the dumps that have a brand string, and the URLs that couldn't be read
        """
        try:
            tree: dict[str, list[dict[str, str]]] = http.get_json(url=cls.TREE_URL)
            paths: list[str] = [item["path"] for item in tree["tree"] if cls._DUMP_PATH.match(string=item["path"])]
        except _SOURCE_ERRORS as error:
            logger.warning("Skipped InstLatx64: {!r}", error)
            return Downloaded(cpus=set(), failed=(cls.TREE_URL,))
        cpus: set[Cpu] = set()
        failed: list[str] = []
        for path in paths:
            try:
                text: str = http.get_bytes(url=cls.RAW_URL + path).decode(encoding="latin-1")
            except _SOURCE_ERRORS as error:
                logger.warning("Skipped {}: {!r}", path, error)
                failed.append(cls.RAW_URL + path)
                continue
            name: str | None = cls.brand_string(text=text)
            if name is not None:
                cpus.add(Cpu(name=name, vendor=_VENDORS[path.split(sep="/")[0]]))
        logger.info("InstLatx64: {} dumps, {} CPUs", len(paths), len(cpus))
        return Downloaded(cpus=cpus, failed=tuple(failed))

    @classmethod
    def brand_string(cls, *, text: str) -> str | None:
        """
        Assemble the CPU name from the brand string leaves of the first logical CPU of a dump.

        :param text: CPUID dump
        :return: CPU name, None when the dump has no brand string
        """
        leaves: dict[str, bytes] = {}
        for leaf, *registers in cls._BRAND_LEAF.findall(string=text):
            # Every logical CPU repeats the leaves: the first one is enough.
            leaves.setdefault(leaf, b"".join(struct.pack("<I", int(register, base=16)) for register in registers))
        if len(leaves) < cls._BRAND_LEAVES:
            return None
        name: str = _Names.clean(name=b"".join(leaves[leaf] for leaf in sorted(leaves)).decode(encoding="latin-1"))
        return name or None
