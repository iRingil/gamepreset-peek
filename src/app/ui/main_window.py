"""Widgets and layout of the main window and of the CPU, GPU and resolution choice drop-downs."""

import html
from pathlib import Path
from queue import Queue
from typing import Callable, Sequence

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPersistentModelIndex, QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_TITLE, WINDOW_MIN_SIZE, WINDOW_SIZE
from app.core.models import GamesTab, ThemeMode
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.choice_popup import ChoicePopup
from app.ui.cover_view import CoverView
from app.ui.games_panel import GamesPanel
from app.ui.icons import IconButton
from app.ui.log_panel import LogPanel
from app.ui.preset_slider import PresetSlider
from app.ui.presenter import Presenter
from app.ui.settings_menu import SettingsMenu
from app.ui.skeleton import SettingsSkeleton
from app.ui.theme import Theme
from app.ui.typography import GAP, Typography
from app.ui.views import ChoiceView, HardwareView, InstalledGameView, SettingsView, StatusLevel

__all__: tuple[str, ...] = ("MainWindow",)

# Width of the value column of the settings table, in ems.
_VALUE_WIDTH: float = 16
# Item data role of the settings table telling that a value differs from the recommended preset.
_CHANGED_ROLE: int = Qt.ItemDataRole.UserRole + 1


