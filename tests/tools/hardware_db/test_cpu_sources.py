"""Tests of reading CPU names from BOINC host dumps and InstLatx64 CPUID dumps."""

import gzip
from typing import Iterator

import pytest
import requests
import responses

from app.infra.http_client import HttpClient
from hardware_db.cpu_sources import BoincHosts, Cpu, Downloaded, InstLatDumps

__all__: tuple = ()

# A Raptor Lake dump: brand string leaves of logical CPU #0, repeated by the next CPU as InstLatx64 dumps do.
_RAPTOR_LAKE_DUMP: str = """------[ CPUID Registers / Logical CPU #0 ]------
CPUID 00000000: 00000020-756E6547-6C65746E-49656E69 [GenuineIntel]
CPUID 80000002: 68743331-6E654720-746E4920-52286C65 [13th Gen Intel(R]
CPUID 80000003: 6F432029-54286572-6920294D-33312D39 [) Core(TM) i9-13]
CPUID 80000004: 4B303039-00000046-00000000-00000000 [900KF]
------[ CPUID Registers / Logical CPU #1 ]------
CPUID 80000002: 68743331-6E654720-746E4920-52286C65 [13th Gen Intel(R]
"""


class _Hosts:
    """Host records of a BOINC dump, laid out one field per line as BOINC writes them."""

    @staticmethod
    def xml(*, hosts: list[tuple[str, str, str]]) -> str:
        """
        Write the dump of the given hosts.

        :param hosts: vendor, model and operating system of each host
        :return: XML of the dump
        """
        records: list[str] = [
            f"<host>\n    <id>{number}</id>\n    <p_vendor>{vendor}</p_vendor>\n    <p_model>{model}</p_model>\n"
            f"    <os_name>{os_name}</os_name>\n  <ncpus>8</ncpus>\n</host>"
            for number, (vendor, model, os_name) in enumerate(hosts, start=1)
        ]
        return '<?xml version="1.0" encoding="iso-8859-1"?>\n<hosts>\n' + "\n".join(records) + "\n</hosts>\n"


