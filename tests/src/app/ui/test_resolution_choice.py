"""Tests of the resolution choice."""

from pathlib import Path

from app.core.models import (
    GamePresets,
    HardwareChoice,
    HardwareSetup,
    RemoteFile,
    ResolutionPreset,
    SystemHardware,
)
from app.i18n.translator import Translator
from app.ui.resolution_choice import ResolutionChoice
from app.ui.views import ChoiceGroup, ChoiceView

__all__: tuple = ()

_SETUP: HardwareSetup = HardwareSetup(
    system=SystemHardware(cpu_name=None, gpus=(), memory_gb=16, os_version="10.0", resolution="2560x1600"),
    amd_cpus=(),
    intel_cpus=(),
    gpus=(),
    resolutions=("3840x2160", "1920x1200"),
    choice=HardwareChoice(cpu_name=None, gpu=None),
    resolution="2560x1600",
)


class TestResolutionChoice:
    """Tests of ResolutionChoice.build."""

    def test_game_resolutions_marked(self, locale_dir: Path) -> None:
        """
        Puts the game's resolutions under the screen, marking the screen's shape and the too demanding ones.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        presets: GamePresets = GamePresets(
            profile="regular",
            version="1",
            presets_file=RemoteFile(url="https://cdn.example.test/pops", sha256="00", size=1),
            resolutions=(
                ResolutionPreset(resolution="1920x1200", preset_index=2, rate=40, below_min_spec=False),
                ResolutionPreset(resolution="2560x1600", preset_index=1, rate=40, below_min_spec=True),
                ResolutionPreset(resolution="3840x2400", preset_index=1, rate=40, below_min_spec=True),
            ),
        )
        # Act
        choice: ChoiceView = ResolutionChoice.build(
            setup=_SETUP,
            presets=presets,
            in_use="1920x1200",
            translator=Translator(language="en", locale_dir=locale_dir),
        )
        # Assert
        assert (choice.detected, choice.groups, choice.selected) == (
            ("2560x1600",),
            (ChoiceGroup(title="", items=("3840x2400", "1920x1200")),),
            2,
        )
        assert (choice.fitting, choice.fit_mark, choice.warned) == (frozenset({1, 2}), "16:10", frozenset({0, 1}))
        assert choice.warn_hint.startswith("Too demanding")

    def test_bundled_without_marks(self, locale_dir: Path) -> None:
        """
        Offers the bundled resolutions, none warned and no hints of the screen, without presets or a detected screen.

        :param locale_dir: compiled catalogs
        :return: None
        """
        # Arrange
        setup: HardwareSetup = HardwareSetup(
            system=SystemHardware(cpu_name=None, gpus=(), memory_gb=16, os_version="10.0", resolution=None),
            amd_cpus=(),
            intel_cpus=(),
            gpus=(),
            resolutions=_SETUP.resolutions,
            choice=_SETUP.choice,
            resolution="2560x1440",
        )
        # Act
        choice: ChoiceView = ResolutionChoice.build(
            setup=setup, presets=None, in_use="2560x1440", translator=Translator(language="en", locale_dir=locale_dir)
        )
        # Assert
        assert choice == ChoiceView(
            detected=(), groups=(ChoiceGroup(title="", items=("3840x2160", "1920x1200")),), selected=None
        )
