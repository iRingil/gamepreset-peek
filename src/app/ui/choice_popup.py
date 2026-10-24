"""The drop-down choice of a CPU or a GPU, with a search over the bundled items."""

from typing import Callable, Sequence

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import Icons
from app.ui.theme import Theme
from app.ui.typography import Typography
from app.ui.views import ChoiceView

__all__: tuple[str, ...] = ("ChoicePopup",)

# Width and height of the list with bundled items, in ems.
_POPUP_SIZE: tuple[float, float] = (35, 28)
# Space between the check and the word of the detected mark, and before the mark, in ems.
_MARK_GAP: float = 0.35


class _DetectedDelegate(QStyledItemDelegate):
    """Draws a detected item with a green check and a word saying it was detected at its right end."""

    def __init__(self, *, mark: str, parent: QListWidget) -> None:
        """
        Use the word of the mark.

        :param mark: the translated word, e.g. "Detected"
        :param parent: the list of detected items
        """
        super().__init__(parent)
        self._mark: str = mark

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        """
        Draw the item as usual with its text shortened to leave room for the mark, then the mark.

        :param painter: painter of the list
        :param option: how to draw the item
        :param index: the item
        :return: None
        """
        item: QStyleOptionViewItem = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        widget: QWidget | None = item.widget
        style: QStyle = widget.style() if widget is not None else QApplication.style()
        gap: int = Typography.px(ems=_MARK_GAP)
        size: int = item.fontMetrics.height()
        word: int = item.fontMetrics.horizontalAdvance(self._mark)
        text: QRect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, item, widget)
        item.text = item.fontMetrics.elidedText(
            item.text, Qt.TextElideMode.ElideRight, text.width() - size - word - 3 * gap
        )
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, widget)
        painter.save()
        painter.setPen(item.palette.color(QPalette.ColorRole.PlaceholderText))
        word_box: QRect = QRect(text.right() - gap - word, text.top(), word, text.height())
        painter.drawText(word_box, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._mark)
        background: QColor = item.palette.color(QPalette.ColorRole.Base)
        Icons.symbol(
            name="circle-check",
            color=QColor(Theme.success_color(background=background)),
            ratio=widget.devicePixelRatio() if widget is not None else 1.0,
        ).paint(painter, QRect(word_box.left() - gap - size, text.center().y() - size // 2, size, size))
        painter.restore()


class ChoicePopup(QFrame):
    """A drop-down list under a link: detected items, a line, a search field, then the bundled items in tabs if several.

    A click or Enter on an item picks it and closes the list; a click outside closes it with no choice. The search
    filters the bundled items of every tab at once and opens a tab with matches when the open one has none."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        parent: QWidget,
        choice: ChoiceView,
        search_hint: str,
        detected_mark: str,
        on_choose: Callable[[int], None],
    ) -> None:
        """
        Build the list with the item in use selected; the search field takes the keys when there are bundled items.

        :param parent: window the list belongs to
        :param choice: items to choose from
        :param search_hint: placeholder text of the search field
        :param detected_mark: word marking the detected items, e.g. "Detected"
        :param on_choose: called with the position of the item picked
        """
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._on_choose: Callable[[int], None] = on_choose
        self._picked: bool = False
        self._groups: list[tuple[QListWidget, str]] = []
        self._tabs: QTabWidget | None = QTabWidget(parent=self) if len(choice.groups) > 1 else None
        self._search: QLineEdit = QLineEdit(parent=self)
        self._search.setPlaceholderText(search_hint)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter)
        self._search.returnPressed.connect(self._pick_current)
        layout: QVBoxLayout = QVBoxLayout(self)
        focus: QWidget | None = None
        offset: int = 0
        if choice.detected:
            detected: QListWidget = self._list(items=choice.detected, offset=offset, selected=choice.selected)
            detected.setObjectName("detected")
            detected.setItemDelegate(_DetectedDelegate(mark=detected_mark, parent=detected))
            # A long name is shortened instead: a scroll bar would take the height of the only row.
            detected.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            detected.setFixedHeight(detected.sizeHintForRow(0) * detected.count() + 2 * detected.frameWidth())
            layout.addWidget(detected)
            focus = detected
            offset += len(choice.detected)
        if choice.detected and choice.groups:
            line: QFrame = QFrame(parent=self)
            line.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(line)
        if choice.groups:
            layout.addWidget(self._search)
            focus = self._search
        else:
            self._search.hide()
        for group in choice.groups:
            items: QListWidget = self._list(items=group.items, offset=offset, selected=choice.selected)
            self._groups.append((items, group.title))
            if self._tabs is None:
                layout.addWidget(items, stretch=1)
            else:
                # The tab pane already draws a frame around the list
                items.setFrameShape(QFrame.Shape.NoFrame)
                self._tabs.addTab(items, group.title)
                if choice.selected is not None and 0 <= choice.selected - offset < len(group.items):
                    self._tabs.setCurrentWidget(items)
            offset += len(group.items)
        if self._tabs is not None:
            layout.addWidget(self._tabs, stretch=1)
        self.resize(
            Typography.px(ems=_POPUP_SIZE[0]),
            Typography.px(ems=_POPUP_SIZE[1]) if choice.groups else self.sizeHint().height(),
        )
        if focus is not None:
            focus.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """
        Move from the search field into the open list on the Down key; other keys are handled as usual.

        :param event: key the search field passed on
        :return: None
        """
        shown: QListWidget | None = self._shown()
        if event.key() == Qt.Key.Key_Down and self._search.hasFocus() and shown is not None:
            shown.setFocus()
        else:
            super().keyPressEvent(event)

    def _filter(self, text: str) -> None:
        """
        Hide the bundled items that don't match the search, count the matches in the tab titles, open a tab with any.

        :param text: search text; every word of it must occur in an item, ignoring case
        :return: None
        """
        words: list[str] = text.casefold().split()
        counts: list[int] = []
        for view, title in self._groups:
            count: int = 0
            for row in range(view.count()):
                item: QListWidgetItem = view.item(row)
                found: bool = all(word in item.text().casefold() for word in words)
                item.setHidden(not found)
                count += int(found)
            counts.append(count)
            current: QListWidgetItem | None = view.currentItem()
            if current is None or current.isHidden():
                first: QListWidgetItem | None = self._first_shown(view=view)
                if first is not None:
                    view.setCurrentItem(first)
            if view.currentItem() is not None:
                view.scrollToItem(view.currentItem(), QAbstractItemView.ScrollHint.EnsureVisible)
            if self._tabs is not None:
                self._tabs.setTabText(self._tabs.indexOf(view), f"{title} ({count})" if words else title)
        if self._tabs is not None and counts[self._tabs.currentIndex()] == 0 and any(counts):
            self._tabs.setCurrentIndex(next(index for index, count in enumerate(counts) if count))

    def _shown(self) -> QListWidget | None:
        """
        Get the list of bundled items in view: the one of the open tab, or the only one.

        :return: the list, None when there are no bundled items
        """
        if self._tabs is not None:
            return self._groups[self._tabs.currentIndex()][0]
        return self._groups[0][0] if self._groups else None

    @staticmethod
    def _first_shown(*, view: QListWidget) -> QListWidgetItem | None:
        """
        Find the first item of a list the search leaves visible.

        :param view: list of bundled items
        :return: the item, None when the search hides them all
        """
        return next((view.item(row) for row in range(view.count()) if not view.item(row).isHidden()), None)

    def _pick_current(self) -> None:
        """
        Pick the current item of the list in view on Enter in the search field, if the search leaves it visible.

        :return: None
        """
        shown: QListWidget | None = self._shown()
        current: QListWidgetItem | None = shown.currentItem() if shown is not None else None
        if shown is not None and current is not None and not current.isHidden():
            shown.itemActivated.emit(current)

    def _list(self, *, items: Sequence[str], offset: int, selected: int | None) -> QListWidget:
        """
        Make a list of items whose positions in the whole choice start at an offset.

        :param items: item texts
        :param offset: position of the first item in the whole choice
        :param selected: position of the item in use in the whole choice, None for none
        :return: the list
        """
        view: QListWidget = QListWidget(parent=self)
        view.setUniformItemSizes(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.addItems(list(items))
        if selected is not None and 0 <= selected - offset < len(items):
            view.setCurrentRow(selected - offset)
            view.scrollToItem(view.currentItem(), QAbstractItemView.ScrollHint.PositionAtCenter)
        view.itemClicked.connect(lambda item: self._pick(position=offset + view.row(item)))
        view.itemActivated.connect(lambda item: self._pick(position=offset + view.row(item)))
        return view

    def _pick(self, *, position: int) -> None:
        """
        Close the list and pass the item picked on; a second signal of the same pick is ignored.

        :param position: position of the item in the whole choice
        :return: None
        """
        if self._picked:
            return
        self._picked = True
        self.close()
        self._on_choose(position)