class TestBoincHosts:
    """Tests of BoincHosts."""

    def test_windows_x86_only(self) -> None:
        """
        Takes Intel and AMD CPUs of Windows 10 and 11 hosts, each name once, without the CPUID signature.

        :return: None
        """
        # Arrange
        xml: str = _Hosts.xml(
            hosts=[
                (
                    "GenuineIntel",
                    "Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz [Family 6 Model 158 Stepping 9]",
                    "Microsoft Windows 10",
                ),
                (
                    "AuthenticAMD",
                    "AMD Ryzen 9 9950X3D 16-Core Processor [Family 26 Model 68 Stepping 0]",
                    "Microsoft Windows 11",
                ),
                (
                    "AuthenticAMD",
                    "AMD Ryzen 9 9950X3D 16-Core Processor [x86 Family 26 Model 68 Stepping 0]",
                    "Microsoft Windows 11",
                ),
                ("GenuineIntel", "Intel(R) Xeon(R) CPU E5520 @ 2.27GHz [Family 6 Model 26 Stepping 5]", "Linux Ubuntu"),
                ("GenuineIntel", "Intel(R) Core(TM)2 CPU 6400 @ 2.13GHz", "Microsoft Windows 7"),
                ("GenuineIntel", "Intel(R) Xeon(R) Gold 6230R CPU @ 2.10GHz", "Microsoft Windows Server 2019"),
                ("ARM", "ARMv8 Processor rev 4 (v8l)", "Android"),
                ("GenuineIntel", "", "Microsoft Windows 10"),
            ]
        )
        # Act
        cpus: set[Cpu] = BoincHosts.cpus(lines=xml.splitlines(keepends=True))
        # Assert
        assert cpus == {
            Cpu(name="Intel(R) Core(TM) i5-7400 CPU @ 3.00GHz", vendor="intel"),
            Cpu(name="AMD Ryzen 9 9950X3D 16-Core Processor", vendor="amd"),
        }

    @pytest.fixture(name="http")
    def _http(self) -> Iterator[HttpClient]:
        """
        Create an HTTP client.

        :return: HTTP client
        """
        with HttpClient() as http:
            yield http

    @responses.activate
    def test_download(self, http: HttpClient) -> None:
        """
        Downloads every dump and merges their CPUs.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        dumps: list[tuple[str, str]] = [
            ("GenuineIntel", "Intel(R) Core(TM) i7-14700K"),
            ("AuthenticAMD", "AMD Ryzen 7 7840H w/ Radeon 780M Graphics"),
        ]
        for url, (vendor, model) in zip(BoincHosts.URLS, dumps, strict=True):
            xml: str = _Hosts.xml(hosts=[(vendor, model, "Microsoft Windows 11")])
            responses.get(url=url, body=gzip.compress(data=xml.encode(encoding="iso-8859-1")))
        # Act
        downloaded: Downloaded = BoincHosts.download(http=http)
        # Assert
        assert downloaded == Downloaded(
            cpus={
                Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel"),
                Cpu(name="AMD Ryzen 7 7840H w/ Radeon 780M Graphics", vendor="amd"),
            },
            failed=(),
        )

    @responses.activate
    def test_dump_down(self, http: HttpClient) -> None:
        """
        Skips a dump that can't be downloaded and keeps the CPUs of the others.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        first, second = BoincHosts.URLS
        responses.get(url=first, body=requests.ConnectTimeout("no answer"))
        xml: str = _Hosts.xml(hosts=[("GenuineIntel", "Intel(R) Core(TM) i7-14700K", "Microsoft Windows 11")])
        responses.get(url=second, body=gzip.compress(data=xml.encode(encoding="iso-8859-1")))
        # Act
        downloaded: Downloaded = BoincHosts.download(http=http)
        # Assert
        assert downloaded == Downloaded(cpus={Cpu(name="Intel(R) Core(TM) i7-14700K", vendor="intel")}, failed=(first,))

    @responses.activate
    def test_not_gzip(self, http: HttpClient) -> None:
        """
        Skips a dump whose body is not gzip, e.g. an error page served with status 200.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        for url in BoincHosts.URLS:
            responses.get(url=url, body=b"<html>maintenance</html>")
        # Act
        downloaded: Downloaded = BoincHosts.download(http=http)
        # Assert
        assert downloaded == Downloaded(cpus=set(), failed=BoincHosts.URLS)


class TestInstLatDumps:
    """Tests of InstLatDumps."""

    def test_brand_string(self) -> None:
        """
        Assembles the CPU name from the brand string leaves of the first logical CPU.

        :return: None
        """
        # Arrange & Act
        name: str | None = InstLatDumps.brand_string(text=_RAPTOR_LAKE_DUMP)
        # Assert
        assert name == "13th Gen Intel(R) Core(TM) i9-13900KF"

    def test_no_brand_string(self) -> None:
        """
        Gives no name for a dump of a CPU without brand string leaves.

        :return: None
        """
        # Arrange
        text: str = "CPUID 00000000: 00000001-756E6547-6C65746E-49656E69 [GenuineIntel]\n"
        # Act
        name: str | None = InstLatDumps.brand_string(text=text)
        # Assert
        assert name is None

    @pytest.fixture(name="http")
    def _http(self) -> Iterator[HttpClient]:
        """
        Create an HTTP client.

        :return: HTTP client
        """
        with HttpClient() as http:
            yield http

    @responses.activate
    def test_download(self, http: HttpClient) -> None:
        """
        Reads only the Intel and AMD CPUID dumps of the repository tree.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        dump_path: str = "GenuineIntel/GenuineIntel00B0671_RaptorLake_02_CPUID.txt"
        tree: list[dict[str, str]] = [
            {"path": dump_path, "type": "blob"},
            {"path": "GenuineIntel/GenuineIntel00B0671_RaptorLake_02_InstLatX64.txt", "type": "blob"},
            {"path": "CentaurHauls/CentaurHauls00006F2_Isaiah_CPUID.txt", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]
        responses.get(url=InstLatDumps.TREE_URL, json={"tree": tree})
        responses.get(url=InstLatDumps.RAW_URL + dump_path, body=_RAPTOR_LAKE_DUMP)
        # Act
        downloaded: Downloaded = InstLatDumps.download(http=http)
        # Assert
        assert downloaded == Downloaded(
            cpus={Cpu(name="13th Gen Intel(R) Core(TM) i9-13900KF", vendor="intel")}, failed=()
        )

    @responses.activate
    def test_dump_down(self, http: HttpClient) -> None:
        """
        Skips a dump that can't be downloaded and keeps the CPUs of the others.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        good: str = "GenuineIntel/GenuineIntel00B0671_RaptorLake_02_CPUID.txt"
        missing: str = "AuthenticAMD/AuthenticAMD0B40F40_Zen5_CPUID.txt"
        tree: list[dict[str, str]] = [{"path": good, "type": "blob"}, {"path": missing, "type": "blob"}]
        responses.get(url=InstLatDumps.TREE_URL, json={"tree": tree})
        responses.get(url=InstLatDumps.RAW_URL + good, body=_RAPTOR_LAKE_DUMP)
        responses.get(url=InstLatDumps.RAW_URL + missing, status=404)
        # Act
        downloaded: Downloaded = InstLatDumps.download(http=http)
        # Assert
        assert downloaded == Downloaded(
            cpus={Cpu(name="13th Gen Intel(R) Core(TM) i9-13900KF", vendor="intel")},
            failed=(InstLatDumps.RAW_URL + missing,),
        )

    @responses.activate
    def test_tree_down(self, http: HttpClient) -> None:
        """
        Skips the whole source when its file list can't be read.

        :param http: HTTP client
        :return: None
        """
        # Arrange
        responses.get(url=InstLatDumps.TREE_URL, status=403, json={"message": "API rate limit exceeded"})
        # Act
        downloaded: Downloaded = InstLatDumps.download(http=http)
        # Assert
        assert downloaded == Downloaded(cpus=set(), failed=(InstLatDumps.TREE_URL,))
