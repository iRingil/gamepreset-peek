"""Colors of the theme: hex parsing, lightening, darkening and transparency, and their QSS, file and SVG forms."""

import colorsys
import math
import re
from dataclasses import dataclass
from typing import ClassVar, Self

__all__: tuple[str, ...] = ("Color",)

# Every channel fraction is rounded to thousandths, through an integer as the defaults were tuned with.
_SCALE: int = 1000


@dataclass(frozen=True, slots=True)
class _Hsla:
    """Hue (degrees), saturation, lightness and alpha (0..1) of a color."""

    hue: int
    saturation: float
    lightness: float
    alpha: float

    @classmethod
    def clamped(cls, *, hue: int, saturation: float, lightness: float, alpha: float) -> Self:
        """
        Make a color from channels kept within their ranges and rounded.

        :param hue: hue in degrees
        :param saturation: saturation, 0..1
        :param lightness: lightness, 0..1
        :param alpha: alpha, 0..1
        :return: the color
        """
        return cls(
            hue=max(min(360, hue), 0),
            saturation=cls.fraction(value=saturation),
            lightness=cls.fraction(value=lightness),
            alpha=cls.fraction(value=alpha),
        )

    @staticmethod
    def fraction(*, value: float) -> float:
        """
        Keep a channel fraction within 0..1, rounded to thousandths.

        :param value: the fraction
        :return: the kept fraction
        """
        return round(max(min(1.0, value), 0.0) * _SCALE) / _SCALE


@dataclass(frozen=True, slots=True)
class Color:
    """An RGBA color with the HSLA form it was derived in, which the next lightening or darkening starts from."""

    red: int
    green: int
    blue: int
    alpha: float
    hsla: _Hsla

    _HEX: ClassVar[re.Pattern[str]] = re.compile(r"#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")

    @classmethod
    def from_hex(cls, *, text: str) -> Self:
        """
        Parse a color written as #RRGGBB or #RRGGBBAA.

        :param text: the color
        :return: the color
        """
        if not cls._HEX.fullmatch(text):
            raise ValueError(f"Not a #RRGGBB or #RRGGBBAA color: {text!r}")
        channels: bytes = bytes.fromhex(text.lstrip("#"))
        return cls.from_rgba(
            red=channels[0], green=channels[1], blue=channels[2], alpha=channels[3] / 255 if len(channels) == 4 else 1
        )

    @classmethod
    def from_rgba(cls, *, red: int, green: int, blue: int, alpha: float) -> Self:
        """
        Make a color from RGBA channels, kept within their ranges.

        :param red: red, 0..255
        :param green: green, 0..255
        :param blue: blue, 0..255
        :param alpha: alpha, 0..1
        :return: the color
        """
        red, green, blue = (min(255, max(0, channel)) for channel in (red, green, blue))
        alpha = _Hsla.fraction(value=alpha)
        hue, lightness, saturation = colorsys.rgb_to_hls(r=red / 255, g=green / 255, b=blue / 255)
        hsla: _Hsla = _Hsla.clamped(hue=int(hue * 360), saturation=saturation, lightness=lightness, alpha=alpha)
        return cls(red=red, green=green, blue=blue, alpha=alpha, hsla=hsla)

    @property
    def qss(self) -> str:
        """
        Get the color as a style sheet value.

        :return: e.g. "rgba(32, 33, 36, 1.000)"
        """
        return f"rgba({self.red}, {self.green}, {self.blue}, {self.alpha:.3f})"

    @property
    def hex(self) -> str:
        """
        Get the color as hex digits, alpha only when it isn't opaque.

        :return: e.g. "202124" or "8ab4f766"
        """
        alpha: str = "" if self.alpha == 1 else f"{math.floor(self.alpha * 255):02x}"
        return f"{self.red:02x}{self.green:02x}{self.blue:02x}{alpha}"

    @property
    def alpha_byte(self) -> int:
        """
        Get the alpha as Qt takes it.

        :return: 0..255
        """
        return math.floor(self.alpha * 255)

    @property
    def svg_fill(self) -> str:
        """
        Get the fill attributes of an SVG drawn in this color: Qt's SVG Tiny renderer takes no alpha in a hex color.

        :return: e.g. 'fill="#202124"' or 'fill="rgb(32,33,36)" fill-opacity="0.4"'
        """
        if self.alpha == 1:
            return f'fill="#{self.hex}"'
        return f'fill="rgb({self.red},{self.green},{self.blue})" fill-opacity="{self.alpha}"'

    def lighten(self, *, factor: float) -> Self:
        """
        Raise the lightness by a share of itself.

        :param factor: share, e.g. 0.2 for 20 % lighter
        :return: the lighter color
        """
        return self._of_hsla(hsla=self._with_lightness(lightness=self.hsla.lightness + self.hsla.lightness * factor))

    def darken(self, *, factor: float) -> Self:
        """
        Lower the lightness by a share of itself.

        :param factor: share, e.g. 0.2 for 20 % darker
        :return: the darker color
        """
        return self._of_hsla(hsla=self._with_lightness(lightness=self.hsla.lightness - self.hsla.lightness * factor))

    def transparent(self, *, factor: float) -> Self:
        """
        Scale the alpha.

        :param factor: share of the alpha kept, e.g. 0.4
        :return: the more transparent color
        """
        return self.from_rgba(red=self.red, green=self.green, blue=self.blue, alpha=self.alpha * factor)

    def _with_lightness(self, *, lightness: float) -> _Hsla:
        """
        Get the HSLA form of this color with another lightness.

        :param lightness: the new lightness
        :return: the HSLA form
        """
        return _Hsla.clamped(
            hue=self.hsla.hue, saturation=self.hsla.saturation, lightness=lightness, alpha=self.hsla.alpha
        )

    @classmethod
    def _of_hsla(cls, *, hsla: _Hsla) -> Self:
        """
        Make a color from its HSLA form, which it keeps.

        :param hsla: the HSLA form
        :return: the color
        """
        red, green, blue = colorsys.hls_to_rgb(h=hsla.hue / 360, l=hsla.lightness, s=hsla.saturation)
        return cls(red=round(red * 255), green=round(green * 255), blue=round(blue * 255), alpha=hsla.alpha, hsla=hsla)
