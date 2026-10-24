"""Tests of the aspect ratios of screen resolutions."""

import pytest

from app.core.screen_shape import ScreenShape

__all__: tuple = ()


class TestScreenShape:
    """Tests of ScreenShape."""

    @pytest.mark.parametrize(
        argnames=("resolution", "screen", "expected"),
        argvalues=[
            ("1920x1200", "2560x1600", True),
            ("3840x2400", "2560x1600", True),
            ("1920x1080", "2560x1600", False),
            ("1366x768", "1920x1080", True),
            ("2560x1080", "3440x1440", True),
            ("1280x1024", "1024x768", False),
            ("wide", "2560x1600", False),
            ("1920x0", "2560x1600", False),
        ],
        ids=["16:10", "16:10 larger", "16:9 on 16:10", "rounded 16:9", "both 21:9", "5:4 on 4:3", "malformed", "zero"],
    )
    def test_fits(self, resolution: str, screen: str, expected: bool) -> None:
        """
        Matches resolutions of the screen's shape within the tolerance, nothing malformed.

        :param resolution: resolution compared
        :param screen: resolution of the screen
        :param expected: whether it fits
        :return: None
        """
        # Arrange & Act
        fits: bool = ScreenShape.fits(resolution=resolution, screen=screen)
        # Assert
        assert fits is expected

    @pytest.mark.parametrize(
        argnames=("resolution", "expected"),
        argvalues=[
            ("2560x1600", "16:10"),
            ("1366x768", "16:9"),
            ("3440x1440", "21:9"),
            ("1280x1024", "5:4"),
            ("1280x768", "5:3"),
            ("x", ""),
        ],
        ids=["16:10", "rounded 16:9", "ultrawide", "5:4", "uncommon", "malformed"],
    )
    def test_name(self, resolution: str, expected: str) -> None:
        """
        Names a ratio the way screens are sold, an uncommon one as a reduced fraction.

        :param resolution: resolution named
        :param expected: the name
        :return: None
        """
        # Arrange & Act
        name: str = ScreenShape.name(resolution=resolution)
        # Assert
        assert name == expected
