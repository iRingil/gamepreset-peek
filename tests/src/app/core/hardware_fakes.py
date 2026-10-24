"""Hardware of the system the detection mocks describe, shared by the service and the presenter tests."""

from app.core.models import Gpu, Hardware, HardwareCheck, HardwareState

__all__: tuple[str, ...] = ("DETECTED_CPU", "FakeHardware")

DETECTED_CPU: str = "13th Gen Intel(R) Core(TM) i9-13900HX"


class FakeHardware:
    """Hardware sent to NVIDIA: the detected memory and Windows version with a chosen CPU and GPU."""

    @staticmethod
    def with_gpu(*, gpu: Gpu, cpu_name: str = DETECTED_CPU) -> Hardware:
        """
        Build hardware with a GPU.

        :param gpu: the GPU
        :param cpu_name: the CPU
        :return: hardware
        """
        return Hardware(
            cpu_name=cpu_name,
            gpu_name=gpu.name,
            gpu_device_id=gpu.device_id,
            memory_gb=16,
            os_version="10.0",
        )

    @classmethod
    def ready(cls, *, gpu: Gpu, cpu_name: str = DETECTED_CPU) -> HardwareCheck:
        """
        Build a READY check result.

        :param gpu: the GPU in use
        :param cpu_name: the CPU in use
        :return: check result
        """
        return HardwareCheck(state=HardwareState.READY, hardware=cls.with_gpu(gpu=gpu, cpu_name=cpu_name))
