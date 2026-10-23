"""Tests of the rules that pick desktop and laptop CPUs of the Windows 10 era."""

import pytest

from hardware_db.cpu_rules import CpuRules

__all__: tuple = ()


class TestRejection:
    """Tests of CpuRules.rejection on real CPU names of the BOINC dumps and InstLatx64."""

    @pytest.mark.parametrize(
        argnames="name",
        argvalues=[
            "13th Gen Intel(R) Core(TM) i9-13900HX",
            "12th Gen Intel(R) Core(TM) i5-12400F",
            "Intel(R) Core(TM) i7-14700K",
            "Intel(R) Core(TM) Ultra 9 285K",
            "Intel(R) Core(TM) 7 150U",
            "Intel(R) Core(TM) i3-N305",
            "Intel(R) Processor U300",
            "Intel(R) Processor 300",
            "11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz",
            "Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz",
            "Intel(R) Core(TM) i9-10900K CPU @ 3.70GHz",
            "Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz",
            "Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz",
            "Intel(R) Core(TM) m3-6Y30 CPU @ 0.90GHz",
            "Intel(R) Core(TM) i5-7Y54 CPU @ 1.20GHz",
            "13th Gen Intel(R) CoreT i5-1350P",
            "Intel(R) Pentium(R) CPU G4560 @ 3.50GHz",
            "Intel(R) Pentium(R) Gold G6400 CPU @ 4.00GHz",
            "Intel(R) Pentium(R) Silver J5005 CPU @ 1.50GHz",
            "Intel(R) Pentium(R) CPU 6805 @ 1.10GHz",
            "Intel(R) Pentium(R) CPU 6405U @ 2.40GHz",
            "Intel(R) Pentium(R) CPU N4200 @ 1.10GHz",
            "Intel(R) Celeron(R) N4020 CPU @ 1.10GHz",
            "Intel(R) Celeron(R) G5905T CPU @ 3.30GHz",
            "Intel(R) N97",
            "AMD Ryzen 7 7800X3D 8-Core Processor",
            "AMD Ryzen 7 7840HS w/ Radeon 780M Graphics",
            "AMD Ryzen AI 9 HX 370 w/ Radeon 890M",
            "AMD Ryzen Threadripper 3970X 32-Core Processor",
            "AMD Ryzen Threadripper PRO 9985WX 64-Cores",
            "AMD Ryzen 5 2600 Six-Core Processor",
            "AMD Athlon Silver 3050U with Radeon Graphics",
            "AMD Athlon 200GE with Radeon Vega Graphics",
            "AMD 3020e with Radeon Graphics",
            "AMD 4700S 8-Core Processor Desktop Kit",
        ],
    )
    def test_kept(self, name: str) -> None:
        """
        Keeps desktop and laptop CPUs of Intel Core 6th gen and AMD Zen on, and the Pentium and Celeron of those years.

        :param name: CPU name
        :return: None
        """
        # Arrange & Act
        reason: str | None = CpuRules.rejection(name=name)
        # Assert
        assert reason is None

    @pytest.mark.parametrize(
        argnames=("name", "expected"),
        argvalues=[
            ("Intel(R) Xeon(R) CPU X5660 @ 2.80GHz", CpuRules.SERVER),
            ("INTEL(R) XEON(R) GOLD 6542Y", CpuRules.SERVER),
            ("AMD EPYC 7302 16-Core Processor", CpuRules.SERVER),
            ("AMD Opteron(tm) Processor 4176 HE", CpuRules.SERVER),
            ("Genuine Intel(R) CPU 0000 @ 2.40GHz", CpuRules.SAMPLE),
            ("AMD Eng Sample: 100-000000053-04_32/20_N", CpuRules.SAMPLE),
            ("Intel(R) Core(TM) i7-5###U CPU @ 2.20GHz", CpuRules.SAMPLE),
            ("Intel(R) CC150 CPU @ 3.50GHz", CpuRules.SAMPLE),
            ("Intel Core Processor (Broadwell, no TSX)", CpuRules.VIRTUAL),
            ("QEMU Virtual CPU version 2.5+", CpuRules.VIRTUAL),
            ("Common KVM processor", CpuRules.VIRTUAL),
            ("Intel Core i7 9xx (Nehalem Class Core i7)", CpuRules.VIRTUAL),
            ("AMD Ryzen Embedded V1605B with Radeon Vega Gfx", CpuRules.EMBEDDED),
            ("AMD Embedded R-Series RX-421BD Radeon R7", CpuRules.EMBEDDED),
            ("13th Gen Intel(R) Core(TM) i9-13900E", CpuRules.EMBEDDED),
            ("13th Gen Intel(R) Core(TM) i7-13700TE", CpuRules.EMBEDDED),
            ("Intel(R) Core(TM) i5-6440EQ CPU @ 2.70GHz", CpuRules.EMBEDDED),
            ("11th Gen Intel(R) Core(TM) i7-1185G7E @ 2.80GHz", CpuRules.EMBEDDED),
            ("Intel(R) Core(TM) i7-4790K CPU @ 4.00GHz", CpuRules.OLD),
            ("Intel(R) Core(TM) i5-5200U CPU @ 2.20GHz", CpuRules.OLD),
            ("Intel(R) Core(TM) M-5Y10c CPU @ 0.80GHz", CpuRules.OLD),
            ("Intel(R) Core(TM) i7 CPU 920 @ 2.67GHz", CpuRules.OLD),
            ("Intel(R) Core(TM)2 Quad CPU Q6600 @ 2.40GHz", CpuRules.OLD),
            ("Intel(R) Core(TM) Duo CPU T2250 @ 1.73GHz", CpuRules.OLD),
            ("Intel(R) Atom(TM) x5-Z8350 CPU @ 1.44GHz", CpuRules.OLD),
            ("Intel(R) Celeron(R) CPU N3060 @ 1.60GHz", CpuRules.OLD),
            ("Intel(R) Pentium(R) CPU G2030 @ 3.00GHz", CpuRules.OLD),
            ("Intel(R) Pentium(R) CPU G6950 @ 2.80GHz", CpuRules.OLD),
            ("Intel(R) Pentium(R) CPU P6200 @ 2.13GHz", CpuRules.OLD),
            ("Pentium(R) Dual-Core CPU E5700 @ 3.00GHz", CpuRules.OLD),
            ("AMD FX(tm)-8350 Eight-Core Processor", CpuRules.OLD),
            ("AMD A8-7410 APU with AMD Radeon R5 Graphics", CpuRules.OLD),
            ("AMD Athlon(tm) II X4 640 Processor", CpuRules.OLD),
            ("AMD Phenom(tm) II X4 940 Processor", CpuRules.OLD),
        ],
    )
    def test_rejected(self, name: str, expected: str) -> None:
        """
        Gives the reason a server, sample, virtual, embedded or old CPU is left out.

        :param name: CPU name
        :param expected: reason
        :return: None
        """
        # Arrange & Act
        reason: str | None = CpuRules.rejection(name=name)
        # Assert
        assert reason == expected
