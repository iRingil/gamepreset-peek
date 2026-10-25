"""Tests of app.ui.flat_theme.color_map."""

import pytest

from app.ui.flat_theme.color_map import ColorMap
from app.ui.flat_theme.default_colors import ColorTree

__all__: tuple = ()


class TestColorMap:
    """Tests of ColorMap."""

    @pytest.fixture(name="defaults")
    def _defaults(self) -> ColorTree:
        """
        Give a small color tree: a plain color and one with a hex state and a changed state.

        :return: colors by id
        """
        return {
            "border": "#3f4042",
            "primary": {"base": "#8ab4f7", "hover": "#112233", "faded": {"transparent": 0.5, "darken": 0.1}},
        }

    @pytest.mark.parametrize(
        argnames=("color_id", "state", "expected"),
        argvalues=[
            ("border", None, "rgba(63, 64, 66, 1.000)"),
            ("border", "anything", "rgba(63, 64, 66, 1.000)"),
            ("primary", None, "rgba(138, 180, 247, 1.000)"),
            ("primary", "hover", "rgba(17, 34, 51, 1.000)"),
            ("primary", "faded", "rgba(102, 159, 245, 0.500)"),
        ],
        ids=["plain", "plain in any state", "base", "hex state", "changed state"],
    )
    def test_color(self, defaults: ColorTree, color_id: str, state: str | None, expected: str) -> None:
        """
        Resolves a color id and a state; a plain color is the same in every state.

        :param defaults: sample colors
        :param color_id: color id
        :param state: state, None for the base
        :param expected: expected style sheet value
        :return: None
        """
        # Arrange
        colors: ColorMap = ColorMap(tree=defaults)
        # Act
        value: str = colors.color(color_id=color_id, state=state).qss
        # Assert
        assert value == expected

    def test_color_lighten(self) -> None:
        """
        Applies a lightening state.

        :return: None
        """
        # Arrange
        colors: ColorMap = ColorMap(tree={"background": {"base": "#202124", "popup": {"lighten": 0.3}}})
        # Act
        value: str = colors.color(color_id="background", state="popup").qss
        # Assert
        assert value == "rgba(42, 43, 47, 1.000)"

    def test_overridden(self, defaults: ColorTree) -> None:
        """
        Replaces a plain color, a base and a state, and leaves the defaults as they were.

        :param defaults: sample colors
        :return: None
        """
        # Arrange
        overrides: dict[str, str] = {"border": "#000000", "primary": "#ffffff", "primary>hover": "#010203"}
        # Act
        colors: ColorMap = ColorMap.overridden(defaults=defaults, overrides=overrides)
        # Assert
        assert colors.color(color_id="border").hex == "000000"
        assert colors.color(color_id="primary").hex == "ffffff"
        assert colors.color(color_id="primary", state="hover").hex == "010203"
        assert defaults["border"] == "#3f4042"
        assert defaults["primary"]["hover"] == "#112233"  # type: ignore[index]

    @pytest.mark.parametrize(
        argnames="key",
        argvalues=["missing", "border>hover", "primary>missing", "missing>hover"],
        ids=["unknown id", "state of a plain color", "unknown state", "state of an unknown id"],
    )
    def test_overridden_unknown(self, defaults: ColorTree, key: str) -> None:
        """
        Refuses to override a color the defaults don't have.

        :param defaults: sample colors
        :param key: override key
        :return: None
        """
        # Act & Assert
        with pytest.raises(expected_exception=KeyError, match="No color"):
            ColorMap.overridden(defaults=defaults, overrides={key: "#000000"})

    def test_overridden_malformed(self, defaults: ColorTree) -> None:
        """
        Refuses a malformed override at once, not at its first use.

        :param defaults: sample colors
        :return: None
        """
        # Act & Assert
        with pytest.raises(expected_exception=ValueError, match="Not a #RRGGBB"):
            ColorMap.overridden(defaults=defaults, overrides={"border": "black"})
