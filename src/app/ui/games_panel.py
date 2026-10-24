"""The game tabs: installed games with the folders searched for them, and all games with a search field."""

from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtCore import QFileInfo, QModelIndex, QSize, Qt
from PySide6.QtGui import QIcon, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n.translator import Translator
from app.i18n.ui_text import UiText
from app.ui.icons import IconButton
from app.ui.skeleton import ListSkeleton
from app.ui.views import InstalledGameView

__all__: tuple[str, ...] = ("GamesPanel",)

_PAD: int = 8
_ICON: int = 16
# Shares of the installed games tab's height: the games above, the folders below.
_GAMES_SHARE: int = 3
_FOLDERS_SHARE: int = 2


class _ChoiceList(QListView):
    """A single-choice list, its items optionally with icons."""

    def __init__(self, *, on_select: Callable[[int], None], parent: QWidget | None = None) -> None:
        """
        Build an empty list.

        :param on_select: called with the position of the item the user (or fill) selects
        :param parent: widget the list belongs to
        """
        super().__init__(parent)
        self._model: QStandardItemModel = QStandardItemModel(parent=self)
        self.setModel(self._model)
        self.setUniformItemSizes(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.selectionModel().currentChanged.connect(
            # A refill or a cleared selection makes no item current, which is no choice.
            lambda current, _: on_select(current.row()) if current.isValid() else None
        )

    def fill(self, *, items: Sequence[str], selected: int | None, icons: Sequence[QIcon] = ()) -> None:
        """
        Replace the items and select one of them.

        :param items: new items
        :param selected: position to select and scroll to, None for none
        :param icons: icon of each item, none for no icons
        :return: None
        """
        self._model.clear()
        for position, text in enumerate(items):
            item: QStandardItem = QStandardItem(text)
            if icons:
                item.setIcon(icons[position])
            self._model.appendRow(item)
        self.select(position=selected)

    def select(self, *, position: int | None) -> None:
        """
        Select an item and scroll to it, or clear the selection keeping the scroll position.

        :param position: position of the item, None for none
        :return: None
        """
        if position is None:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            return
        index: QModelIndex = self._model.index(position, 0)
        self.setCurrentIndex(index)
        self.scrollTo(index, hint=QAbstractItemView.ScrollHint.EnsureVisible)


class _InstalledTab(QWidget):  # pylint: disable=too-many-instance-attributes
    """The installed games over the folders searched for them, with the buttons that change the folders."""

    def __init__(
        self,
        *,
        on_select: Callable[[int], None],
        on_find: Callable[[], None],
        on_add: Callable[[str], None],
        on_change: Callable[[int, str], None],
        on_remove: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the tab with the skeleton in place of the games.

        :param on_select: called with the position of the game chosen
        :param on_find: called when the user asks to search again
        :param on_add: called with a folder the user picked to add
        :param on_change: called with the position of a folder and the one the user picked instead
        :param on_remove: called with the position of the folder to remove
        :param parent: widget the tab belongs to
        """
        super().__init__(parent)
        self._on_add: Callable[[str], None] = on_add
        self._on_change: Callable[[int, str], None] = on_change
        self._on_remove: Callable[[int], None] = on_remove
        self._dialog_title: str = ""
        self._icons: dict[Path, QIcon] = {}
        self._icon_provider: QFileIconProvider = QFileIconProvider()
        self.skeleton: ListSkeleton = ListSkeleton(icons=True, parent=self)
        self.list: _ChoiceList = _ChoiceList(on_select=on_select, parent=self)
        self.list.setIconSize(QSize(_ICON, _ICON))
        self._empty: QLabel = QLabel(parent=self)
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty.setMargin(_PAD * 2)
        self.pages: QStackedWidget = QStackedWidget(parent=self)
        for page in (self.skeleton, self.list, self._empty):
            self.pages.addWidget(page)
        self._caption: QLabel = QLabel(parent=self)
        self._caption.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.folder_list: QListWidget = QListWidget(parent=self)
        self.folder_list.currentRowChanged.connect(lambda _: self._update_buttons())
        self.add: IconButton = IconButton(symbol="plus", parent=self)
        self.add.clicked.connect(self._add)
        self.remove: IconButton = IconButton(symbol="minus", parent=self)
        self.remove.clicked.connect(lambda: self._on_remove(self.folder_list.currentRow()))
        self.change: IconButton = IconButton(symbol="pencil", parent=self)
        self.change.clicked.connect(self._change)
        self.find_again: IconButton = IconButton(symbol="refresh-cw", parent=self)
        self.find_again.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.find_again.clicked.connect(on_find)
        self._lay_out()
        self._update_buttons()

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the fixed texts of the tab.

        :param translator: translator of the UI language
        :return: None
        """
        self._empty.setText(translator.text(item=UiText.NO_GAMES_FOUND))
        self._caption.setText(translator.text(item=UiText.GAME_FOLDERS))
        self._dialog_title = translator.text(item=UiText.CHOOSE_FOLDER)
        self.add.setToolTip(translator.text(item=UiText.ADD_FOLDER))
        self.remove.setToolTip(translator.text(item=UiText.REMOVE_FOLDER))
        self.change.setToolTip(translator.text(item=UiText.CHANGE_FOLDER))
        self.find_again.setText(translator.text(item=UiText.FIND_AGAIN))

    def show_finding(self) -> None:
        """
        Show the moving skeleton in place of the games.

        :return: None
        """
        self.pages.setCurrentWidget(self.skeleton)
        self.skeleton.set_active(active=True)

    def show_games(self, *, games: Sequence[InstalledGameView], selected: int | None) -> None:
        """
        Show the installed games with the icons of their executables, or the invitation to add a folder.

        :param games: installed games in list order
        :param selected: position of the chosen game, None for none
        :return: None
        """
        self.skeleton.set_active(active=False)
        self.list.fill(
            items=[game.name for game in games],
            selected=selected,
            icons=[self._icon(executable=game.executable) for game in games],
        )
        self.pages.setCurrentWidget(self.list if games else self._empty)

    def show_folders(self, *, folders: Sequence[str]) -> None:
        """
        Show the folders searched for games, keeping the selected position.

        :param folders: folders in the user's order
        :return: None
        """
        row: int = self.folder_list.currentRow()
        self.folder_list.clear()
        self.folder_list.addItems(list(folders))
        if folders:
            self.folder_list.setCurrentRow(min(max(row, 0), len(folders) - 1))
        self._update_buttons()

    def _icon(self, *, executable: Path) -> QIcon:
        """
        Get the icon of an executable once.

        :param executable: the file
        :return: its icon as Windows shows it
        """
        if executable not in self._icons:
            self._icons[executable] = self._icon_provider.icon(QFileInfo(str(executable)))
        return self._icons[executable]

    def _add(self) -> None:
        """
        Let the user pick a folder to add in the Windows folder dialog.

        :return: None
        """
        folder: str = QFileDialog.getExistingDirectory(self, self._dialog_title)
        if folder:
            self._on_add(folder)

    def _change(self) -> None:
        """
        Let the user pick a folder in place of the selected one, the dialog opened at it.

        :return: None
        """
        row: int = self.folder_list.currentRow()
        if row < 0:  # pragma: no cover
            return
        folder: str = QFileDialog.getExistingDirectory(self, self._dialog_title, self.folder_list.item(row).text())
        if folder:
            self._on_change(row, folder)

    def _update_buttons(self) -> None:
        """
        Allow changing and removing a folder only while one is selected.

        :return: None
        """
        selected: bool = self.folder_list.currentRow() >= 0
        self.remove.setEnabled(selected)
        self.change.setEnabled(selected)

    def _lay_out(self) -> None:
        """
        Place the games above the folders, the folder buttons under them.

        :return: None
        """
        buttons: QHBoxLayout = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        for button in (self.add, self.remove, self.change):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.find_again)
        lower: QVBoxLayout = QVBoxLayout()
        lower.addWidget(self._caption)
        lower.addWidget(self.folder_list, stretch=1)
        lower.addLayout(buttons)
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.addWidget(self.pages, stretch=_GAMES_SHARE)
        layout.addSpacing(_PAD)
        layout.addLayout(lower, stretch=_FOLDERS_SHARE)


class _AllTab(QWidget):
    """Every game with the search field above it."""

    def __init__(
        self, *, on_search: Callable[[str], None], on_select: Callable[[int], None], parent: QWidget | None = None
    ) -> None:
        """
        Build the tab.

        :param on_search: called with the search text on every change
        :param on_select: called with the position of the game chosen
        :param parent: widget the tab belongs to
        """
        super().__init__(parent)
        self.search: QLineEdit = QLineEdit(parent=self)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(on_search)
        self.list: _ChoiceList = _ChoiceList(on_select=on_select, parent=self)
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.addWidget(self.search)
        layout.addWidget(self.list, stretch=1)


class GamesPanel(QTabWidget):
    """Two tabs: the games installed on this computer, and all games NVIDIA has presets for."""

    def __init__(
        self,
        *,
        on_select_installed: Callable[[int], None],
        on_select: Callable[[int], None],
        on_search: Callable[[str], None],
        on_find: Callable[[], None],
        on_add_folder: Callable[[str], None],
        on_change_folder: Callable[[int, str], None],
        on_remove_folder: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build both tabs, the installed games first.

        :param on_select_installed: called with the position of an installed game chosen
        :param on_select: called with the position of a game chosen in the list of all games
        :param on_search: called with the search text on every change
        :param on_find: called when the user asks to search for installed games again
        :param on_add_folder: called with a folder to add
        :param on_change_folder: called with the position of a folder and the one to put in its place
        :param on_remove_folder: called with the position of a folder to remove
        :param parent: widget the panel belongs to
        """
        super().__init__(parent)
        self.installed: _InstalledTab = _InstalledTab(
            on_select=on_select_installed,
            on_find=on_find,
            on_add=on_add_folder,
            on_change=on_change_folder,
            on_remove=on_remove_folder,
            parent=self,
        )
        self.all: _AllTab = _AllTab(on_search=on_search, on_select=on_select, parent=self)
        self.addTab(self.installed, "")
        self.addTab(self.all, "")

    def apply_language(self, *, translator: Translator) -> None:
        """
        Translate the tab names and the fixed texts of the tabs.

        :param translator: translator of the UI language
        :return: None
        """
        self.setTabText(self.indexOf(self.installed), translator.text(item=UiText.MY_GAMES))
        self.setTabText(self.indexOf(self.all), translator.text(item=UiText.ALL_GAMES))
        self.installed.apply_language(translator=translator)
        self.all.search.setPlaceholderText(translator.text(item=UiText.SEARCH))

    def select(self, *, position: int | None, installed_position: int | None) -> None:
        """
        Select the chosen game in both lists without refilling them.

        :param position: position in the list of all games, None to clear its selection
        :param installed_position: position in the list of installed games, None to clear its selection
        :return: None
        """
        self.all.list.select(position=position)
        self.installed.list.select(position=installed_position)
