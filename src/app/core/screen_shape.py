"""Aspect ratios of screen resolutions."""

from math import gcd

from app.config import ASPECT_TOLERANCE

__all__: tuple[str, ...] = ("ScreenShape",)


class ScreenShape:
    """Compares resolutions by their width-to-height ratio and names the ratio the way screens are sold, e.g. "16:9"."""

    # Ratios screens are sold by; ultrawide 3440x1440 and 2560x1080 are both sold as 21:9.
    _NAMED: tuple[tuple[int, int], ...] = ((4, 3), (5, 4), (16, 9), (16, 10), (21, 9), (32, 9), (32, 10))

    @classmethod
    def fits(cls, *, resolution: str, screen: str) -> bool:
        """
        Tell whether a resolution has the shape of the screen, so it fills it without black bars or stretching.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1200"
        :param screen: resolution of the screen, e.g. "2560x1600"
        :return: True when the ratios match within the tolerance, False also for a malformed resolution
        """
        ratio: float | None = cls._ratio(resolution=resolution)
        target: float | None = cls._ratio(resolution=screen)
        return ratio is not None and target is not None and cls._close(ratio=ratio, other=target)

    @classmethod
    def name(cls, *, resolution: str) -> str:
        """
        Name the aspect ratio of a resolution.

        :param resolution: resolution as NVIDIA writes it, e.g. "2560x1600"
        :return: the ratio, e.g. "16:10"; the reduced fraction for an uncommon one, "" for a malformed resolution
        """
        size: tuple[int, int] | None = cls._size(resolution=resolution)
        if size is None:
            return ""
        width, height = size
        for named_width, named_height in cls._NAMED:
            if cls._close(ratio=width / height, other=named_width / named_height):
                return f"{named_width}:{named_height}"
        divisor: int = gcd(width, height)
        return f"{width // divisor}:{height // divisor}"

    @classmethod
    def _ratio(cls, *, resolution: str) -> float | None:
        """
        Get the width-to-height ratio of a resolution.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1080"
        :return: the ratio, None for a malformed resolution
        """
        size: tuple[int, int] | None = cls._size(resolution=resolution)
        return None if size is None else size[0] / size[1]

    @staticmethod
    def _size(*, resolution: str) -> tuple[int, int] | None:
        """
        Split a resolution into its width and height.

        :param resolution: resolution as NVIDIA writes it, e.g. "1920x1080"
        :return: width and height, None unless both are positive whole numbers
        """
        width, _, height = resolution.partition("x")
        if not (width.isdigit() and height.isdigit()) or int(width) == 0 or int(height) == 0:
            return None
        return int(width), int(height)

    @staticmethod
    def _close(*, ratio: float, other: float) -> bool:
        """
        Compare two ratios within the tolerance.

        :param ratio: a width-to-height ratio
        :param other: the ratio to compare with
        :return: True when they differ by at most the tolerance share
        """
        return abs(ratio / other - 1) <= ASPECT_TOLERANCE
