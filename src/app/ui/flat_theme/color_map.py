"""The colors of one mode: the defaults with the app's overrides, resolved by color id and state."""

import copy
from collections.abc import Mapping
from typing import Self

from .color import Color
from .default_colors import ColorTree

__all__: tuple[str, ...] = ("ColorMap",)


class ColorMap:
    """Resolves a color id and an optional state, e.g. "primary" and "list.selectionBackground", to a color."""

    def __init__(self, *, tree: ColorTree) -> None:
        """
        Keep the colors of a mode.

        :param tree: colors by id, as in the defaults
        """
        self._tree: ColorTree = tree

    @classmethod
    def overridden(cls, *, defaults: ColorTree, overrides: Mapping[str, str]) -> Self:
        """
        Take the default colors with some replaced.

        :param defaults: default colors by id
        :param overrides: hex colors by "id" (a plain color or a base) or by "id>state"
        :return: the colors
        """
        tree: ColorTree = copy.deepcopy(defaults)
        for key, value in overrides.items():
            Color.from_hex(text=value)
            color_id, _, state = key.partition(">")
            current: str | dict[str, str | dict[str, float]] | None = tree.get(color_id)
            if isinstance(current, dict) and (state or "base") in current:
                current[state or "base"] = value
            elif isinstance(current, str) and not state:
                tree[color_id] = value
            else:
                raise KeyError(f"No color {key!r} to override")
        return cls(tree=tree)

    def color(self, *, color_id: str, state: str | None = None) -> Color:
        """
        Get a color; a plain color has no states and is the same in every one.

        :param color_id: color id, e.g. "primary"
        :param state: state of the color, e.g. "disabled"; None for the base
        :return: the color
        """
        value: str | dict[str, str | dict[str, float]] = self._tree[color_id]
        if isinstance(value, str):
            return Color.from_hex(text=value)
        base: Color = Color.from_hex(text=str(value["base"]))
        if state is None:
            return base
        change: str | dict[str, float] = value[state]
        if isinstance(change, str):
            return Color.from_hex(text=change)
        return self._changed(color=base, change=change)

    @staticmethod
    def _changed(*, color: Color, change: Mapping[str, float]) -> Color:
        """
        Apply a state's changes to its base color, in the order the defaults are tuned for.

        :param color: base color
        :param change: factors by "transparent", "darken" and "lighten"
        :return: the changed color
        """
        if "transparent" in change:
            color = color.transparent(factor=change["transparent"])
        if "darken" in change:
            color = color.darken(factor=change["darken"])
        if "lighten" in change:
            color = color.lighten(factor=change["lighten"])
        return color
