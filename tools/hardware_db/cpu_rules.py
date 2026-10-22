"""Which CPU names go into the list: desktop and laptop CPUs of the Windows 10 era."""

import re

__all__: tuple[str, ...] = ("CpuRules",)


class CpuRules:
    """Decides on a CPU name as the hardware reports it, e.g. "13th Gen Intel(R) Core(TM) i9-13900HX".

    Dropped: servers, engineering samples, virtual machine CPUs, embedded parts and CPUs older than Intel Core 6th
    gen (Skylake, 2015) or AMD Zen (2017). Pentium and Celeron stay from the same years on.

    A name the rules don't recognize is kept: NVIDIA still has to accept it."""

    SERVER: str = "server"
    SAMPLE: str = "engineering sample"
    VIRTUAL: str = "virtual machine"
    EMBEDDED: str = "embedded"
    OLD: str = "old"

    _MIN_INTEL_GENERATION: int = 6
    # Generation given to Core Ultra, Core 3/5/7 and the 12th-14th gen names: any modern one will do.
    _MODERN_GENERATION: int = 12
    _SERVER_NAME: re.Pattern[str] = re.compile(pattern=r"(?i)xeon|epyc|opteron")
    _SAMPLE_NAME: re.Pattern[str] = re.compile(
        pattern=r"Genuine Intel|Eng Sample|\b0000\b|^Intel\(R\) Core\(TM\) CPU\b|\bCC150\b|#"
    )
    _VIRTUAL_NAME: re.Pattern[str] = re.compile(
        pattern=r"Intel Core Processor \(|KVM|QEMU|Virtual|Nehalem|Westmere|Quad-Core Processor \(up to"
    )
    _EMBEDDED_NAME: re.Pattern[str] = re.compile(pattern=r"(?i)embedded|\bRX-\d|\bGX-\d|\bG-T\d")
    # Intel embedded suffixes: i9-13900E, i7-13700TE, i5-6440EQ, i7-1185G7E.
    _INTEL_EMBEDDED_NAME: re.Pattern[str] = re.compile(pattern=r"\d{3,5}(E|TE|EQ|G\dE)\b")
    _AMD_ZEN_NAME: re.Pattern[str] = re.compile(
        pattern=r"Ryzen|Athlon (Silver|Gold|PRO)|Athlon \d{3,4}[A-Z]|AMD \d{4}[a-zA-Z]|AMD [34]\d00S\b"
    )
    _INTEL_OLD_NAME: re.Pattern[str] = re.compile(
        pattern=r"Core\(TM\)2|Core2|Core\(TM\) (Duo|Solo)|Atom|Core\(TM\) i[3579] CPU"
    )
    _INTEL_MODERN_NAME: re.Pattern[str] = re.compile(
        pattern=r"1[2-4]th Gen|Core\(TM\) Ultra|Core Ultra|Core\(TM\) [357] N?\d{3}|i3-N\d{3}|Processor U\d{3}"
    )
    # Y-series numbers: "m3-6Y30", "i5-7Y54", "M-5Y10c", "Processor 5Y70".
    _INTEL_Y_NUMBER: re.Pattern[str] = re.compile(pattern=r"(?:\b(?:i[357]|m[357]|M)-|Processor )(\d)Y\d")
    _INTEL_NUMBER: re.Pattern[str] = re.compile(pattern=r"\b(?:i[3579]|m[357])-(\d{4,5})")
    # Ice Lake and Tiger Lake laptop numbers: "i5-1035G1", "i7-1165G7".
    _INTEL_G_NUMBER: re.Pattern[str] = re.compile(pattern=r"\b(?:i[3579]|m[357])-1[01]\d{2}G\d")
    _INTEL_BUDGET_NAME: re.Pattern[str] = re.compile(pattern=r"Pentium|Celeron|Intel\(R\) N\d|Processor N\d")
    # 2015+ Pentium, Celeron, Intel N (G4400, N4200, J5005, N100); a 2020 G6400 is "Gold", "CPU G6950" is of 2010.
    _INTEL_BUDGET_MODERN_NAME: re.Pattern[str] = re.compile(
        pattern=r"Pentium\(R\) (Gold|Silver)|Pentium (Gold|Silver)"
        r"|Celeron\(R\) (N[4-6]\d{3}|J[4-6]\d{3}|G[4-6]\d{3}|[67]\d{3}U?)"
        r"|Celeron\(R\) CPU (G39\d\d|3[89]\d{2}U)"
        r"|Pentium\(R\) CPU (G[45]\d{3}|N[45]\d{3}|J[45]\d{3}|[4-6]\d{3}[UY]|6805)"
        r"|Intel\(R\) Pentium\(R\) ([NJ]6\d{3}|8\d{3}U?)"
        r"|Intel\(R\) N\d{2,3}\b|Processor N\d{2,3}\b"
    )

    @classmethod
    def rejection(cls, *, name: str) -> str | None:
        """
        Tell why a CPU doesn't belong in the list.

        :param name: CPU name as the hardware reports it
        :return: one of the reason constants of the class, None when the CPU belongs in the list
        """
        checks: tuple[tuple[re.Pattern[str], str], ...] = (
            (cls._SERVER_NAME, cls.SERVER),
            (cls._SAMPLE_NAME, cls.SAMPLE),
            (cls._VIRTUAL_NAME, cls.VIRTUAL),
            (cls._EMBEDDED_NAME, cls.EMBEDDED),
        )
        reason: str | None = next((reason for pattern, reason in checks if pattern.search(string=name)), None)
        if reason is not None:
            return reason
        if "AMD" in name:
            return None if cls._AMD_ZEN_NAME.search(string=name) else cls.OLD
        return cls._intel_rejection(name=name)

    @classmethod
    def _intel_rejection(cls, *, name: str) -> str | None:
        """
        Tell why an Intel CPU doesn't belong in the list.

        :param name: CPU name
        :return: EMBEDDED, OLD or None
        """
        if cls._INTEL_EMBEDDED_NAME.search(string=name):
            return cls.EMBEDDED
        if cls._INTEL_OLD_NAME.search(string=name):
            return cls.OLD
        generation: int | None = cls._intel_generation(name=name)
        if generation is not None:
            return None if generation >= cls._MIN_INTEL_GENERATION else cls.OLD
        if cls._INTEL_BUDGET_NAME.search(string=name):
            return None if cls._INTEL_BUDGET_MODERN_NAME.search(string=name) else cls.OLD
        return None

    @classmethod
    def _intel_generation(cls, *, name: str) -> int | None:
        """
        Find the generation of an Intel Core CPU from its model number: "i7-8700K" -> 8, "i5-1135G7" -> 11.

        :param name: CPU name
        :return: generation, None for a name without a Core model number
        """
        if cls._INTEL_MODERN_NAME.search(string=name):
            return cls._MODERN_GENERATION
        y_number: re.Match[str] | None = cls._INTEL_Y_NUMBER.search(string=name)
        if y_number is not None:
            return int(y_number.group(1))
        if cls._INTEL_G_NUMBER.search(string=name):
            number: re.Match[str] | None = cls._INTEL_NUMBER.search(string=name)
            return None if number is None else int(number.group(1)[:2])
        number = cls._INTEL_NUMBER.search(string=name)
        if number is None:
            return None
        digits: str = number.group(1)
        return int(digits[:2]) if len(digits) == 5 else int(digits[0])
