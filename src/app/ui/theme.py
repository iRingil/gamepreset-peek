"""The app ttk theme: a sea palette in light or dark with rounded elements; AUTO mode and dark title bars."""

import ctypes
import tkinter as tk
import winreg
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

from loguru import logger

from app.core.models import ThemeMode

__all__: tuple[str, ...] = ("Theme",)


class _Shapes:
    """Rounded rectangles drawn into named Tk images, antialiased against the color around them.

    Tk images have no partial transparency, so the edge pixels are blended with the color the shape sits on. An
    image keeps its name when redrawn, so the ttk elements made from it follow a palette switch."""

    _SAMPLES: int = 4

    def __init__(self, *, root: tk.Tk) -> None:
        """
        Start with no images.

        :param root: Tk root window
        """
        self._root: tk.Tk = root
        self._images: dict[str, tk.PhotoImage] = {}

    def draw(  # pylint: disable=too-many-arguments
        self,
        *,
        name: str,
        size: tuple[int, int],
        radius: int,
        fill: str,
        outside: str,
        border: str | None = None,
        border_width: int = 0,
    ) -> str:
        """
        Draw a rounded rectangle, replacing the image of that name if it exists.

        :param name: image name, also used in ttk element definitions
        :param size: width and height in pixels
        :param radius: corner radius in pixels
        :param fill: inner color
        :param outside: color of the surface around the shape
        :param border: border color, None for no border
        :param border_width: border width in pixels
        :return: the image name
        """
        width: int
        height: int
        width, height = size
        image: tk.PhotoImage | None = self._images.get(name)
        if image is None:
            image = tk.PhotoImage(master=self._root, name=name, width=width, height=height)
            self._images[name] = image
        rows: list[str] = []
        for y in range(height):
            row: list[str] = []
            for x in range(width):
                outer: float = self._coverage(x=x, y=y, size=size, radius=radius, inset=0)
                if border is None:
                    row.append(self.mix(first=outside, second=fill, share=outer))
                    continue
                inner: float = self._coverage(x=x, y=y, size=size, radius=radius, inset=border_width)
                edge: str = self.mix(first=outside, second=border, share=outer)
                row.append(self.mix(first=edge, second=fill, share=inner))
            rows.append("{" + " ".join(row) + "}")
        image.put(" ".join(rows))
        return name

    @staticmethod
    def mix(*, first: str, second: str, share: float) -> str:
        """
        Blend two colors.

        :param first: color as #rrggbb
        :param second: color as #rrggbb
        :param share: share of the second color, 0 to 1
        :return: blended color as #rrggbb
        """
        channels: list[int] = [
            round(int(first[i : i + 2], 16) * (1 - share) + int(second[i : i + 2], 16) * share) for i in (1, 3, 5)
        ]
        return "#" + "".join(f"{channel:02x}" for channel in channels)

    @classmethod
    def _coverage(cls, *, x: int, y: int, size: tuple[int, int], radius: float, inset: float) -> float:
        """
        Measure how much of a pixel lies inside a rounded rectangle shrunk by an inset.

        :param x: pixel column
        :param y: pixel row
        :param size: width and height of the rectangle
        :param radius: corner radius before the inset
        :param inset: distance the edges move inwards
        :return: covered share of the pixel, 0 to 1
        """
        left: float = inset
        top: float = inset
        right: float = size[0] - inset
        bottom: float = size[1] - inset
        corner: float = max(radius - inset, 0.0)
        inside: int = 0
        for sub_x in range(cls._SAMPLES):
            for sub_y in range(cls._SAMPLES):
                point_x: float = x + (sub_x + 0.5) / cls._SAMPLES
                point_y: float = y + (sub_y + 0.5) / cls._SAMPLES
                # Distance to the nearest point of the inner rectangle the corners are drawn around.
                near_x: float = min(max(point_x, left + corner), right - corner)
                near_y: float = min(max(point_y, top + corner), bottom - corner)
                if (
                    left <= point_x <= right
                    and top <= point_y <= bottom
                    and (point_x - near_x) ** 2 + (point_y - near_y) ** 2 <= corner**2
                ):
                    inside += 1
        return inside / cls._SAMPLES**2


