"""Read-only view of the application log at the bottom of the main window."""

import tkinter as tk
from queue import Empty, Queue
from tkinter import ttk

from app.config import LOG_PANEL_HEIGHT, LOG_PANEL_MAX_LINES, LOG_POLL_MS

__all__: tuple[str, ...] = ("LogPanel",)


class LogPanel:
    """A scrollable text that keeps appending the lines of the log queue, whether it is shown or not."""

    def __init__(self, *, parent: tk.Misc, lines: Queue[str]) -> None:
        """
        Build the panel and start draining the queue.

        :param parent: widget to place the panel in
        :param lines: formatted log lines, filled by the logging sink
        """
        self.frame: ttk.Frame = ttk.Frame(master=parent)
        self._lines: Queue[str] = lines
        self._text: tk.Text = tk.Text(
            master=self.frame,
            height=LOG_PANEL_HEIGHT,
            wrap="none",
            state="disabled",
            font="TkFixedFont",
            padx=6,
            pady=4,
            relief="flat",
            borderwidth=0,
        )
        scrollbar: ttk.Scrollbar = ttk.Scrollbar(master=self.frame, orient="vertical", command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        self._text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.frame.columnconfigure(index=0, weight=1)
        self.frame.rowconfigure(index=0, weight=1)
        self._drain()

    def apply_colors(self, *, background: str, foreground: str) -> None:
        """
        Color the text like the ttk theme: tk.Text is not a ttk widget, so the theme doesn't reach it.

        :param background: background color
        :param foreground: text color
        :return: None
        """
        self._text.configure(
            background=background, foreground=foreground, insertbackground=foreground, selectforeground=background
        )

    def _drain(self) -> None:
        """
        Append the queued lines, keeping the view at the end when it was there, and schedule the next drain.

        :return: None
        """
        lines: list[str] = []
        while True:
            try:
                lines.append(self._lines.get_nowait())
            except Empty:
                break
        if lines:
            at_end: bool = self._text.yview()[1] >= 1.0
            self._text.configure(state="normal")
            self._text.insert(index="end", chars="\n".join(lines) + "\n")
            # The last line is the empty one after the final newline.
            excess: int = int(self._text.index(index="end-1c").split(sep=".", maxsplit=1)[0]) - 1 - LOG_PANEL_MAX_LINES
            if excess > 0:
                self._text.delete(index1="1.0", index2=f"{excess + 1}.0")
            self._text.configure(state="disabled")
            if at_end:
                self._text.see(index="end")
        self.frame.after(ms=LOG_POLL_MS, func=self._drain)
