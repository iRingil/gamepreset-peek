"""The "OSD" ttk theme: graphite or steel-grey with a blue accent, the Windows app mode for AUTO, dark title bars."""

import ctypes
import tkinter as tk
import winreg
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

from loguru import logger

from app.core.models import ThemeMode

__all__: tuple[str, ...] = ("Theme",)


class Theme:  # pylint: disable=too-few-public-methods
    """Styles every ttk widget of a Tk application in the light or dark palette, built on the "clam" theme.

    Fonts are in points, which Tk scales to the screen DPI itself; sizes in pixels (row height, paddings) are scaled
    here. The style names for labels and buttons with a role are the class constants."""

    MUTED: str = "Muted.TLabel"
    SECTION: str = "Section.TLabel"
    HEADLINE: str = "Headline.TLabel"
    TITLE: str = "Title.TLabel"
    BIG: str = "Big.TLabel"
    ACCENT: str = "Accent.TButton"
    STRONG_FONT: str = "OsdStrong"
    LOG_FONT: str = "TkFixedFont"

    _PERSONALIZE_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    _DWMWA_USE_IMMERSIVE_DARK_MODE: int = 20
    _BASE_DPI: float = 96.0
    _BASE: str = "clam"
    _PALETTES: dict[ThemeMode, dict[str, str]] = {
        ThemeMode.DARK: {
            "bg": "#15171c",
            "panel": "#1d2027",
            "raised": "#262a33",
            "fg": "#d6dae1",
            "muted": "#868d9a",
            "selected": "#2a303b",
            "accent": "#4fb3ff",
            "on_accent": "#0e1620",
            "line": "#2b2f38",
        },
        ThemeMode.LIGHT: {
            "bg": "#dcdfe4",
            "panel": "#e8eaee",
            "raised": "#f1f2f5",
            "fg": "#20242b",
            "muted": "#5d6470",
            "selected": "#c9ced6",
            "accent": "#1d6fb8",
            "on_accent": "#f2f6fa",
            "line": "#c7cbd2",
        },
    }
    # Named fonts: name -> (family, size in points); weights are separate families. Bahnschrift ships with Windows 10+.
    _FONTS: dict[str, tuple[str, int]] = {
        "OsdBody": ("Segoe UI", 10),
        STRONG_FONT: ("Segoe UI Semibold", 10),
        "OsdSmall": ("Bahnschrift", 9),
        "OsdSection": ("Bahnschrift SemiBold", 10),
        "OsdHeadline": ("Bahnschrift SemiBold", 12),
        "OsdTitle": ("Bahnschrift SemiBold", 17),
        "OsdBig": ("Bahnschrift SemiBold", 26),
    }
    # Pixel sizes at 96 DPI.
    _ROW_PADDING: int = 8
    _SLIDER_SIZE: int = 18
    _ARROW_SIZE: int = 12

    def __init__(self, *, root: tk.Tk) -> None:
        """
        Create the fonts and measure the screen scale; no style is set before apply().

        :param root: Tk root window
        """
        self._root: tk.Tk = root
        self.scale: float = root.winfo_fpixels("1i") / self._BASE_DPI
        # Kept referenced: a garbage-collected tkfont.Font deletes its named font from Tk.
        self._fonts: list[tkfont.Font] = [
            tkfont.Font(root=root, name=name, family=family, size=size) for name, (family, size) in self._FONTS.items()
        ]
        self._colors: dict[str, str] = self._PALETTES[ThemeMode.DARK]

    def apply(self, *, mode: ThemeMode) -> ThemeMode:
        """
        Style the ttk widgets in the light or dark palette.

        :param mode: theme mode; AUTO takes the Windows app mode
        :return: the mode applied, LIGHT or DARK
        """
        resolved: ThemeMode = self.resolve(mode=mode)
        self._colors = self._PALETTES[resolved]
        style: ttk.Style = ttk.Style(master=self._root)
        style.theme_use(self._BASE)
        self._style_text(style=style)
        self._style_controls(style=style)
        self._style_lists(style=style)
        self._root.configure(background=self.color(name="bg"))
        for option, name in (("background", "panel"), ("foreground", "fg"), ("selectBackground", "selected")):
            self._root.option_add(f"*TCombobox*Listbox.{option}", self.color(name=name))
        self._root.option_add("*TCombobox*Listbox.selectForeground", self.color(name="fg"))
        logger.info("Theme: {} ({}), scale {}", resolved.value, mode.value, self.scale)
        return resolved

    def color(self, *, name: str) -> str:
        """
        Get a color of the palette applied last, for tk widgets ttk doesn't style and for highlights.

        :param name: "bg", "panel", "raised", "fg", "muted", "selected", "accent", "on_accent" or "line"
        :return: color as #rrggbb
        """
        return self._colors[name]

    @classmethod
    def resolve(cls, *, mode: ThemeMode) -> ThemeMode:
        """
        Turn AUTO into the Windows app mode.

        :param mode: chosen theme mode
        :return: LIGHT or DARK
        """
        if mode is not ThemeMode.AUTO:
            return mode
        return ThemeMode.DARK if cls._windows_dark() else ThemeMode.LIGHT

    @classmethod
    def title_bar(cls, *, window: tk.Tk | tk.Toplevel, dark: bool) -> None:
        """
        Make the Windows title bar of a window dark or light; Windows 10 before 20H1 ignores it.

        :param window: Tk or Toplevel window
        :param dark: True for a dark title bar
        :return: None
        """
        window.update_idletasks()
        # winfo_id() is Tk's client window; the title bar belongs to its parent, the top-level frame.
        get_parent: Any = ctypes.WinDLL(name="user32")["GetParent"]
        set_attribute: Any = ctypes.WinDLL(name="dwmapi")["DwmSetWindowAttribute"]
        value: ctypes.c_int = ctypes.c_int(1 if dark else 0)
        set_attribute(
            get_parent(window.winfo_id()),
            cls._DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )

    def _style_text(self, *, style: ttk.Style) -> None:
        """
        Style the base of every widget and the labels.

        :param style: ttk style of the application
        :return: None
        """
        style.configure(
            ".",
            background=self.color(name="bg"),
            foreground=self.color(name="fg"),
            font="OsdBody",
            troughcolor=self.color(name="panel"),
            fieldbackground=self.color(name="panel"),
            selectbackground=self.color(name="selected"),
            selectforeground=self.color(name="fg"),
            insertcolor=self.color(name="fg"),
            focuscolor=self.color(name="accent"),
            **self._flat(name="bg"),
        )
        style.map(".", foreground=[("disabled", self.color(name="muted"))])
        style.configure(self.MUTED, foreground=self.color(name="muted"), font="OsdSmall")
        style.configure(self.SECTION, foreground=self.color(name="muted"), font="OsdSection")
        style.configure(self.HEADLINE, font="OsdHeadline")
        style.configure(self.TITLE, font="OsdTitle")
        style.configure(self.BIG, foreground=self.color(name="accent"), font="OsdBig")

    def _style_controls(self, *, style: ttk.Style) -> None:
        """
        Style the buttons, the entry, the comboboxes and the slider: flat, filled, no 3D borders.

        :param style: ttk style of the application
        :return: None
        """
        padding: tuple[int, int] = (round(12 * self.scale), round(5 * self.scale))
        style.configure(
            "TButton",
            background=self.color(name="raised"),
            padding=padding,
            focuscolor=self.color(name="raised"),
            **self._flat(name="raised"),
        )
        style.map(
            "TButton", background=[("pressed", self.color(name="selected")), ("active", self.color(name="selected"))]
        )
        style.configure(
            self.ACCENT,
            background=self.color(name="accent"),
            foreground=self.color(name="on_accent"),
            font=self.STRONG_FONT,
            focuscolor=self.color(name="accent"),
            **self._flat(name="accent"),
        )
        style.map(
            self.ACCENT,
            background=[("disabled", self.color(name="raised")), ("active", self.color(name="accent"))],
            foreground=[("disabled", self.color(name="muted")), ("active", self.color(name="on_accent"))],
        )
        field: dict[str, Any] = {
            "fieldbackground": self.color(name="panel"),
            "padding": round(4 * self.scale),
            "bordercolor": self.color(name="line"),
            "lightcolor": self.color(name="panel"),
            "darkcolor": self.color(name="panel"),
        }
        style.configure("TEntry", **field)
        style.map(
            "TEntry",
            bordercolor=[("focus", self.color(name="accent"))],
            lightcolor=[("focus", self.color(name="accent"))],
        )
        style.configure(
            "TCombobox",
            background=self.color(name="panel"),
            arrowcolor=self.color(name="muted"),
            selectbackground=self.color(name="panel"),
            selectforeground=self.color(name="fg"),
            **field,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.color(name="panel"))],
            background=[("readonly", self.color(name="panel"))],
            foreground=[("readonly", self.color(name="fg"))],
        )
        style.configure(
            "Horizontal.TScale",
            background=self.color(name="accent"),
            troughcolor=self.color(name="raised"),
            sliderlength=round(self._SLIDER_SIZE * self.scale),
            sliderthickness=round(self._SLIDER_SIZE * self.scale),
            gripcount=0,
            bordercolor=self.color(name="raised"),
            lightcolor=self.color(name="accent"),
            darkcolor=self.color(name="accent"),
        )

    def _style_lists(self, *, style: ttk.Style) -> None:
        """
        Style the lists and tables (Treeview), their headings and the scrollbars.

        :param style: ttk style of the application
        :return: None
        """
        body: tkfont.Font = tkfont.nametofont(name="OsdBody", root=self._root)
        style.configure(
            "Treeview",
            background=self.color(name="panel"),
            fieldbackground=self.color(name="panel"),
            rowheight=int(body.metrics("linespace")) + round(self._ROW_PADDING * self.scale),
            borderwidth=0,
            **self._flat(name="panel"),
        )
        style.map(
            "Treeview",
            background=[("selected", self.color(name="selected"))],
            foreground=[("selected", self.color(name="fg"))],
        )
        style.configure(
            "Treeview.Heading",
            foreground=self.color(name="muted"),
            font="OsdSection",
            relief="flat",
            padding=(round(6 * self.scale), round(4 * self.scale)),
        )
        style.map("Treeview.Heading", background=[("active", self.color(name="bg"))])
        style.configure(
            "Vertical.TScrollbar",
            background=self.color(name="raised"),
            troughcolor=self.color(name="panel"),
            arrowcolor=self.color(name="muted"),
            gripcount=0,
            arrowsize=round(self._ARROW_SIZE * self.scale),
            **self._flat(name="panel"),
        )
        style.map("Vertical.TScrollbar", background=[("active", self.color(name="selected"))])

    def _flat(self, *, name: str) -> dict[str, str]:
        """
        Make the 3D border colors of "clam" one flat color.

        :param name: palette color name
        :return: border, light and dark color options
        """
        color: str = self.color(name=name)
        return {"bordercolor": color, "lightcolor": color, "darkcolor": color}

    @classmethod
    def _windows_dark(cls) -> bool:
        """
        Read whether Windows runs apps in dark mode.

        :return: True for dark mode; False for light mode or when the setting can't be read
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls._PERSONALIZE_KEY) as key:
                value: Any = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        except OSError:
            return False
        return bool(value == 0)
