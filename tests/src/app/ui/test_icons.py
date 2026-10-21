"""Tests of app.ui.icons."""

import tkinter as tk
from contextlib import contextmanager
from typing import Iterator

from app.ui.icons import Icons

__all__: tuple = ()


class TestIcons:
    """Tests of Icons.warning on a hidden Tk root.

    The root is made inside each test: pytest swaps the standard file descriptors between fixture setup and the
    test, and a Tcl interpreter created before the swap fails to read files after it."""

    _SIZE: int = 32

    @staticmethod
    @contextmanager
    def _hidden_root() -> Iterator[tk.Tk]:
        """
        Create a hidden Tk root for the duration of a block.

        :return: context manager giving the root, destroyed at the end
        """
        root: tk.Tk = tk.Tk()
        root.withdraw()
        try:
            yield root
        finally:
            root.destroy()

    def test_warning(self) -> None:
        """
        Draws an amber triangle with a dark rim and exclamation mark on a transparent background.

        :return: None
        """
        with self._hidden_root() as root:
            # Arrange & Act
            image: tk.PhotoImage = Icons.warning(root=root, size=self._SIZE)
            pixels: tuple[object, ...] = (
                (image.width(), image.height()),
                image.transparency_get(x=0, y=0),
                image.get(x=9, y=24),
                image.get(x=16, y=15),
                image.get(x=16, y=28),
            )
        # Assert
        assert pixels == ((32, 32), True, (0xFF, 0xC2, 0x4B), (0x03, 0x18, 0x30), (0x03, 0x18, 0x30))

    def test_gap(self) -> None:
        """
        Leaves a transparent gap left of the sign: the image grows by the gap, the sign moves right by it.

        :return: None
        """
        with self._hidden_root() as root:
            # Arrange & Act
            image: tk.PhotoImage = Icons.warning(root=root, size=self._SIZE, gap=5)
            gap: bool = all(image.transparency_get(x=x, y=y) for x in range(5) for y in range(self._SIZE))
            shown: tuple[object, ...] = ((image.width(), image.height()), image.get(x=5 + 16, y=15))
        # Assert
        assert (gap, shown) == (True, ((37, 32), (0x03, 0x18, 0x30)))
