"""Tests of app.ui.flat_theme.color."""

import pytest

from app.ui.flat_theme.color import Color

__all__: tuple = ()


class TestColor:
    """Tests of Color."""

    @pytest.mark.parametrize(
        argnames=("text", "expected"),
        argvalues=[
            ("#202124", (32, 33, 36, 1.0)),
            ("8ab4f766", (138, 180, 247, 0.4)),
            ("#FFFFFF", (255, 255, 255, 1.0)),
        ],
        ids=["opaque", "with alpha, no hash", "upper case"],
    )
    def test_from_hex(self, text: str, expected: tuple[int, int, int, float]) -> None:
        """
        Parses #RRGGBB and #RRGGBBAA, the hash optional, the alpha as a fraction.

        :param text: hex color
        :param expected: red, green, blue and alpha
        :return: None
        """
        # Arrange & Act
        color: Color = Color.from_hex(text=text)
        # Assert
        assert (color.red, color.green, color.blue, color.alpha) == expected

    @pytest.mark.parametrize(
        argnames="text", argvalues=["#fff", "#2021", "#20212g", ""], ids=["short", "4", "g", "empty"]
    )
    def test_from_hex_malformed(self, text: str) -> None:
        """
        Refuses colors in any other notation.

        :param text: malformed color
        :return: None
        """
        # Act & Assert
        with pytest.raises(expected_exception=ValueError, match="Not a #RRGGBB"):
            Color.from_hex(text=text)

    def test_from_rgba_clamps(self) -> None:
        """
        Keeps channels within their ranges and rounds the alpha to thousandths.

        :return: None
        """
        # Arrange & Act
        color: Color = Color.from_rgba(red=300, green=-5, blue=10, alpha=0.12345)
        # Assert
        assert (color.red, color.green, color.blue, color.alpha) == (255, 0, 10, 0.123)

    @pytest.mark.parametrize(
        argnames=("text", "qss", "hex_digits", "alpha_byte"),
        argvalues=[
            ("#202124", "rgba(32, 33, 36, 1.000)", "202124", 255),
            ("#8ab4f766", "rgba(138, 180, 247, 0.400)", "8ab4f766", 102),
        ],
        ids=["opaque", "transparent"],
    )
    def test_forms(self, text: str, qss: str, hex_digits: str, alpha_byte: int) -> None:
        """
        Writes a color for style sheets, for file names (alpha only when not opaque) and for Qt.

        :param text: hex color
        :param qss: expected style sheet value
        :param hex_digits: expected hex digits
        :param alpha_byte: expected alpha for Qt
        :return: None
        """
        # Arrange & Act
        color: Color = Color.from_hex(text=text)
        # Assert
        assert (color.qss, color.hex, color.alpha_byte) == (qss, hex_digits, alpha_byte)

    @pytest.mark.parametrize(
        argnames=("text", "expected"),
        argvalues=[
            ("#202124", 'fill="#202124"'),
            ("#20212466", 'fill="rgb(32,33,36)" fill-opacity="0.4"'),
        ],
        ids=["opaque", "transparent"],
    )
    def test_svg_fill(self, text: str, expected: str) -> None:
        """
        Gives SVG a hex fill, or a fill in rgb() with a separate opacity: Qt's SVG renderer takes no hex alpha.

        :param text: hex color
        :param expected: fill attributes
        :return: None
        """
        # Arrange & Act
        fill: str = Color.from_hex(text=text).svg_fill
        # Assert
        assert fill == expected

    def test_darken_rounds_half_lightness(self) -> None:
        """
        Halves a lightness of 0.133 to 0.066, as the defaults were tuned with, not to 0.067.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#202124")
        # Act
        darker: Color = color.darken(factor=0.5)
        # Assert
        assert (darker.red, darker.green, darker.blue, darker.hsla.lightness) == (16, 16, 18, 0.066)

    def test_lighten(self) -> None:
        """
        Raises the lightness by a share of itself and keeps the alpha.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#20212480")
        # Act
        lighter: Color = color.lighten(factor=0.3)
        # Assert
        assert lighter.qss == "rgba(42, 43, 47, 0.502)"

    def test_lighten_after_darken(self) -> None:
        """
        Lightens from the HSLA form the darkening left, not from its rounded RGB channels.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#e4e7eb")
        # Act
        changed: Color = color.darken(factor=0.3).lighten(factor=0.2)
        # Assert
        assert changed.qss == "rgba(186, 193, 204, 1.000)"

    def test_lighten_caps_lightness(self) -> None:
        """
        Stops at white instead of going past it.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#f8f9fa")
        # Act
        lighter: Color = color.lighten(factor=0.5)
        # Assert
        assert (lighter.red, lighter.green, lighter.blue) == (255, 255, 255)

    def test_transparent(self) -> None:
        """
        Scales the alpha and keeps the channels.

        :return: None
        """
        # Arrange
        color: Color = Color.from_hex(text="#e4e7eb")
        # Act
        faded: Color = color.transparent(factor=0.4)
        # Assert
        assert faded.qss == "rgba(228, 231, 235, 0.400)"