class _ChangedDelegate(QStyledItemDelegate):
    """Draws the values that differ from the recommended preset in bold and in the accent color of the theme.

    The color is taken while painting, so a switch between light and dark mode reaches it at once."""

    def initStyleOption(  # pylint: disable=invalid-name
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        """
        Style an item, emphasizing a changed value.

        :param option: item style to fill
        :param index: item
        :return: None
        """
        super().initStyleOption(option, index)
        if index.data(_CHANGED_ROLE):
            option.font.setBold(True)
            option.palette.setColor(QPalette.ColorRole.Text, option.palette.color(QPalette.ColorRole.Link))


class _SettingsPanel(QWidget):  # pylint: disable=too-many-instance-attributes
    """The game title, the quality slider and the settings table.

    Rows whose value differs from the recommended preset are emphasized: that is what the slider trades."""

    def __init__(
        self, *, on_slider: Callable[[int], None], on_optimal: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        """
        Build the panel with the slider and the table hidden.

        :param on_slider: called with the 1-based preset index when the user moves the slider
        :param on_optimal: called when the user asks for the recommended preset
        :param parent: widget the panel belongs to
        """
        super().__init__(parent)
        self._on_slider: Callable[[int], None] = on_slider
        self._index: int = 0
        self._title: QLabel = QLabel(parent=self)
        self._title.setFont(Typography.heading(base=self.font()))
        # A long name wraps instead of running under the preset number.
        self._title.setWordWrap(True)
        self._position: QLabel = QLabel(parent=self)
        self._position.setFont(Typography.heading(base=self.font()))
        # The theme's accent comes as Link, the Accent role is Windows' own.
        self._position.setForegroundRole(QPalette.ColorRole.Link)
        self._caption: QLabel = self._muted(parent=self)
        self._slider_row: QWidget = QWidget(parent=self)
        self._slider_row.hide()
        self._performance: QLabel = self._muted(parent=self._slider_row)
        self.slider: PresetSlider = PresetSlider(parent=self._slider_row)
        self.slider.valueChanged.connect(self._moved)
        self._quality: QLabel = self._muted(parent=self._slider_row)
        self._optimal: QPushButton = QPushButton(parent=self._slider_row)
        self._optimal.clicked.connect(on_optimal)
        self._table: QTreeWidget = self._settings_table()
        self._lay_out()

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the panel.

        :param translator: translator of the UI language
        :return: None
        """
        self._performance.setText(translator.text(item=UiText.PERFORMANCE))
        self._quality.setText(translator.text(item=UiText.QUALITY))
        self._optimal.setText(translator.text(item=UiText.OPTIMAL))
        self._optimal.setToolTip(translator.text(item=UiText.OPTIMAL_HINT))
        self.slider.setToolTip(translator.text(item=UiText.SLIDER_HINT))
        self._table.setHeaderLabels([translator.text(item=UiText.SETTING), translator.text(item=UiText.VALUE)])

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """
        self._index = settings.index
        self._title.setText(settings.title)
        self._position.setText(settings.position)
        self._caption.setText(settings.caption)
        self.slider.set_presets(count=settings.count, index=settings.index, recommended=settings.recommended)
        self._optimal.setEnabled(not settings.optimal)
        self._table.clear()
        items: list[QTreeWidgetItem] = []
        for row in settings.rows:
            item: QTreeWidgetItem = QTreeWidgetItem([row.name, row.value])
            for column in range(2):
                item.setData(column, _CHANGED_ROLE, row.changed)
                item.setToolTip(column, row.hint)
            items.append(item)
        self._table.addTopLevelItems(items)
        self._slider_row.show()
        self._table.show()

    def clear(self) -> None:
        """
        Hide the slider and the table.

        :return: None
        """
        for label in (self._title, self._position, self._caption):
            label.clear()
        self._table.clear()
        self._slider_row.hide()
        self._table.hide()

    @staticmethod
    def _muted(*, parent: QWidget) -> QLabel:
        """
        Make a label in the dimmed text color of the palette.

        :param parent: widget the label belongs to
        :return: the label
        """
        label: QLabel = QLabel(parent=parent)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        return label

    def _settings_table(self) -> QTreeWidget:
        """
        Make the hidden two-column table of setting names and values.

        :return: the table
        """
        table: QTreeWidget = QTreeWidget(parent=self)
        table.setColumnCount(2)
        table.setRootIsDecorated(False)
        table.setUniformRowHeights(True)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setItemDelegate(_ChangedDelegate(table))
        header: QHeaderView = table.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(1, Typography.px(ems=_VALUE_WIDTH))
        table.hide()
        return table

    def _lay_out(self) -> None:
        """
        Place the widgets: the title with the preset position right of it, the slider row, the table.

        :return: None
        """
        titles: QVBoxLayout = QVBoxLayout()
        titles.addWidget(self._title)
        titles.addStretch()
        preset: QVBoxLayout = QVBoxLayout()
        preset.addWidget(self._position, alignment=Qt.AlignmentFlag.AlignRight)
        preset.addWidget(self._caption, alignment=Qt.AlignmentFlag.AlignRight)
        head: QHBoxLayout = QHBoxLayout()
        head.addLayout(titles, stretch=1)
        head.addLayout(preset)
        slider: QHBoxLayout = QHBoxLayout(self._slider_row)
        slider.setContentsMargins(0, Typography.px(ems=GAP), 0, Typography.px(ems=GAP))
        slider.addWidget(self._performance)
        slider.addWidget(self.slider, stretch=1)
        slider.addWidget(self._quality)
        slider.addSpacing(Typography.px(ems=GAP * 2))
        slider.addWidget(self._optimal)
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addWidget(self._slider_row)
        layout.addWidget(self._table, stretch=1)
        layout.addStretch()

    def _moved(self, index: int) -> None:
        """
        Pass a slider move to another preset on.

        :param index: 1-based preset index
        :return: None
        """
        if index != self._index:
            self._on_slider(index)


class _HardwareBlock(QWidget):
    """The CPU, GPU and screen resolution in use as links that open their choice, next to the memory sizes."""

    def __init__(
        self,
        *,
        on_cpu: Callable[[], None],
        on_gpu: Callable[[], None],
        on_resolution: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the block: three columns of a caption and a value, CPU over GPU, RAM over VRAM, the resolution.

        :param on_cpu: called when the user opens the CPU choice
        :param on_gpu: called when the user opens the GPU choice
        :param on_resolution: called when the user opens the resolution choice
        :param parent: widget the block belongs to
        """
        super().__init__(parent)
        self._captions: dict[UiText, QLabel] = {
            item: self._caption() for item in (UiText.CPU, UiText.GPU, UiText.RESOLUTION, UiText.RAM, UiText.VRAM)
        }
        self.cpu: QLabel = self._link(on_click=on_cpu)
        self.gpu: QLabel = self._link(on_click=on_gpu)
        self.resolution: QLabel = self._link(on_click=on_resolution)
        self._memory: QLabel = self._value()
        self._video_memory: QLabel = self._value()
        grid: QGridLayout = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        # Caption, value, gap, caption, value, gap, caption, value.
        grid.setColumnMinimumWidth(2, Typography.px(ems=GAP * 4))
        grid.setColumnMinimumWidth(5, Typography.px(ems=GAP * 4))
        cells: tuple[tuple[UiText, QLabel, int, int], ...] = (
            (UiText.CPU, self.cpu, 0, 0),
            (UiText.GPU, self.gpu, 1, 0),
            (UiText.RAM, self._memory, 0, 3),
            (UiText.VRAM, self._video_memory, 1, 3),
            (UiText.RESOLUTION, self.resolution, 0, 6),
        )
        for name, value, row, column in cells:
            grid.addWidget(self._captions[name], row, column)
            grid.addWidget(value, row, column + 1)

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the captions.

        :param translator: translator of the UI language
        :return: None
        """
        for item, caption in self._captions.items():
            caption.setText(translator.text(item=item))
        for link, hint in (
            (self.cpu, UiText.CPU_HINT),
            (self.gpu, UiText.GPU_HINT),
            (self.resolution, UiText.RESOLUTION_HINT),
        ):
            link.setToolTip(translator.text(item=hint))

    def show_hardware(self, *, hardware: HardwareView) -> None:
        """
        Show the CPU, GPU and resolution in use and the memory sizes.

        :param hardware: what to show
        :return: None
        """
        links: tuple[tuple[QLabel, str], ...] = (
            (self.cpu, hardware.cpu),
            (self.gpu, hardware.gpu),
            (self.resolution, hardware.resolution),
        )
        for link, text in links:
            link.setText(f'<a href="choose">{html.escape(text)}</a>')
        self._memory.setText(hardware.memory)
        self._video_memory.setText(hardware.video_memory)

    def _caption(self) -> QLabel:
        """
        Make a caption in the dimmed text color of the palette.

        :return: the caption
        """
        label: QLabel = QLabel(parent=self)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        return label

    def _value(self) -> QLabel:
        """
        Make a value label.

        :return: the label
        """
        label: QLabel = QLabel(parent=self)
        label.setFont(Typography.strong(base=self.font()))
        return label

    def _link(self, *, on_click: Callable[[], None]) -> QLabel:
        """
        Make a value label shown as a link that opens a choice.

        :param on_click: called when the link is clicked
        :return: the label
        """
        label: QLabel = self._value()
        label.setTextFormat(Qt.TextFormat.RichText)
        # Combined as ints: PyCharm misreads the operand types of Flag.__or__.
        flags: Qt.TextInteractionFlag = Qt.TextInteractionFlag(
            Qt.TextInteractionFlag.LinksAccessibleByMouse.value | Qt.TextInteractionFlag.LinksAccessibleByKeyboard.value
        )
        label.setTextInteractionFlags(flags)
        label.linkActivated.connect(lambda _: on_click())
        return label


class _TopBar(QWidget):
    """The hardware block, and the button that opens the settings menu in the corner."""

    def __init__(
        self,
        *,
        on_cpu: Callable[[], None],
        on_gpu: Callable[[], None],
        on_resolution: Callable[[], None],
        on_settings: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the bar.

        :param on_cpu: called when the user opens the CPU choice
        :param on_gpu: called when the user opens the GPU choice
        :param on_resolution: called when the user opens the resolution choice
        :param on_settings: called when the user opens the settings menu
        :param parent: widget the bar belongs to
        """
        super().__init__(parent)
        layout: QHBoxLayout = QHBoxLayout(self)
        self.hardware: _HardwareBlock = _HardwareBlock(
            on_cpu=on_cpu, on_gpu=on_gpu, on_resolution=on_resolution, parent=self
        )
        self.settings: IconButton = IconButton(symbol="settings", parent=self)
        self.settings.clicked.connect(on_settings)
        layout.addWidget(self.hardware)
        layout.addStretch(1)
        layout.addWidget(self.settings, alignment=Qt.AlignmentFlag.AlignTop)

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the bar.

        :param translator: translator of the UI language
        :return: None
        """
        self.hardware.apply_language(translator=translator)
        self.settings.setToolTip(translator.text(item=UiText.SETTINGS))


class _StatusLine(QLabel):
    """The status line: an informing line in the placeholder text color, a warning in yellow, an error in red."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        """
        Build an empty informing line.

        :param parent: widget the line belongs to
        """
        super().__init__(parent)
        self._level: StatusLevel = StatusLevel.INFO
        self.setForegroundRole(QPalette.ColorRole.PlaceholderText)

    def show_status(self, *, text: str, level: StatusLevel) -> None:
        """
        Show a line in the color of its level.

        :param text: the line, empty to clear it
        :param level: how serious the line is
        :return: None
        """
        self._level = level
        self.setText(text)
        self.recolor()

    def recolor(self) -> None:
        """
        Color the text for its level on the background of the parent, e.g. again after a theme switch.

        :return: None
        """
        # The own style sheet keeps the line's palette from following its parent's background.
        backdrop: QWidget = self.parentWidget() or self
        color: str | None = Theme.status_color(
            level=self._level, background=backdrop.palette().color(QPalette.ColorRole.Window)
        )
        sheet: str = "" if color is None else f"color:{color}"
        if sheet != self.styleSheet():
            self.setStyleSheet(sheet)


class MainWindow(QWidget):  # pylint: disable=too-many-instance-attributes
    """The main window; user actions go to the presenter set with attach(), which fills the widgets in turn."""

    def __init__(self, *, log_lines: Queue[str]) -> None:
        """
        Build every widget; texts are set by apply_language(), the color scheme by apply_theme().

        :param log_lines: formatted log lines for the log panel
        """
        super().__init__()
        self._presenter: Presenter | None = None
        self._translator: Translator | None = None
        self._theme: ThemeMode = ThemeMode.AUTO
        self._auto_update: bool = True
        self.setWindowTitle(APP_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        layout: QVBoxLayout = QVBoxLayout(self)

        self._top: _TopBar = _TopBar(
            on_cpu=lambda: self._call(action=Presenter.open_cpu_choice),
            on_gpu=lambda: self._call(action=Presenter.open_gpu_choice),
            on_resolution=lambda: self._call(action=Presenter.open_resolution_choice),
            on_settings=self._open_settings,
            parent=self,
        )
        layout.addWidget(self._top)

        self._games: GamesPanel = GamesPanel(
            on_select_installed=lambda index: self._call(
                action=lambda presenter: presenter.select_installed_game(index=index)
            ),
            on_select=lambda index: self._call(action=lambda presenter: presenter.select_game(index=index)),
            on_search=lambda text: self._call(action=lambda presenter: presenter.search_games(text=text)),
            on_find=lambda: self._call(action=Presenter.find_games),
            on_add_folder=lambda folder: self._call(action=lambda presenter: presenter.add_folder(folder=folder)),
            on_change_folder=lambda position, folder: self._call(
                action=lambda presenter: presenter.change_folder(position=position, folder=folder)
            ),
            on_remove_folder=lambda position: self._call(
                action=lambda presenter: presenter.remove_folder(position=position)
            ),
            on_tab=lambda tab: self._call(action=lambda presenter: presenter.select_tab(tab=tab)),
            parent=self,
        )
        self._cover: CoverView = CoverView(parent=self)
        self._settings: _SettingsPanel = _SettingsPanel(
            on_slider=lambda index: self._call(action=lambda presenter: presenter.move_slider(index=index)),
            on_optimal=lambda: self._call(action=Presenter.back_to_optimal),
            parent=self,
        )
        self._settings_skeleton: SettingsSkeleton = SettingsSkeleton(parent=self)
        self._settings_area: QStackedWidget = QStackedWidget(parent=self)
        self._settings_area.addWidget(self._settings_skeleton)
        self._settings_area.addWidget(self._settings)
        layout.addLayout(self._body(), stretch=1)

        bottom: QHBoxLayout = QHBoxLayout()
        self._status: _StatusLine = _StatusLine(parent=self)
        self._logs_button: QPushButton = QPushButton(parent=self)
        self._logs_button.clicked.connect(self._toggle_logs)
        bottom.addWidget(self._status, stretch=1)
        bottom.addWidget(self._logs_button)
        layout.addLayout(bottom)
        self._log_panel: LogPanel = LogPanel(lines=log_lines, parent=self)
        self._log_panel.hide()
        layout.addWidget(self._log_panel)

    def _body(self) -> QHBoxLayout:
        """
        Lay out the middle of the window: the game tabs and the cover take one half, the settings the other.

        :return: the layout
        """
        # Keeps the cover level with the top of the tab pages: the tab bar's height is known only once styled.
        self._cover_gap: QWidget = QWidget(parent=self)
        self._games.tabBar().installEventFilter(self)
        cover: QVBoxLayout = QVBoxLayout()
        cover.addWidget(self._cover_gap)
        cover.addWidget(self._cover)
        cover.addStretch(1)
        games: QHBoxLayout = QHBoxLayout()
        games.addWidget(self._games, stretch=1)
        games.addSpacing(Typography.px(ems=GAP * 2))
        games.addLayout(cover)
        body: QHBoxLayout = QHBoxLayout()
        body.addLayout(games, stretch=1)
        body.addSpacing(Typography.px(ems=GAP * 3))
        body.addWidget(self._settings_area, stretch=1)
        return body

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """
        Recolor the status line when the palette changes, e.g. on a switch between the light and the dark theme.

        :param event: the change
        :return: None
        """
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._status.recolor()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """
        Keep the gap above the cover as tall as the tab bar.

        :param watched: object the event is for
        :param event: the event
        :return: False, so the event goes on as usual
        """
        if watched is self._games.tabBar() and event.type() == QEvent.Type.Resize:
            self._cover_gap.setFixedHeight(self._games.tabBar().height())
        return super().eventFilter(watched, event)

    def attach(self, *, presenter: Presenter) -> None:
        """
        Send the user actions to the presenter.

        :param presenter: presenter of this window
        :return: None
        """
        self._presenter = presenter

    def apply_theme(self, *, mode: ThemeMode) -> None:
        """
        Switch the color scheme; AUTO follows the Windows app mode, also when it changes later.

        :param mode: theme mode
        :return: None
        """
        self._theme = mode
        Theme.apply(mode=mode)

    def show_auto_update(self, *, enabled: bool) -> None:
        """
        Keep whether the database is updated automatically, for the settings menu.

        :param enabled: True when it is
        :return: None
        """
        self._auto_update = enabled

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the window: labels, buttons, headings.

        :param translator: translator of the UI language
        :return: None
        """
        self._translator = translator
        self._top.apply_language(translator=translator)
        self._games.apply_language(translator=translator)
        self._settings.apply_language(translator=translator)
        self._logs_button.setText(
            translator.text(item=UiText.HIDE_LOGS if self._log_panel.isVisible() else UiText.SHOW_LOGS)
        )

    def show_hardware(self, *, hardware: HardwareView) -> None:
        """
        Show the CPU, GPU and resolution in use and the memory sizes.

        :param hardware: what to show
        :return: None
        """
        self._top.hardware.show_hardware(hardware=hardware)

    def offer_cpus(self, *, choice: ChoiceView) -> None:
        """
        Open the CPU choice under the CPU link; a pick is passed to the presenter.

        :param choice: CPUs to choose from
        :return: None
        """
        self._offer(
            anchor=self._top.hardware.cpu,
            choice=choice,
            on_choose=lambda position: self._call(action=lambda presenter: presenter.choose_cpu(position=position)),
        )

    def offer_gpus(self, *, choice: ChoiceView) -> None:
        """
        Open the GPU choice under the GPU link; a pick is passed to the presenter.

        :param choice: GPUs to choose from
        :return: None
        """
        self._offer(
            anchor=self._top.hardware.gpu,
            choice=choice,
            on_choose=lambda position: self._call(action=lambda presenter: presenter.choose_gpu(position=position)),
        )

    def offer_resolutions(self, *, choice: ChoiceView) -> None:
        """
        Open the resolution choice under the resolution link; a pick is passed to the presenter.

        :param choice: resolutions to choose from
        :return: None
        """
        self._offer(
            anchor=self._top.hardware.resolution,
            choice=choice,
            on_choose=lambda position: self._call(
                action=lambda presenter: presenter.choose_resolution(position=position)
            ),
        )

    def show_status(self, *, text: str, level: StatusLevel) -> None:
        """
        Show progress, a warning or an error, colored by how serious it is; an empty text clears the line.

        :param text: the line to show
        :param level: how serious the line is
        :return: None
        """
        self._status.show_status(text=text, level=level)

    def warn(self, *, text: str) -> None:
        """
        Show a warning in a dialog the user closes with OK.

        :param text: the warning
        :return: None
        """
        QMessageBox.warning(self, APP_TITLE, text)

    def show_games(self, *, names: Sequence[str], selected: int | None) -> None:
        """
        Fill the list of all games.

        :param names: display names in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """
        self._games.all.list.fill(items=names, selected=selected)

    def show_finding(self) -> None:
        """
        Show the moving skeleton in place of the installed games.

        :return: None
        """
        self._games.installed.show_finding()

    def show_installed_games(self, *, games: Sequence[InstalledGameView], selected: int | None) -> None:
        """
        Fill the list of installed games; an empty list invites the user to add a folder.

        :param games: installed games in list order
        :param selected: position of the chosen game, None when it is not in the list
        :return: None
        """
        self._games.installed.show_games(games=games, selected=selected)

    def show_tab(self, *, tab: GamesTab) -> None:
        """
        Bring a game tab to the front.

        :param tab: the tab
        :return: None
        """
        self._games.show_tab(tab=tab)

    def show_folders(self, *, folders: Sequence[str]) -> None:
        """
        Show the folders searched for games.

        :param folders: folders in the user's order
        :return: None
        """
        self._games.installed.show_folders(folders=folders)

    def show_cover(self, *, picture: Path | None) -> None:
        """
        Show the box art of the chosen game.

        :param picture: the picture file, None for a placeholder when the game has none
        :return: None
        """
        self._cover.show_picture(path=picture)

    def clear_cover(self, *, loading: bool) -> None:
        """
        Show a skeleton instead of the box art.

        :param loading: True while the picture is on its way, False when no game is chosen
        :return: None
        """
        self._cover.clear(loading=loading)

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """
        self._settings_skeleton.set_active(active=False)
        self._settings.show_settings(settings=settings)
        self._settings_area.setCurrentWidget(self._settings)

    def clear_settings(self, *, loading: bool) -> None:
        """
        Show the skeleton instead of the settings.

        :param loading: True while the settings are requested, False when there are none to wait for
        :return: None
        """
        self._settings.clear()
        self._settings_area.setCurrentWidget(self._settings_skeleton)
        self._settings_skeleton.set_active(active=loading)

    def _offer(self, *, anchor: QWidget, choice: ChoiceView, on_choose: Callable[[int], None]) -> None:
        """
        Open a drop-down choice under a widget; an empty choice opens nothing.

        :param anchor: widget the list drops from
        :param choice: items to choose from
        :param on_choose: called with the position of the item picked
        :return: None
        """
        if not choice.detected and not any(group.items for group in choice.groups):
            return
        translator: Translator | None = self._translator
        popup: ChoicePopup = ChoicePopup(
            parent=self,
            choice=choice,
            search_hint="" if translator is None else translator.text(item=UiText.SEARCH),
            detected_mark="" if translator is None else translator.text(item=UiText.DETECTED),
            on_choose=on_choose,
        )
        popup.move(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        popup.show()

    def _open_settings(self) -> None:
        """
        Open the settings menu under the settings button, its right edge at the button's; picks go to the presenter.

        :return: None
        """
        if self._translator is None:
            return
        menu: SettingsMenu = SettingsMenu(
            parent=self,
            translator=self._translator,
            theme=self._theme,
            auto_update=self._auto_update,
            on_theme=lambda mode: self._call(action=lambda presenter: presenter.change_theme(mode=mode)),
            on_language=lambda code: self._call(action=lambda presenter: presenter.change_language(language=code)),
            on_auto_update=lambda enabled: self._call(
                action=lambda presenter: presenter.change_auto_update(enabled=enabled)
            ),
        )
        menu.adjustSize()
        corner: QPoint = self._top.settings.mapToGlobal(self._top.settings.rect().bottomRight())
        menu.move(corner.x() - menu.width(), corner.y())
        menu.show()

    def _call(self, *, action: Callable[[Presenter], None]) -> None:
        """
        Run a presenter action once the presenter is connected.

        :param action: the action
        :return: None
        """
        if self._presenter is not None:
            action(self._presenter)

    def _toggle_logs(self) -> None:
        """
        Show or hide the log panel.

        :return: None
        """
        shown: bool = not self._log_panel.isVisible()
        self._log_panel.setVisible(shown)
        if self._translator is not None:
            self._logs_button.setText(self._translator.text(item=UiText.HIDE_LOGS if shown else UiText.SHOW_LOGS))
