"""One update of the hardware database: new CPUs and GPUs NVIDIA accepts are added, the chip ranks refreshed."""

import collections
from dataclasses import dataclass, field

from loguru import logger

from hardware_db.cpu_rules import CpuRules
from hardware_db.cpu_sources import Cpu
from hardware_db.gpu_sources import PciIds
from hardware_db.storage import HardwareDbWriter

from app.core.models import Compatibility, Gpu, Hardware
from app.core.ops_api import OpsApi
from app.infra.http_client import HttpClientError

__all__: tuple[str, ...] = ("HardwareUpdater", "UpdateReport")


@dataclass(slots=True)
class UpdateReport:
    """What an update did: added CPUs and GPUs, CPUs left out by reason, changed ranks and the sources not read."""

    cpus: list[Cpu] = field(default_factory=list)
    gpus: list[Gpu] = field(default_factory=list)
    skipped: collections.Counter[str] = field(default_factory=collections.Counter)
    ranks_changed: bool = False
    failed: list[str] = field(default_factory=list)

    def markdown(self) -> str:
        """
        Describe the update for a commit message and the workflow summary.

        :return: Markdown text: a title line, then the lists of added CPUs and GPUs
        """
        lines: list[str] = [f"Update hardware database: {len(self.cpus)} CPUs, {len(self.gpus)} GPUs", ""]
        for title, names in (
            ("AMD CPUs", [cpu.name for cpu in self.cpus if cpu.vendor == "amd"]),
            ("Intel CPUs", [cpu.name for cpu in self.cpus if cpu.vendor == "intel"]),
            ("GPUs", [f"{gpu.name} ({gpu.device_id})" for gpu in self.gpus]),
        ):
            if names:
                lines += [f"{title}:", *(f"- {name}" for name in sorted(names, key=str.casefold)), ""]
        if self.ranks_changed:
            lines += ["GPU chip ranks changed.", ""]
        if self.skipped:
            lines += [
                "CPUs left out: " + ", ".join(f"{reason} {count}" for reason, count in self.skipped.most_common()),
                "",
            ]
        if self.failed:
            lines += ["Sources not read this time:", *(f"- {url}" for url in self.failed), ""]
        return "\n".join(lines).rstrip() + "\n"


class HardwareUpdater:
    """Adds to the database the candidates it doesn't have yet, once NVIDIA accepts them.

    A rejected candidate is not remembered: NVIDIA may learn it later, and it is checked again on the next update."""

    _HTTP_NOT_FOUND: int = 404
    # Hardware NVIDIA accepts: only the component under check varies.
    _CPU_NAME: str = "13th Gen Intel(R) Core(TM) i9-13900HX"
    _GPU: Gpu = Gpu(name="NVIDIA GeForce RTX 4060 Laptop GPU", device_id="28e0")
    _MEMORY_GB: int = 16
    _OS_VERSION: str = "10.0"
    # Game whose preset request tells whether NVIDIA knows a GPU's device id.
    _CHECK_GAME: str = "baldurs_gate_3"
    _NVIDIA_REJECTED: str = "rejected by NVIDIA"

    def __init__(self, *, db: HardwareDbWriter, api: OpsApi, added: str) -> None:
        """
        Prepare an update.

        :param db: database to add to
        :param api: NVIDIA API client
        :param added: date of the update, YYYY-MM-DD
        """
        self._db: HardwareDbWriter = db
        self._api: OpsApi = api
        self._added: str = added
        self.report: UpdateReport = UpdateReport()

    def update_cpus(self, *, candidates: set[Cpu]) -> None:
        """
        Add the candidate CPUs that belong in the list, aren't in the database yet and NVIDIA accepts.

        :param candidates: CPUs of the sources
        :return: None
        """
        known: set[str] = self._db.cpu_names()
        new: list[Cpu] = []
        for cpu in sorted(candidates, key=lambda item: item.name):
            if cpu.name in known:
                continue
            reason: str | None = CpuRules.rejection(name=cpu.name)
            if reason is None and not self._cpu_accepted(name=cpu.name):
                reason = self._NVIDIA_REJECTED
            if reason is None:
                new.append(cpu)
                known.add(cpu.name)
            else:
                self.report.skipped[reason] += 1
        self._db.add_cpus(cpus=new, added=self._added)
        self.report.cpus += new
        logger.info("CPUs: {} candidates, {} added, left out: {}", len(candidates), len(new), dict(self.report.skipped))

    def update_gpus(self, *, pci_ids: PciIds) -> None:
        """
        Refresh the chip ranks and add new GeForce GPUs, each with the first device id NVIDIA accepts.

        :param pci_ids: the PCI ID database
        :return: None
        """
        self.report.ranks_changed = self._db.replace_ranks(ranks=pci_ids.ranks())
        known: set[str] = self._db.gpu_names()
        new: list[Gpu] = []
        for gpu in pci_ids.geforce():
            if gpu.name not in known and self._gpu_accepted(gpu=gpu):
                new.append(gpu)
                known.add(gpu.name)
        self._db.add_gpus(gpus=new, added=self._added)
        self.report.gpus += new
        logger.info("GPUs: {} added, ranks changed: {}", len(new), self.report.ranks_changed)

    def _cpu_accepted(self, *, name: str) -> bool:
        """
        Ask NVIDIA whether it knows a CPU.

        :param name: CPU name
        :return: True when the compatibility check doesn't reject the CPU
        """
        compatibility: Compatibility = self._api.check_compatibility(
            hardware=self._hardware(cpu_name=name, gpu=self._GPU)
        )
        return compatibility.ok

    def _gpu_accepted(self, *, gpu: Gpu) -> bool:
        """
        Ask NVIDIA whether it passes a GPU in the compatibility check and knows its device id for presets.

        :param gpu: GPU to check
        :return: True when both checks pass
        """
        hardware: Hardware = self._hardware(cpu_name=self._CPU_NAME, gpu=gpu)
        if not self._api.check_compatibility(hardware=hardware).ok:
            return False
        try:
            self._api.game_presets(game_id=self._CHECK_GAME, hardware=hardware)
        except HttpClientError as error:
            if error.status != self._HTTP_NOT_FOUND:
                raise
            return False
        return True

    def _hardware(self, *, cpu_name: str, gpu: Gpu) -> Hardware:
        """
        Build the hardware of a check.

        :param cpu_name: CPU name
        :param gpu: GPU
        :return: hardware sent to NVIDIA
        """
        return Hardware(
            cpu_name=cpu_name,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=self._MEMORY_GB,
            os_version=self._OS_VERSION,
        )
