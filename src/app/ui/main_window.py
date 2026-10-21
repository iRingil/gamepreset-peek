"""Widgets and layout of the main window and of the GPU choice dialog."""

import html
from queue import Queue
from typing import Callable, Sequence

from PySide6.QtCore import QEvent, QModelIndex, QPersistentModelIndex, QRect, QStringListModel, Qt
from PySide6.QtGui import QFont, QHelpEvent, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_TITLE, LANGUAGE_NAMES, WINDOW_MIN_SIZE, WINDOW_SIZE
from app.core.models import ThemeMode
from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.icons import Icons
from app.ui.log_panel import LogPanel
from app.ui.presenter import Hint, Presenter, ResolutionRow, SettingsView
from app.ui.theme import Theme

__all__: tuple[str, ...] = ("MainWindow",)

_PAD: int = 8
_GAMES_WIDTH: int = 300
_RESOLUTIONS_WIDTH: int = 230
_VALUE_WIDTH: int = 220
_GPU_LIST_SIZE: tuple[int, int] = (460, 320)
_ICON_SIZE: int = 18
# Point size steps above the base font: the GPU line, the settings title and the preset position.
_HEADLINE_STEP: float = 2
_TITLE_STEP: float = 6
_BIG_STEP: float = 10
# Item data role of the settings table telling that a value differs from the recommended preset.
_CHANGED_ROLE: int = Qt.ItemDataRole.UserRole + 1


class _Fonts:
    """Fonts derived from the application font: bold and larger ones for headings."""

    @staticmethod
    def derived(*, base: QFont, step: float = 0, bold: bool = False) -> QFont:
        """
        Make a font from the base one.

        :param base: font to start from
        :param step: points to add to its size
        :param bold: True for bold
        :return: the font
        """
        font: QFont = QFont(base)
        font.setPointSizeF(base.pointSizeF() + step)
        font.setBold(bold)
        return font