class Theme:
    """Styles every ttk widget of a Tk application in the light or dark palette, on top of the "clam" theme.

    Buttons, fields, lists, scrollbars and the slider are image elements with rounded corners, drawn for the palette
    and the screen scale. Fonts are in points, which Tk scales to the DPI itself; pixel sizes are scaled here."""

    MUTED: str = "Muted.TLabel"
    SECTION: str = "Section.TLabel"
    HEADLINE: str = "Headline.TLabel"
    TITLE: str = "Title.TLabel"
    BIG: str = "Big.TLabel"
    ACCENT: str = "Accent.TButton"
    STRONG_FONT: str = "AppStrong"
    BODY_FONT: str = "AppBody"
    MARKED_LIST: str = "Marked.Treeview"
    # Text indent of a marked list item in pixels: the width of the clam tree indicator it replaces, which is unscaled.
    MARKED_INDENT: int = 17

    _PERSONALIZE_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    _DWMWA_USE_IMMERSIVE_DARK_MODE: int = 20
    _BASE_DPI: float = 96.0
    _BASE: str = "clam"
    # Sea palette: Oxford by Night #031830, Dark Eclipse #0a2943, Deadwind Pass #576e7d, Porch Ceiling #a4b2ba,
    # Delicacy White #ede3e4, plus a turquoise accent the palette lacks.
    _PALETTES: dict[ThemeMode, dict[str, str]] = {
        ThemeMode.DARK: {
            "bg": "#031830",
            "panel": "#0a2943",
            "raised": "#163a57",
            "fg": "#ede3e4",
            "muted": "#a4b2ba",
            "selected": "#576e7d",
            "accent": "#5ec4e0",
            "on_accent": "#031830",
            "line": "#2a4a63",
        },
        ThemeMode.LIGHT: {
            "bg": "#ede3e4",
            "panel": "#e2dadc",
            "raised": "#cdd3d8",
            "fg": "#031830",
            "muted": "#576e7d",
            "selected": "#a4b2ba",
            "accent": "#17708f",
            "on_accent": "#f6f1f1",
            "line": "#a4b2ba",
        },
    }
    # Named fonts: name -> (family, size in points); weights are separate families. Bahnschrift ships with Windows 10+.
    _FONTS: dict[str, tuple[str, int]] = {
        BODY_FONT: ("Segoe UI", 10),
        STRONG_FONT: ("Segoe UI Semibold", 10),
        "AppSmall": ("Bahnschrift", 9),
        "AppSection": ("Bahnschrift SemiBold", 10),
        "AppHeadline": ("Bahnschrift SemiBold", 12),
        "AppTitle": ("Bahnschrift SemiBold", 17),
        "AppBig": ("Bahnschrift SemiBold", 26),
    }
    # Pixel sizes at 96 DPI.
    _RADIUS: int = 6
    _ROW_PADDING: int = 10
    _KNOB: int = 18
    _TRACK: int = 6
    _THUMB: int = 10
    # Element names of the rounded shapes, created once per Tk application.
    _BUTTON: str = "App.Button.border"
    _ACCENT_BUTTON: str = "App.Accent.border"
    _FIELD: str = "App.Field.field"
    _CARD: str = "App.Card.field"
    _THUMB_ELEMENT: str = "App.Scrollbar.thumb"
    _TRACK_ELEMENT: str = "App.Scale.trough"
    _KNOB_ELEMENT: str = "App.Scale.slider"

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
        self._shapes: _Shapes = _Shapes(root=root)
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
        self._draw_shapes()
        if self._BUTTON not in style.element_names():
            self._create_elements(style=style)
        self._style_text(style=style)
        self._style_controls(style=style)
        self._style_lists(style=style)
        self._root.configure(background=self.color(name="bg"))
        for option, name in (
            ("background", "panel"),
            ("foreground", "fg"),
            ("selectBackground", "selected"),
            ("selectForeground", "fg"),
        ):
            self._root.option_add(f"*TCombobox*Listbox.{option}", self.color(name=name))
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

    def _px(self, *, size: float) -> int:
        """
        Scale a size in pixels at 96 DPI to the screen.

        :param size: size at 96 DPI
        :return: size on the screen, at least 1
        """
        return max(1, round(size * self.scale))

    def _draw_shapes(self) -> None:
        """
        Draw the images of the rounded elements in the palette applied.

        :return: None
        """
        radius: int = self._px(size=self._RADIUS)
        box: tuple[int, int] = (2 * radius + 6, 2 * radius + 6)
        bg: str = self.color(name="bg")
        accent: str = self.color(name="accent")
        boxes: dict[str, str] = {
            "app_button": self.color(name="raised"),
            "app_button_active": self.color(name="selected"),
            "app_accent": accent,
            "app_accent_active": _Shapes.mix(first=accent, second=self.color(name="fg"), share=0.15),
            "app_card": self.color(name="panel"),
        }
        for name, fill in boxes.items():
            self._shapes.draw(name=name, size=box, radius=radius, fill=fill, outside=bg)
        for name, border in (("app_field", self.color(name="line")), ("app_field_focus", accent)):
            self._shapes.draw(
                name=name,
                size=box,
                radius=radius,
                fill=self.color(name="panel"),
                outside=bg,
                border=border,
                border_width=self._px(size=1),
            )
        thumb: int = self._px(size=self._THUMB)
        self._shapes.draw(
            name="app_thumb",
            size=(thumb, thumb + 6),
            radius=thumb // 2,
            fill=self.color(name="selected"),
            outside=bg,
        )
        track: int = self._px(size=self._TRACK)
        self._shapes.draw(
            name="app_track",
            size=(track * 3, track),
            radius=track // 2,
            fill=self.color(name="selected"),
            outside=bg,
        )
        knob: int = self._px(size=self._KNOB)
        self._shapes.draw(name="app_knob", size=(knob, knob), radius=knob // 2, fill=accent, outside=bg)

    def _create_elements(self, *, style: ttk.Style) -> None:
        """
        Make the rounded image elements and the layouts that use them.

        :param style: ttk style of the application
        :return: None
        """
        # The border is the part of an image that doesn't stretch: just past the corner, below half the image.
        corner: int = self._px(size=self._RADIUS) + 1
        style.element_create(
            self._BUTTON,
            "image",
            "app_button",
            ("pressed", "app_button_active"),
            ("active", "app_button_active"),
            border=corner,
            sticky="nsew",
        )
        style.element_create(
            self._ACCENT_BUTTON,
            "image",
            "app_accent",
            ("disabled", "app_button"),
            ("active", "app_accent_active"),
            border=corner,
            sticky="nsew",
        )
        style.element_create(
            self._FIELD, "image", "app_field", ("focus", "app_field_focus"), border=corner, sticky="nsew"
        )
        style.element_create(self._CARD, "image", "app_card", border=corner, sticky="nsew")
        half_thumb: int = self._px(size=self._THUMB) // 2
        style.element_create(self._THUMB_ELEMENT, "image", "app_thumb", border=half_thumb, sticky="ns")
        style.element_create(
            self._TRACK_ELEMENT, "image", "app_track", border=(self._px(size=self._TRACK), 0), sticky="ew"
        )
        style.element_create(self._KNOB_ELEMENT, "image", "app_knob", sticky="")
        label: list[Any] = [("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]
        style.layout("TButton", [(self._BUTTON, {"sticky": "nsew", "children": label})])
        style.layout(self.ACCENT, [(self._ACCENT_BUTTON, {"sticky": "nsew", "children": label})])
        style.layout(
            "TEntry",
            [
                (
                    self._FIELD,
                    {
                        "sticky": "nsew",
                        "children": [
                            ("Entry.padding", {"sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]})
                        ],
                    },
                )
            ],
        )
        style.layout(
            "TCombobox",
            [
                (
                    self._FIELD,
                    {
                        "sticky": "nsew",
                        "children": [
                            ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
                            (
                                "Combobox.padding",
                                {"sticky": "nsew", "children": [("Combobox.textarea", {"sticky": "nsew"})]},
                            ),
                        ],
                    },
                )
            ],
        )
        style.layout(
            "Treeview",
            [
                (
                    self._CARD,
                    {
                        "sticky": "nsew",
                        "children": [
                            (
                                "Treeview.padding",
                                {"sticky": "nsew", "children": [("Treeview.treearea", {"sticky": "nsew"})]},
                            )
                        ],
                    },
                )
            ],
        )
        style.layout(self.MARKED_LIST, style.layout("Treeview"))
        # A flat list has no tree indicator; the item image follows the text as a mark after it.
        style.layout(
            f"{self.MARKED_LIST}.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nsew",
                        "children": [
                            ("Treeitem.text", {"side": "left", "sticky": ""}),
                            ("Treeitem.image", {"side": "left", "sticky": ""}),
                        ],
                    },
                )
            ],
        )
        style.layout(
            "Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {"sticky": "ns", "children": [(self._THUMB_ELEMENT, {"sticky": "nswe"})]},
                )
            ],
        )
        style.layout(
            "Horizontal.TScale",
            [
                (
                    self._TRACK_ELEMENT,
                    {"sticky": "ew", "children": [(self._KNOB_ELEMENT, {"side": "left", "sticky": ""})]},
                )
            ],
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
            font=self.BODY_FONT,
            troughcolor=self.color(name="bg"),
            fieldbackground=self.color(name="panel"),
            selectbackground=self.color(name="selected"),
            selectforeground=self.color(name="fg"),
            insertcolor=self.color(name="fg"),
            focuscolor=self.color(name="accent"),
            **self._flat(name="bg"),
        )
        style.map(".", foreground=[("disabled", self.color(name="muted"))])
        style.configure(self.MUTED, foreground=self.color(name="muted"), font="AppSmall")
        style.configure(self.SECTION, foreground=self.color(name="muted"), font="AppSection")
        style.configure(self.HEADLINE, font="AppHeadline")
        style.configure(self.TITLE, font="AppTitle")
        style.configure(self.BIG, foreground=self.color(name="accent"), font="AppBig")

    def _style_controls(self, *, style: ttk.Style) -> None:
        """
        Style the buttons, the entry and the comboboxes; their shapes are the rounded elements.

        :param style: ttk style of the application
        :return: None
        """
        padding: tuple[int, int] = (self._px(size=14), self._px(size=6))
        style.configure("TButton", foreground=self.color(name="fg"), padding=padding)
        style.configure(self.ACCENT, foreground=self.color(name="on_accent"), font=self.STRONG_FONT, padding=padding)
        style.map(self.ACCENT, foreground=[("disabled", self.color(name="muted"))])
        style.configure("TEntry", padding=(self._px(size=8), self._px(size=5)))
        style.configure(
            "TCombobox",
            padding=(self._px(size=8), self._px(size=4)),
            arrowcolor=self.color(name="muted"),
            background=self.color(name="panel"),
            selectbackground=self.color(name="panel"),
            selectforeground=self.color(name="fg"),
            **self._flat(name="panel"),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.color(name="panel"))],
            background=[("readonly", self.color(name="panel"))],
            foreground=[("readonly", self.color(name="fg"))],
        )

    def _style_lists(self, *, style: ttk.Style) -> None:
        """
        Style the lists and tables (Treeview), their headings and the scrollbars.

        :param style: ttk style of the application
        :return: None
        """
        body: tkfont.Font = self._fonts[0]
        style.configure(
            "Treeview",
            background=self.color(name="panel"),
            fieldbackground=self.color(name="panel"),
            foreground=self.color(name="fg"),
            rowheight=int(body.metrics("linespace")) + self._px(size=self._ROW_PADDING),
            padding=self._px(size=4),
        )
        style.map(
            "Treeview",
            background=[("selected", self.color(name="selected"))],
            foreground=[("selected", self.color(name="fg"))],
        )
        style.configure(f"{self.MARKED_LIST}.Item", padding=(self.MARKED_INDENT, 0, 0, 0))
        style.configure(
            "Treeview.Heading",
            background=self.color(name="panel"),
            foreground=self.color(name="muted"),
            font="AppSection",
            relief="flat",
            padding=(self._px(size=6), self._px(size=4)),
            **self._flat(name="panel"),
        )
        style.map("Treeview.Heading", background=[("active", self.color(name="panel"))])
        style.configure("Vertical.TScrollbar", troughcolor=self.color(name="bg"), **self._flat(name="bg"))

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
