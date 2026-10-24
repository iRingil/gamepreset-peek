"""The resolution choice: the detected screen, then the game's resolutions with the marks they call for."""

from app.core.models import GamePresets, HardwareSetup
from app.core.screen_shape import ScreenShape
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.views import ChoiceGroup, ChoiceView

__all__: tuple[str, ...] = ("ResolutionChoice",)


class ResolutionChoice:
    """Builds the resolution choice: the detected screen above the game's resolutions, the largest first.

    Before a game's presets arrive, the bundled resolutions stand in for the game's. Resolutions of the screen's shape
    are marked with its ratio, ones too demanding for the hardware with the warning sign."""

    @classmethod
    def build(
        cls, *, setup: HardwareSetup, presets: GamePresets | None, in_use: str | None, translator: Translator
    ) -> ChoiceView:
        """
        Build the choice with the resolution in use selected.

        :param setup: detected screen and bundled resolutions
        :param presets: presets of the game, None while they are not known
        :param in_use: resolution in use
        :param translator: translator of the hints
        :return: the choice
        """
        detected: tuple[str, ...] = setup.detected_resolutions
        others: tuple[str, ...] = setup.resolutions
        if presets is not None:
            others = tuple(item for item in presets.resolution_names if item not in detected)
        offered: tuple[str, ...] = detected + others
        screen: str | None = setup.system.resolution
        ratio: str = "" if screen is None else ScreenShape.name(resolution=screen)
        demanding: frozenset[str] = cls._demanding(presets=presets)
        warned: frozenset[int] = frozenset(position for position, item in enumerate(offered) if item in demanding)
        return ChoiceView(
            detected=detected,
            groups=(ChoiceGroup(title="", items=others),),
            selected=offered.index(in_use) if in_use in offered else None,
            fitting=frozenset(
                len(detected) + row
                for row, item in enumerate(others)
                if screen is not None and ScreenShape.fits(resolution=item, screen=screen)
            ),
            fit_mark=ratio,
            fit_hint=translator.text(item=UiText.FITS_SCREEN, ratio=ratio) if ratio else "",
            warned=warned,
            warn_hint=translator.text(item=UiText.RESOLUTION_BELOW_MIN_SPEC) if warned else "",
        )

    @staticmethod
    def _demanding(*, presets: GamePresets | None) -> frozenset[str]:
        """
        List the resolutions of the game NVIDIA marks as too demanding for the hardware.

        :param presets: presets of the game, None while they are not known
        :return: the resolutions, none while the game's presets are not known
        """
        if presets is None:
            return frozenset()
        return frozenset(item.resolution for item in presets.resolutions if item.below_min_spec)
