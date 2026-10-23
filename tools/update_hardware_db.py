"""Update the bundled hardware database with new CPUs and GPUs NVIDIA accepts; run monthly by GitHub Actions.

Run from the repository root with src and tools on the import path:
PYTHONPATH=src:tools python tools/update_hardware_db.py [--report report.md] (on Windows: PYTHONPATH=src;tools)"""

import argparse
from pathlib import Path

import requests
from loguru import logger

from hardware_db.cpu_sources import BoincHosts, Downloaded, InstLatDumps
from hardware_db.gpu_sources import PciIds
from hardware_db.storage import HardwareDbWriter
from hardware_db.updater import HardwareUpdater

from app.config import APP_DB
from app.core.ops_api import OpsApi
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple = ()


class _Update:  # pylint: disable=too-few-public-methods
    """Downloads the sources, updates the database and writes the report."""

    @staticmethod
    def run(*, db: Path, report: Path | None) -> None:
        """
        Run one update.

        :param db: database file
        :param report: file for the Markdown report, None to log it only
        :return: None
        """
        with HttpClient() as http, HardwareDbWriter(path=db) as writer:
            updater: HardwareUpdater = HardwareUpdater(db=writer, api=OpsApi(http=http))
            sources: list[Downloaded] = [BoincHosts.download(http=http), InstLatDumps.download(http=http)]
            for source in sources:
                updater.report.failed += source.failed
            updater.update_cpus(candidates=set().union(*(source.cpus for source in sources)))
            try:
                pci_ids: PciIds | None = PciIds(text=http.get_bytes(url=PciIds.URL).decode(encoding="utf-8"))
            except (requests.RequestException, HttpClientError) as error:
                logger.warning("Skipped GPUs: {!r}", error)
                updater.report.failed.append(PciIds.URL)
                pci_ids = None
            if pci_ids is not None:
                updater.update_gpus(pci_ids=pci_ids)
        text: str = updater.report.markdown()
        logger.info("Update done:\n{}", text)
        if report is not None:
            report.write_text(data=text, encoding="utf-8", newline="\n")


if __name__ == "__main__":  # pragma: no cover
    _parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Update the hardware database.")
    _parser.add_argument("--db", type=Path, default=APP_DB, help="database file (default: the bundled one)")
    _parser.add_argument("--report", type=Path, help="write the Markdown report to this file")
    _arguments: argparse.Namespace = _parser.parse_args()
    _Update.run(db=_arguments.db, report=_arguments.report)
