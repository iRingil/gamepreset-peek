"""Keyboard focus by the mouse only: Tab reaches nothing, so no focus frame shows up on its own."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractScrollArea, QAbstractSpinBox, QLineEdit, QWidget

__all__: tuple[str, ...] = ("MouseFocus",)


class MouseFocus:
    """Takes Tab out of the focus of a window: a game app is driven by the mouse, as other desktop apps are.

    A click still focuses where keys go on, a text field or a list; buttons, check boxes, combo boxes and tabs take no
    focus, so none of them keeps a focus frame. With nothing reachable by Tab, a window opens with nothing focused."""

    # Widgets that keep taking focus by a click, where it took one: typing and arrow keys go there.
    _KEYED: tuple[type[QWidget], ...] = (QLineEdit, QAbstractSpinBox, QAbstractScrollArea)

    @classmethod
    def apply(cls, *, root: QWidget) -> None:
        """
        Set the focus policy of a widget and of everything in it to click focus or none.

        :param root: the window or widget, built with all its children
        :return: None
        """
        widgets: list[QWidget] = [root, *root.findChildren(QWidget)]
        policies: list[Qt.FocusPolicy] = [
            (
                Qt.FocusPolicy.ClickFocus
                if isinstance(widget, cls._KEYED) and widget.focusPolicy().value & Qt.FocusPolicy.ClickFocus.value
                else Qt.FocusPolicy.NoFocus
            )
            for widget in widgets
        ]
        # A policy set on a widget with a focus proxy, e.g. a list's viewport, also lands on the proxy: those go first.
        for widget, policy in sorted(zip(widgets, policies), key=lambda pair: pair[0].focusProxy() is None):
            widget.setFocusPolicy(policy)