class _SignDelegate(QStyledItemDelegate):
    """Draws a warning sign one space after the text of a list item; its hint pops up over the sign only."""

    def __init__(self, *, parent: QListView, warnings: Callable[[], dict[int, Hint]]) -> None:
        """
        Prepare the sign; its pixels are drawn once for each screen scale met.

        :param parent: list the delegate draws
        :param warnings: gives the hint of the sign of each row that has one
        """
        super().__init__(parent)
        self._warnings: Callable[[], dict[int, Hint]] = warnings
        self._signs: dict[float, QPixmap] = {}

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        """
        Draw the item, then its sign when it has one.

        :param painter: painter of the list
        :param option: item style
        :param index: item
        :return: None
        """
        super().paint(painter, option, index)
        if index.row() in self._warnings():
            sign: QRect = self._sign_rect(option=option, index=index)
            painter.drawPixmap(sign.topLeft(), self._sign(scale=painter.device().devicePixelRatioF()))

    def helpEvent(  # pylint: disable=invalid-name
        self,
        event: QHelpEvent,
        view: QAbstractItemView,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        """
        Show the hint of the sign while the pointer is over it, and no tooltip anywhere else.

        :param event: tooltip request
        :param view: the list
        :param option: item style
        :param index: item under the pointer
        :return: True: the request is handled here
        """
        hint: Hint | None = self._warnings().get(index.row())
        sign: QRect = self._sign_rect(option=option, index=index)
        if event.type() == QEvent.Type.ToolTip and hint is not None and sign.contains(event.pos()):
            text: str = f"<b>{html.escape(hint.title)}</b><br>{html.escape(hint.text)}"
            QToolTip.showText(event.globalPos(), text, view, sign)
        else:
            QToolTip.hideText()
        return True

    def _sign_rect(self, *, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QRect:
        """
        Locate the sign of an item: a space after the end of its text, centered on the row.

        :param option: item style
        :param index: item
        :return: rectangle of the sign in list coordinates
        """
        item: QStyleOptionViewItem = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        style: QStyle = item.widget.style() if item.widget is not None else QApplication.style()
        text: QRect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, item, item.widget)
        margin: int = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, item, item.widget) + 1
        left: int = text.left() + margin + item.fontMetrics.horizontalAdvance(item.text + " ")
        return QRect(left, item.rect.center().y() - _ICON_SIZE // 2 + 1, _ICON_SIZE, _ICON_SIZE)

    def _sign(self, *, scale: float) -> QPixmap:
        """
        Get the sign drawn for a screen scale.

        :param scale: device pixel ratio of the screen
        :return: the sign at its logical size
        """
        if scale not in self._signs:
            sign: QPixmap = QPixmap()
            sign.loadFromData(Icons.warning(size=round(_ICON_SIZE * scale)))
            sign.setDevicePixelRatio(scale)
            self._signs[scale] = sign
        return self._signs[scale]


class _ChoiceList(QListView):
    """A single-choice list; given warnings, an item can carry a warning sign whose hint pops up over the sign."""

    def __init__(self, *, on_select: Callable[[int], None], parent: QWidget | None = None) -> None:
        """
        Build an empty list.

        :param on_select: called with the position of the item the user (or fill) selects
        :param parent: widget the list belongs to
        """
        super().__init__(parent)
        self._model: QStringListModel = QStringListModel(parent=self)
        self.setModel(self._model)
        self.setUniformItemSizes(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._warnings: dict[int, Hint] = {}
        self.setItemDelegate(_SignDelegate(parent=self, warnings=lambda: self._warnings))
        self.selectionModel().currentChanged.connect(
            # A refill resets the current item to none, which is no choice.
            lambda current, _: on_select(current.row()) if current.isValid() else None
        )

    def fill(self, *, items: Sequence[str], selected: int | None = None, warnings: Sequence[Hint | None] = ()) -> None:
        """
        Replace the items and select one of them.

        :param items: new items
        :param selected: position to select and scroll to, None for none
        :param warnings: hint of the warning sign of each item, None for no sign
        :return: None
        """
        self._warnings = {position: hint for position, hint in enumerate(warnings) if hint is not None}
        self._model.setStringList(list(items))
        if selected is not None:
            index: QModelIndex = self._model.index(selected)
            self.setCurrentIndex(index)
            self.scrollTo(index, hint=QAbstractItemView.ScrollHint.EnsureVisible)

    def count(self) -> int:
        """
        Count the items.

        :return: number of items
        """
        return self._model.rowCount()

    def selection(self) -> int | None:
        """
        Get the selected position.

        :return: position, None when nothing is selected
        """
        rows: list[QModelIndex] = self.selectionModel().selectedIndexes()
        return rows[0].row() if rows else None


class _GpuDialog(QDialog):
    """Modal list of GPUs to pick one from."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        parent: QWidget,
        translator: Translator,
        message: str,
        names: Sequence[str],
        selected: int | None,
    ) -> None:
        """
        Build the dialog.

        :param parent: main window
        :param translator: translator of the UI language
        :param message: why the user has to choose
        :param names: GPU names in list order
        :param selected: position preselected in the list, None for none
        """
        super().__init__(parent)
        self.setWindowTitle(translator.text(item=UiText.CHOOSE_GPU_TITLE))
        layout: QVBoxLayout = QVBoxLayout(self)
        label: QLabel = QLabel(message, parent=self)
        label.setWordWrap(True)
        layout.addWidget(label)
        self._buttons: QDialogButtonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        self._ok: QPushButton = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok.setText(translator.text(item=UiText.OK))
        self._ok.setEnabled(False)
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(translator.text(item=UiText.CANCEL))
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self.reject)
        self._list: _ChoiceList = _ChoiceList(on_select=lambda _: self._ok.setEnabled(True), parent=self)
        self._list.setMinimumSize(*_GPU_LIST_SIZE)
        self._list.doubleClicked.connect(lambda _: self._accept())
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(self._buttons)
        self._list.fill(items=names, selected=selected)
        self._list.setFocus()

    def choice(self) -> int | None:
        """
        Show the dialog and wait until it is closed.

        :return: position of the chosen GPU, None when the user cancelled
        """
        return self._list.selection() if self.exec() == QDialog.DialogCode.Accepted else None

    def _accept(self) -> None:
        """
        Close the dialog with the selected GPU, if there is one.

        :return: None
        """
        if self._list.selection() is not None:
            self.accept()


class _ChangedDelegate(QStyledItemDelegate):
    """Draws the values that differ from the recommended preset in bold and in the accent color of the palette.

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
            option.palette.setColor(QPalette.ColorRole.Text, option.palette.color(QPalette.ColorRole.Accent))


class _SettingsPanel(QWidget):  # pylint: disable=too-many-instance-attributes
    """The game and resolution title, the "Show settings" button, the quality slider and the settings table.

    Rows whose value differs from the recommended preset are emphasized: that is what the slider trades."""

    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        on_slider: Callable[[int], None],
        on_optimal: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the panel with the slider and the table hidden.

        :param on_show: called when the user asks for the settings
        :param on_slider: called with the 1-based preset index when the user moves the slider
        :param on_optimal: called when the user asks for the recommended preset
        :param parent: widget the panel belongs to
        """
        super().__init__(parent)
        self._on_slider: Callable[[int], None] = on_slider
        self._index: int = 0
        self._title: QLabel = QLabel(parent=self)
        self._title.setFont(_Fonts.derived(base=self.font(), step=_TITLE_STEP, bold=True))
        self._subtitle: QLabel = self._muted(parent=self)
        self._position: QLabel = QLabel(parent=self)
        self._position.setFont(_Fonts.derived(base=self.font(), step=_BIG_STEP, bold=True))
        self._position.setForegroundRole(QPalette.ColorRole.Accent)
        self._caption: QLabel = self._muted(parent=self)
        self._button: QPushButton = QPushButton(parent=self)
        self._button.setDefault(True)
        self._button.clicked.connect(on_show)
        self._button.hide()
        self._slider_row: QWidget = QWidget(parent=self)
        self._slider_row.hide()
        self._performance: QLabel = self._muted(parent=self._slider_row)
        self._slider: QSlider = QSlider(Qt.Orientation.Horizontal, parent=self._slider_row)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setPageStep(1)
        self._slider.valueChanged.connect(self._moved)
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
        self._button.setText(translator.text(item=UiText.SHOW_SETTINGS))
        self._performance.setText(translator.text(item=UiText.PERFORMANCE))
        self._quality.setText(translator.text(item=UiText.QUALITY))
        self._optimal.setText(translator.text(item=UiText.BACK_TO_OPTIMAL))
        self._table.setHeaderLabels([translator.text(item=UiText.SETTING), translator.text(item=UiText.VALUE)])

    def show_button(self, *, visible: bool) -> None:
        """
        Show or hide the "Show settings" button.

        :param visible: True to show the button
        :return: None
        """
        self._button.setVisible(visible)

    def show_settings(self, *, settings: SettingsView) -> None:
        """
        Show the settings of a preset with the slider at its position.

        :param settings: what to show
        :return: None
        """
        self._index = settings.index
        self._title.setText(settings.title)
        self._subtitle.setText(settings.subtitle)
        self._position.setText(settings.position)
        self._caption.setText(settings.caption)
        # Set by the program, not by the user: no slider callback.
        self._slider.blockSignals(True)
        self._slider.setRange(1, max(settings.count, 2))
        self._slider.setValue(settings.index)
        self._slider.blockSignals(False)
        self._slider.setEnabled(settings.count > 1)
        self._optimal.setEnabled(not settings.optimal)
        self._table.clear()
        items: list[QTreeWidgetItem] = []
        for row in settings.rows:
            item: QTreeWidgetItem = QTreeWidgetItem([row.name, row.value])
            for column in range(2):
                item.setData(column, _CHANGED_ROLE, row.changed)
            items.append(item)
        self._table.addTopLevelItems(items)
        self._slider_row.show()
        self._table.show()

    def clear(self) -> None:
        """
        Hide the slider and the table.

        :return: None
        """
        for label in (self._title, self._subtitle, self._position, self._caption):
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
        header.resizeSection(1, _VALUE_WIDTH)
        table.hide()
        return table

    def _lay_out(self) -> None:
        """
        Place the widgets: the titles with the preset position right of them, the button, the slider row, the table.

        :return: None
        """
        titles: QVBoxLayout = QVBoxLayout()
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)
        titles.addStretch()
        preset: QVBoxLayout = QVBoxLayout()
        preset.addWidget(self._position, alignment=Qt.AlignmentFlag.AlignRight)
        preset.addWidget(self._caption, alignment=Qt.AlignmentFlag.AlignRight)
        head: QHBoxLayout = QHBoxLayout()
        head.addLayout(titles, stretch=1)
        head.addLayout(preset)
        slider: QHBoxLayout = QHBoxLayout(self._slider_row)
        slider.setContentsMargins(0, _PAD, 0, _PAD)
        slider.addWidget(self._performance)
        slider.addWidget(self._slider, stretch=1)
        slider.addWidget(self._quality)
        slider.addSpacing(_PAD * 2)
        slider.addWidget(self._optimal)
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignLeft)
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


class _TopBar(QWidget):
    """The GPU in use with the button to change it, and the theme and language choices."""

    def __init__(
        self,
        *,
        on_change_gpu: Callable[[], None],
        on_theme: Callable[[int], None],
        on_language: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the bar.

        :param on_change_gpu: called when the user wants another GPU
        :param on_theme: called with the position of the chosen theme
        :param on_language: called with the code of the chosen language
        :param parent: widget the bar belongs to
        """
        super().__init__(parent)
        layout: QHBoxLayout = QHBoxLayout(self)
        self._hardware: QLabel = QLabel(parent=self)
        self._hardware.setFont(_Fonts.derived(base=self.font(), step=_HEADLINE_STEP, bold=True))
        self._change_gpu: QPushButton = QPushButton(parent=self)
        self._change_gpu.clicked.connect(on_change_gpu)
        self._theme_label: QLabel = QLabel(parent=self)
        self._themes: QComboBox = QComboBox(parent=self)
        # Activated: chosen by the user, not set by the program.
        self._themes.activated.connect(on_theme)
        self._language_label: QLabel = QLabel(parent=self)
        self._language: QComboBox = QComboBox(parent=self)
        self._language.addItems(list(LANGUAGE_NAMES.values()))
        self._language.activated.connect(lambda index: on_language(list(LANGUAGE_NAMES)[index]))
        layout.addWidget(self._hardware, stretch=1)
        layout.addWidget(self._change_gpu)
        layout.addSpacing(_PAD * 2)
        layout.addWidget(self._theme_label)
        layout.addWidget(self._themes)
        layout.addSpacing(_PAD * 2)
        layout.addWidget(self._language_label)
        layout.addWidget(self._language)

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the bar and show the language in use.

        :param translator: translator of the UI language
        :return: None
        """
        self._change_gpu.setText(translator.text(item=UiText.CHANGE_GPU))
        self._theme_label.setText(translator.text(item=UiText.THEME))
        self._language_label.setText(translator.text(item=UiText.LANGUAGE))
        self._language.setCurrentIndex(list(LANGUAGE_NAMES).index(translator.language))

    def show_hardware(self, *, text: str) -> None:
        """
        Show the GPU in use or why there is none.

        :param text: the line to show
        :return: None
        """
        self._hardware.setText(text)

    def show_themes(self, *, names: Sequence[str], selected: int) -> None:
        """
        Fill the theme choice.

        :param names: theme names in list order
        :param selected: position of the theme in use
        :return: None
        """
        self._themes.clear()
        self._themes.addItems(list(names))
        self._themes.setCurrentIndex(selected)


class _GamesColumn(QWidget):
    """The game list with its search field and the button that requests the list again after a failure."""

    def __init__(
        self,
        *,
        on_search: Callable[[str], None],
        on_load: Callable[[], None],
        on_select: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the column with the "Load games" button hidden.

        :param on_search: called with the search text on every change
        :param on_load: called when the user asks for the game list again
        :param on_select: called with the position of the selected game
        :param parent: widget the column belongs to
        """
        super().__init__(parent)
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._title: QLabel = QLabel(parent=self)
        self._title.setFont(_Fonts.derived(base=self.font(), bold=True))
        self._search: QLineEdit = QLineEdit(parent=self)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(on_search)
        self._load: QPushButton = QPushButton(parent=self)
        self._load.clicked.connect(on_load)
        self._load.hide()
        self.list: _ChoiceList = _ChoiceList(on_select=on_select, parent=self)
        layout.addWidget(self._title)
        layout.addWidget(self._search)
        layout.addWidget(self._load)
        layout.addWidget(self.list, stretch=1)

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the column.

        :param translator: translator of the UI language
        :return: None
        """
        self._title.setText(translator.text(item=UiText.GAME))
        self._search.setPlaceholderText(translator.text(item=UiText.SEARCH))
        self._load.setText(translator.text(item=UiText.LOAD_GAMES))

    def show_load(self, *, visible: bool) -> None:
        """
        Show or hide the "Load games" button.

        :param visible: True to show the button
        :return: None
        """
        self._load.setVisible(visible)


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
        self.setWindowTitle(APP_TITLE)
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(*WINDOW_MIN_SIZE)
        layout: QVBoxLayout = QVBoxLayout(self)

        self._top: _TopBar = _TopBar(
            on_change_gpu=lambda: self._call(action=Presenter.change_gpu),
            on_theme=lambda index: self._call(action=lambda presenter: presenter.change_theme(index=index)),
            on_language=lambda code: self._call(action=lambda presenter: presenter.change_language(language=code)),
            parent=self,
        )
        layout.addWidget(self._top)

        body: QHBoxLayout = QHBoxLayout()
        self._games: _GamesColumn = _GamesColumn(
            on_search=lambda text: self._call(action=lambda presenter: presenter.search_games(text=text)),
            on_load=lambda: self._call(action=Presenter.load_games),
            on_select=lambda index: self._call(action=lambda presenter: presenter.select_game(index=index)),
            parent=self,
        )
        self._games.setFixedWidth(_GAMES_WIDTH)
        body.addWidget(self._games)
        body.addSpacing(_PAD)

        resolutions: QVBoxLayout = QVBoxLayout()
        self._resolutions_label: QLabel = QLabel(parent=self)
        self._resolutions_label.setFont(_Fonts.derived(base=self.font(), bold=True))
        self._resolutions: _ChoiceList = _ChoiceList(
            on_select=lambda index: self._call(action=lambda presenter: presenter.select_resolution(index=index)),
            parent=self,
        )
        self._resolutions.setFixedWidth(_RESOLUTIONS_WIDTH)
        resolutions.addWidget(self._resolutions_label)
        resolutions.addWidget(self._resolutions, stretch=1)
        body.addLayout(resolutions)
        body.addSpacing(_PAD * 2)

        self._settings: _SettingsPanel = _SettingsPanel(
            on_show=lambda: self._call(action=Presenter.show_settings),
            on_slider=lambda index: self._call(action=lambda presenter: presenter.move_slider(index=index)),
            on_optimal=lambda: self._call(action=Presenter.back_to_optimal),
            parent=self,
        )
        body.addWidget(self._settings, stretch=1)
        layout.addLayout(body, stretch=1)

        bottom: QHBoxLayout = QHBoxLayout()
        self._status: QLabel = QLabel(parent=self)
        self._status.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._logs_button: QPushButton = QPushButton(parent=self)
        self._logs_button.clicked.connect(self._toggle_logs)
        bottom.addWidget(self._status, stretch=1)
        bottom.addWidget(self._logs_button)
        layout.addLayout(bottom)
        self._log_panel: LogPanel = LogPanel(lines=log_lines, parent=self)
        self._log_panel.hide()
        layout.addWidget(self._log_panel)

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
        Theme.apply(mode=mode)

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
        self._resolutions_label.setText(translator.text(item=UiText.RESOLUTION))
        self._settings.apply_language(translator=translator)
        self._logs_button.setText(
            translator.text(item=UiText.HIDE_LOGS if self._log_panel.isVisible() else UiText.SHOW_LOGS)
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
        self._status.setText(text)

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

    def show_resolutions(self, *, items: Sequence[ResolutionRow]) -> None:
        """
        Fill the resolution list, keeping the selection when only the texts change (language switch).

        :param items: resolution rows in list order
        :return: None
        """
        selected: int | None = self._resolutions.selection()
        same: bool = self._resolutions.count() == len(items) > 0
        self._resolutions.fill(
            items=[item.resolution for item in items],
            selected=selected if same else None,
            warnings=[item.warning for item in items],
        )

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
        self._settings.show_settings(settings=settings)

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
            parent=self, translator=self._translator, message=message, names=names, selected=selected
        )
        return dialog.choice()

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
