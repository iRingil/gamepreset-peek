"""Widgets and layout of the main window and of the GPU choice dialog."""

import tkinter as tk
from queue import Queue
from tkinter import ttk
from types import TracebackType
from typing import Callable, Sequence

from loguru import logger

from app.config import APP_TITLE, LANGUAGE_NAMES, THEME_POLL_MS, WINDOW_MIN_SIZE, WINDOW_SIZE
from app.core.models import ThemeMode
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.log_panel import LogPanel
from app.ui.presenter import Presenter, SettingsView
from app.ui.theme import Theme

__all__: tuple[str, ...] = ("MainWindow",)

_PAD: int = 8
_GAMES_WIDTH: int = 300
_RESOLUTIONS_WIDTH: int = 230
_SETTING_WIDTH: int = 320
_VALUE_WIDTH: int = 220
_GPU_LIST_WIDTH: int = 460
_GPU_LIST_HEIGHT: int = 14
_MESSAGE_WRAP: int = 460
_COMBO_WIDTH: int = 12
_CHANGED_TAG: str = "changed"


class _ChoiceList:
    """A single-choice list on a ttk.Treeview, so the theme styles it; item ids are the positions as strings."""

    def __init__(self, *, parent: tk.Misc, width: int, on_select: Callable[[int], None], height: int = 10) -> None:
        """
        Build the list with a vertical scrollbar in a frame of its own.

        :param parent: widget to place the list in
        :param width: width in pixels
        :param on_select: called with the position of the item the user (or fill) selects
        :param height: visible rows when the layout doesn't stretch the list
        """
        self.frame: ttk.Frame = ttk.Frame(master=parent)
        self.frame.columnconfigure(index=0, weight=1)
        self.frame.rowconfigure(index=0, weight=1)
        self.tree: ttk.Treeview = ttk.Treeview(master=self.frame, show="tree", selectmode="browse", height=height)
        self.tree.column(column="#0", width=width, stretch=True)
        scrollbar: ttk.Scrollbar = ttk.Scrollbar(master=self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind(sequence="<<TreeviewSelect>>", func=lambda _: self._selected(on_select=on_select))

    def fill(self, *, items: Sequence[str], selected: int | None = None) -> None:
        """
        Replace the items and select one of them.

        :param items: new items
        :param selected: position to select and scroll to, None for none
        :return: None
        """
        self.tree.delete(*self.tree.get_children())
        for position, item in enumerate(items):
            self.tree.insert(parent="", index="end", iid=str(position), text=item)
        if selected is not None:
            self.tree.selection_set(str(selected))
            self.tree.see(item=str(selected))

    def selection(self) -> int | None:
        """
        Get the selected position.

        :return: position, None when nothing is selected
        """
        selection: tuple[str, ...] = self.tree.selection()
        return int(selection[0]) if selection else None

    def _selected(self, *, on_select: Callable[[int], None]) -> None:
        """
        Pass the selected position on.

        :param on_select: receiver of the position
        :return: None
        """
        position: int | None = self.selection()
        if position is not None:
            on_select(position)


class _GpuDialog:
    """Modal list of GPUs to pick one from."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        parent: tk.Tk,
        translator: Translator,
        message: str,
        names: Sequence[str],
        selected: int | None,
        dark: bool,
    ) -> None:
        """
        Build the dialog.

        :param parent: main window
        :param translator: translator of the UI language
        :param message: why the user has to choose
        :param names: GPU names in list order
        :param selected: position preselected in the list, None for none
        :param dark: True for a dark title bar
        """
        self.choice: int | None = None
        self._window: tk.Toplevel = tk.Toplevel(master=parent)
        self._window.title(string=translator.text(item=UiText.CHOOSE_GPU_TITLE))
        self._window.transient(master=parent)
        frame: ttk.Frame = ttk.Frame(master=self._window, padding=_PAD * 2)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(master=frame, text=message, wraplength=_MESSAGE_WRAP).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, _PAD)
        )
        self._list: _ChoiceList = _ChoiceList(
            parent=frame,
            width=_GPU_LIST_WIDTH,
            height=_GPU_LIST_HEIGHT,
            on_select=self._enable_ok,
        )
        self._list.frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self._ok: ttk.Button = ttk.Button(
            master=frame,
            text=translator.text(item=UiText.OK),
            command=self._accept,
            state="disabled",
            style=Theme.ACCENT,
        )
        self._ok.grid(row=2, column=0, sticky="e", pady=(_PAD, 0), padx=_PAD)
        ttk.Button(master=frame, text=translator.text(item=UiText.CANCEL), command=self._window.destroy).grid(
            row=2, column=1, sticky="e", pady=(_PAD, 0)
        )
        frame.columnconfigure(index=0, weight=1)
        frame.rowconfigure(index=1, weight=1)
        self._window.columnconfigure(index=0, weight=1)
        self._window.rowconfigure(index=0, weight=1)
        self._list.tree.bind(sequence="<Double-Button-1>", func=lambda _: self._accept())
        self._window.bind(sequence="<Return>", func=lambda _: self._accept())
        self._window.bind(sequence="<Escape>", func=lambda _: self._window.destroy())
        self._list.fill(items=names, selected=selected)
        Theme.title_bar(window=self._window, dark=dark)

    def run(self) -> int | None:
        """
        Show the dialog and wait until it is closed.

        :return: position of the chosen GPU, None when the user cancelled
        """
        self._window.grab_set()
        self._list.tree.focus_set()
        self._window.wait_window()
        return self.choice

    def _enable_ok(self, _: int) -> None:
        """
        Allow OK once a GPU is selected.

        :param _: position of the selected GPU
        :return: None
        """
        self._ok.configure(state="normal")

    def _accept(self) -> None:
        """
        Take the selected GPU and close the dialog.

        :return: None
        """
        position: int | None = self._list.selection()
        if position is not None:
            self.choice = position
            self._window.destroy()


class _SettingsPanel:  # pylint: disable=too-many-instance-attributes
    """The game and resolution title, the "Show settings" button, the quality slider and the settings table.

    Rows whose value differs from the recommended preset are drawn in the accent color: that is what the slider
    trades."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        on_show: Callable[[], None],
        on_slider: Callable[[int], None],
        on_optimal: Callable[[], None],
    ) -> None:
        """
        Build the panel with the slider and the table hidden.

        :param parent: widget to place the panel in
        :param on_show: called when the user asks for the settings
        :param on_slider: called with the 1-based preset index when the user moves the slider
        :param on_optimal: called when the user asks for the recommended preset
        """
        self.frame: ttk.Frame = ttk.Frame(master=parent)
        self.frame.columnconfigure(index=0, weight=1)
        self.frame.rowconfigure(index=3, weight=1)
        self._on_slider: Callable[[int], None] = on_slider
        head: ttk.Frame = ttk.Frame(master=self.frame)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(index=0, weight=1)
        self._title: ttk.Label = ttk.Label(master=head, style=Theme.TITLE)
        self._title.grid(row=0, column=0, sticky="w")
        self._subtitle: ttk.Label = ttk.Label(master=head, style=Theme.MUTED)
        self._subtitle.grid(row=1, column=0, sticky="nw")
        self._position: ttk.Label = ttk.Label(master=head, style=Theme.BIG)
        self._position.grid(row=0, column=1, rowspan=2, sticky="e")
        self._caption: ttk.Label = ttk.Label(master=head, style=Theme.MUTED)
        self._caption.grid(row=2, column=1, sticky="e")
        self._button: ttk.Button = ttk.Button(master=self.frame, command=on_show, style=Theme.ACCENT)
        self._button.grid(row=1, column=0, sticky="w", pady=(_PAD, 0))
        self._button.grid_remove()
        self._slider_frame: ttk.Frame = ttk.Frame(master=self.frame)
        self._slider_frame.grid(row=2, column=0, sticky="ew", pady=(_PAD, _PAD + _PAD // 2))
        self._slider_frame.columnconfigure(index=1, weight=1)
        self._performance: ttk.Label = ttk.Label(master=self._slider_frame, style=Theme.MUTED)
        self._performance.grid(row=0, column=0, sticky="w")
        self._slider: ttk.Scale = ttk.Scale(master=self._slider_frame, orient="horizontal", from_=1, to=2)
        self._slider.configure(command=self._moved)
        self._slider.grid(row=0, column=1, sticky="ew", padx=_PAD)
        self._quality: ttk.Label = ttk.Label(master=self._slider_frame, style=Theme.MUTED)
        self._quality.grid(row=0, column=2, sticky="e")
        self._optimal: ttk.Button = ttk.Button(master=self._slider_frame, command=on_optimal, style=Theme.ACCENT)
        self._optimal.grid(row=0, column=3, padx=(_PAD * 2, 0))
        self._slider_frame.grid_remove()
        self._table_frame: ttk.Frame = ttk.Frame(master=self.frame)
        self._table_frame.grid(row=3, column=0, sticky="nsew")
        self._table_frame.columnconfigure(index=0, weight=1)
        self._table_frame.rowconfigure(index=0, weight=1)
        self._table: ttk.Treeview = ttk.Treeview(
            master=self._table_frame, columns=("setting", "value"), show="headings", selectmode="none"
        )
        self._table.column(column="setting", width=_SETTING_WIDTH, stretch=True)
        self._table.column(column="value", width=_VALUE_WIDTH, stretch=False)
        scrollbar: ttk.Scrollbar = ttk.Scrollbar(master=self._table_frame, orient="vertical", command=self._table.yview)
        self._table.configure(yscrollcommand=scrollbar.set)
        self._table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._table_frame.grid_remove()
        self._index: int = 0

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the panel.

        :param translator: translator of the UI language
        :return: None
        """
        self._button.configure(text=translator.text(item=UiText.SHOW_SETTINGS))
        self._performance.configure(text=translator.text(item=UiText.PERFORMANCE))
        self._quality.configure(text=translator.text(item=UiText.QUALITY))
        self._optimal.configure(text=translator.text(item=UiText.BACK_TO_OPTIMAL))
        self._table.heading(column="setting", text=translator.text(item=UiText.SETTING), anchor="w")
        self._table.heading(column="value", text=translator.text(item=UiText.VALUE), anchor="w")

    def apply_accent(self, *, color: str) -> None:
        """
        Color the rows that differ from the recommended preset.

        :param color: accent color of the theme
        :return: None
        """
        self._table.tag_configure(tagname=_CHANGED_TAG, foreground=color, font=Theme.STRONG_FONT)

    def show_button(self, *, visible: bool) -> None:
        """
        Show or hide the "Show settings" button.

        :param visible: True to show the button
        :return: None
        """
        if visible:
            self._button.grid()
        else:
            self._button.grid_remove()

    def show(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """
        self._index = settings.index
        self._title.configure(text=settings.title)
        self._subtitle.configure(text=settings.subtitle)
        self._position.configure(text=settings.position)
        self._caption.configure(text=settings.caption)
        self._slider.configure(to=max(settings.count, 2), state="normal" if settings.count > 1 else "disabled")
        self._slider.set(value=settings.index)
        self._optimal.configure(state="disabled" if settings.optimal else "normal")
        self._table.delete(*self._table.get_children())
        for row in settings.rows:
            self._table.insert(
                parent="", index="end", values=(row.name, row.value), tags=(_CHANGED_TAG,) if row.changed else ()
            )
        self._slider_frame.grid()
        self._table_frame.grid()

    def clear(self) -> None:
        """
        Hide the slider and the table.

        :return: None
        """
        for label in (self._title, self._subtitle, self._position, self._caption):
            label.configure(text="")
        self._table.delete(*self._table.get_children())
        self._slider_frame.grid_remove()
        self._table_frame.grid_remove()

    def _moved(self, value: str) -> None:
        """
        Pass a slider move to another preset on; ttk.Scale moves continuously, so the position is rounded.

        :param value: slider position as Tk passes it, e.g. "12.37"
        :return: None
        """
        index: int = round(float(value))
        if index != self._index:
            self._on_slider(index)


class _TopBar:
    """The GPU in use with the button to change it, and the theme and language choices."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        on_change_gpu: Callable[[], None],
        on_theme: Callable[[int], None],
        on_language: Callable[[str], None],
    ) -> None:
        """
        Build the bar.

        :param parent: widget to place the bar in
        :param on_change_gpu: called when the user wants another GPU
        :param on_theme: called with the position of the chosen theme
        :param on_language: called with the code of the chosen language
        """
        self.frame: ttk.Frame = ttk.Frame(master=parent, padding=_PAD)
        self.frame.columnconfigure(index=0, weight=1)
        self._hardware: ttk.Label = ttk.Label(master=self.frame, style=Theme.HEADLINE)
        self._hardware.grid(row=0, column=0, sticky="w")
        self._change_gpu: ttk.Button = ttk.Button(master=self.frame, command=on_change_gpu)
        self._change_gpu.grid(row=0, column=1, padx=_PAD)
        self._theme_label: ttk.Label = ttk.Label(master=self.frame, style=Theme.SECTION)
        self._theme_label.grid(row=0, column=2, padx=(_PAD * 2, _PAD))
        self._themes: ttk.Combobox = ttk.Combobox(master=self.frame, state="readonly", width=_COMBO_WIDTH)
        self._themes.grid(row=0, column=3)
        self._themes.bind(sequence="<<ComboboxSelected>>", func=lambda _: on_theme(self._themes.current()))
        self._language_label: ttk.Label = ttk.Label(master=self.frame, style=Theme.SECTION)
        self._language_label.grid(row=0, column=4, padx=(_PAD * 2, _PAD))
        self._language: ttk.Combobox = ttk.Combobox(
            master=self.frame, state="readonly", values=list(LANGUAGE_NAMES.values()), width=_COMBO_WIDTH
        )
        self._language.grid(row=0, column=5)
        self._language.bind(
            sequence="<<ComboboxSelected>>", func=lambda _: on_language(list(LANGUAGE_NAMES)[self._language.current()])
        )

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the bar and show the language in use.

        :param translator: translator of the UI language
        :return: None
        """
        self._change_gpu.configure(text=translator.text(item=UiText.CHANGE_GPU))
        self._theme_label.configure(text=translator.text(item=UiText.THEME))
        self._language_label.configure(text=translator.text(item=UiText.LANGUAGE))
        self._language.current(newindex=list(LANGUAGE_NAMES).index(translator.language))

    def show_hardware(self, *, text: str) -> None:
        """
        Show the GPU in use or why there is none.

        :param text: the line to show
        :return: None
        """
        self._hardware.configure(text=text)

    def recolor_popdowns(self, *, theme: Theme) -> None:
        """
        Recolor the drop-down lists of the comboboxes already opened; new ones take the colors from the option database.

        :param theme: theme just applied
        :return: None
        """
        for combobox in (self._themes, self._language):
            popdown: str = str(combobox.tk.call("ttk::combobox::PopdownWindow", str(combobox)))
            combobox.tk.call(
                f"{popdown}.f.l",
                "configure",
                "-background",
                theme.color(name="panel"),
                "-foreground",
                theme.color(name="fg"),
                "-selectbackground",
                theme.color(name="selected"),
                "-selectforeground",
                theme.color(name="fg"),
            )

    def show_themes(self, *, names: Sequence[str], selected: int) -> None:
        """
        Fill the theme choice.

        :param names: theme names in list order
        :param selected: position of the theme in use
        :return: None
        """
        self._themes.configure(values=list(names))
        self._themes.current(newindex=selected)


class _GamesColumn:
    """The game list with its search field and the button that requests the list again after a failure."""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        width: int,
        on_search: Callable[[str], None],
        on_load: Callable[[], None],
        on_select: Callable[[int], None],
    ) -> None:
        """
        Build the column with the "Load games" button hidden.

        :param parent: widget to place the column in
        :param width: width of the list in pixels
        :param on_search: called with the search text on every change
        :param on_load: called when the user asks for the game list again
        :param on_select: called with the position of the selected game
        """
        self.frame: ttk.Frame = ttk.Frame(master=parent)
        self.frame.columnconfigure(index=0, weight=1)
        self.frame.rowconfigure(index=3, weight=1)
        self._title: ttk.Label = ttk.Label(master=self.frame, style=Theme.SECTION)
        self._title.grid(row=0, column=0, sticky="w", pady=(0, _PAD // 2))
        search: ttk.Frame = ttk.Frame(master=self.frame)
        search.grid(row=1, column=0, sticky="ew", pady=(0, _PAD // 2))
        search.columnconfigure(index=1, weight=1)
        self._search_label: ttk.Label = ttk.Label(master=search, style=Theme.MUTED)
        self._search_label.grid(row=0, column=0, padx=(0, _PAD))
        self._search: tk.StringVar = tk.StringVar(master=self.frame)
        self._search.trace_add(mode="write", callback=lambda *_: on_search(self._search.get()))
        ttk.Entry(master=search, textvariable=self._search).grid(row=0, column=1, sticky="ew")
        self._load: ttk.Button = ttk.Button(master=self.frame, command=on_load)
        self._load.grid(row=2, column=0, sticky="ew", pady=(0, _PAD // 2))
        self._load.grid_remove()
        self.list: _ChoiceList = _ChoiceList(parent=self.frame, width=width, on_select=on_select)
        self.list.frame.grid(row=3, column=0, sticky="nsew")

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the column.

        :param translator: translator of the UI language
        :return: None
        """
        self._title.configure(text=translator.text(item=UiText.GAME))
        self._search_label.configure(text=translator.text(item=UiText.SEARCH))
        self._load.configure(text=translator.text(item=UiText.LOAD_GAMES))

    def show_load(self, *, visible: bool) -> None:
        """
        Show or hide the "Load games" button.

        :param visible: True to show the button
        :return: None
        """
        if visible:
            self._load.grid()
        else:
            self._load.grid_remove()


class MainWindow:  # pylint: disable=too-many-instance-attributes
    """The main window; user actions go to the presenter set with connect(), which fills the widgets in turn."""

    def __init__(self, *, root: tk.Tk, log_lines: Queue[str]) -> None:
        """
        Build every widget; texts are set by apply_language(), colors by apply_theme().

        :param root: Tk root window
        :param log_lines: formatted log lines for the log panel
        """
        self._root: tk.Tk = root
        self._presenter: Presenter | None = None
        self._translator: Translator | None = None
        self._theme: Theme = Theme(root=root)
        self._mode: ThemeMode = ThemeMode.AUTO
        self._applied: ThemeMode | None = None
        self._logs_shown: bool = False
        root.title(string=APP_TITLE)
        width, height = (round(int(size) * self._theme.scale) for size in WINDOW_SIZE.split(sep="x"))
        root.geometry(newGeometry=f"{width}x{height}")
        root.minsize(
            width=round(WINDOW_MIN_SIZE[0] * self._theme.scale), height=round(WINDOW_MIN_SIZE[1] * self._theme.scale)
        )
        root.report_callback_exception = self._report_callback_exception  # type: ignore[method-assign]
        root.columnconfigure(index=0, weight=1)
        root.rowconfigure(index=1, weight=1)

        self._top: _TopBar = _TopBar(
            parent=root,
            on_change_gpu=lambda: self._call(action=Presenter.change_gpu),
            on_theme=lambda index: self._call(action=lambda presenter: presenter.change_theme(index=index)),
            on_language=lambda code: self._call(action=lambda presenter: presenter.change_language(language=code)),
        )
        self._top.frame.grid(row=0, column=0, sticky="ew")

        body: ttk.Frame = ttk.Frame(master=root, padding=(_PAD, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(index=2, weight=1)
        body.rowconfigure(index=0, weight=1)
        self._games: _GamesColumn = _GamesColumn(
            parent=body,
            width=round(_GAMES_WIDTH * self._theme.scale),
            on_search=lambda text: self._call(action=lambda presenter: presenter.search_games(text=text)),
            on_load=lambda: self._call(action=Presenter.load_games),
            on_select=lambda index: self._call(action=lambda presenter: presenter.select_game(index=index)),
        )
        self._games.frame.grid(row=0, column=0, sticky="nsew", padx=(0, _PAD))

        resolutions: ttk.Frame = ttk.Frame(master=body)
        resolutions.grid(row=0, column=1, sticky="nsew", padx=(0, _PAD * 2))
        resolutions.columnconfigure(index=0, weight=1)
        resolutions.rowconfigure(index=1, weight=1)
        self._resolutions_label: ttk.Label = ttk.Label(master=resolutions, style=Theme.SECTION)
        self._resolutions_label.grid(row=0, column=0, sticky="w", pady=(0, _PAD // 2))
        self._resolutions: _ChoiceList = _ChoiceList(
            parent=resolutions,
            width=round(_RESOLUTIONS_WIDTH * self._theme.scale),
            on_select=lambda index: self._call(action=lambda presenter: presenter.select_resolution(index=index)),
        )
        self._resolutions.frame.grid(row=1, column=0, sticky="nsew")

        self._settings: _SettingsPanel = _SettingsPanel(
            parent=body,
            on_show=lambda: self._call(action=Presenter.show_settings),
            on_slider=lambda index: self._call(action=lambda presenter: presenter.move_slider(index=index)),
            on_optimal=lambda: self._call(action=Presenter.back_to_optimal),
        )
        self._settings.frame.grid(row=0, column=2, sticky="nsew")

        bottom: ttk.Frame = ttk.Frame(master=root, padding=_PAD)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(index=0, weight=1)
        self._status: ttk.Label = ttk.Label(master=bottom, style=Theme.MUTED)
        self._status.grid(row=0, column=0, sticky="w")
        self._logs_button: ttk.Button = ttk.Button(master=bottom, command=self._toggle_logs)
        self._logs_button.grid(row=0, column=1)
        self._log_panel: LogPanel = LogPanel(parent=root, lines=log_lines)
        root.after(ms=THEME_POLL_MS, func=self._follow_windows)

    def connect(self, *, presenter: Presenter) -> None:
        """
        Send the user actions to the presenter.

        :param presenter: presenter of this window
        :return: None
        """
        self._presenter = presenter

    def apply_theme(self, *, mode: ThemeMode) -> None:
        """
        Switch the colors of the window; AUTO follows the Windows app mode, also when it changes later.

        :param mode: theme mode
        :return: None
        """
        self._mode = mode
        applied: ThemeMode = self._theme.apply(mode=mode)
        self._applied = applied
        Theme.title_bar(window=self._root, dark=applied is ThemeMode.DARK)
        self._log_panel.apply_colors(
            background=self._theme.color(name="panel"), foreground=self._theme.color(name="fg")
        )
        self._settings.apply_accent(color=self._theme.color(name="accent"))
        self._top.recolor_popdowns(theme=self._theme)

    def show_themes(self, *, names: Sequence[str], selected: int) -> None:
        """
        Fill the theme choice.

        :param names: theme names in list order
        :param selected: position of the theme in use
        :return: None
        """
        self._top.show_themes(names=names, selected=selected)

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the window: labels, buttons, headings.

        :param translator: translator of the UI language
        :return: None
        """
        self._translator = translator
        self._top.apply_language(translator=translator)
        self._games.apply_language(translator=translator)
        self._resolutions_label.configure(text=translator.text(item=UiText.RESOLUTION))
        self._settings.apply_language(translator=translator)
        self._logs_button.configure(
            text=translator.text(item=UiText.HIDE_LOGS if self._logs_shown else UiText.SHOW_LOGS)
        )

    def show_hardware(self, *, text: str) -> None:
        """
        Show the GPU in use or why there is none.

        :param text: the line to show
        :return: None
        """
        self._top.show_hardware(text=text)

    def show_status(self, *, text: str) -> None:
        """
        Show progress, an error or a notice; an empty text clears the line.

        :param text: the line to show
        :return: None
        """
        self._status.configure(text=text)

    def show_load_games(self, *, visible: bool) -> None:
        """
        Show or hide the button that requests the game list again.

        :param visible: True to show the button
        :return: None
        """
        self._games.show_load(visible=visible)

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Fill the game list.

        :param names: display names in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """
        self._games.list.fill(items=names, selected=selected)

    def show_resolutions(self, *, items: Sequence[str]) -> None:
        """
        Fill the resolution list, keeping the selection when only the captions change (language switch).

        :param items: resolution captions in list order
        :return: None
        """
        selected: int | None = self._resolutions.selection()
        same: bool = len(self._resolutions.tree.get_children()) == len(items) > 0
        self._resolutions.fill(items=items, selected=selected if same else None)

    def show_settings_button(self, *, visible: bool) -> None:
        """
        Show or hide the "Show settings" button.

        :param visible: True to show the button
        :return: None
        """
        self._settings.show_button(visible=visible)

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """
        self._settings.show(settings=settings)

    def clear_settings(self) -> None:
        """
        Hide the settings table and the slider.

        :return: None
        """
        self._settings.clear()

    def ask_gpu(self, *, message: str, names: Sequence[str], selected: int | None) -> int | None:
        """
        Let the user pick a GPU in a modal dialog.

        :param message: why the user has to choose
        :param names: GPU names in list order
        :param selected: position preselected in the list, None for none
        :return: position of the chosen GPU, None when the user cancelled
        """
        if self._translator is None:
            return None
        dialog: _GpuDialog = _GpuDialog(
            parent=self._root,
            translator=self._translator,
            message=message,
            names=names,
            selected=selected,
            dark=self._applied is ThemeMode.DARK,
        )
        return dialog.run()

    def _call(self, *, action: Callable[[Presenter], None]) -> None:
        """
        Run a presenter action once the presenter is connected.

        :param action: the action
        :return: None
        """
        if self._presenter is not None:
            action(self._presenter)

    def _follow_windows(self) -> None:
        """
        Re-apply the AUTO theme when Windows switched between light and dark mode, then check again later.

        :return: None
        """
        if (
            self._mode is ThemeMode.AUTO
            and self._applied is not None
            and Theme.resolve(mode=ThemeMode.AUTO) != self._applied
        ):
            self.apply_theme(mode=ThemeMode.AUTO)
        self._root.after(ms=THEME_POLL_MS, func=self._follow_windows)

    def _toggle_logs(self) -> None:
        """
        Show or hide the log panel.

        :return: None
        """
        self._logs_shown = not self._logs_shown
        if self._logs_shown:
            self._log_panel.frame.grid(row=3, column=0, sticky="ew", padx=_PAD, pady=(0, _PAD))
        else:
            self._log_panel.frame.grid_remove()
        if self._translator is not None:
            self._logs_button.configure(
                text=self._translator.text(item=UiText.HIDE_LOGS if self._logs_shown else UiText.SHOW_LOGS)
            )

    @staticmethod
    def _report_callback_exception(
        exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType | None
    ) -> None:
        """
        Log an error raised in a Tk callback, which would otherwise go to the missing stderr.

        :param exc_type: exception type
        :param exc_value: exception
        :param traceback: traceback
        :return: None
        """
        logger.opt(exception=(exc_type, exc_value, traceback)).error("Unhandled error in the window")
