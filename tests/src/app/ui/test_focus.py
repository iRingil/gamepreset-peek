"""Tests of app.ui.focus."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.focus import MouseFocus

__all__: tuple = ()


class TestMouseFocus:
    """Tests of MouseFocus."""

    @pytest.fixture(name="root")
    def _root(self, qt_app: QApplication) -> QWidget:
        """
        Build a widget with a text field, lists, buttons and tabs, as Qt makes them; the tree takes no focus.

        :param qt_app: Qt application
        :return: the widget
        """
        root: QWidget = QWidget()
        layout: QVBoxLayout = QVBoxLayout(root)
        tabs: QTabWidget = QTabWidget(parent=root)
        tabs.addTab(QWidget(), "Tab")
        tree: QTreeWidget = QTreeWidget(parent=root)
        tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for widget in (
            QLineEdit(parent=root),
            QListWidget(parent=root),
            tree,
            QPushButton(parent=root),
            QCheckBox(parent=root),
            QComboBox(parent=root),
            tabs,
        ):
            layout.addWidget(widget)
        assert qt_app is not None
        return root

    @pytest.mark.parametrize(
        argnames=("kind", "expected"),
        argvalues=[
            (QLineEdit, Qt.FocusPolicy.ClickFocus),
            (QListWidget, Qt.FocusPolicy.ClickFocus),
            (QTreeWidget, Qt.FocusPolicy.NoFocus),
            (QPushButton, Qt.FocusPolicy.NoFocus),
            (QCheckBox, Qt.FocusPolicy.NoFocus),
            (QComboBox, Qt.FocusPolicy.NoFocus),
            (QTabWidget, Qt.FocusPolicy.NoFocus),
        ],
        ids=["text field", "list", "list without focus", "button", "check box", "combo box", "tabs"],
    )
    def test_apply(self, root: QWidget, kind: type[QWidget], expected: Qt.FocusPolicy) -> None:
        """
        Leaves click focus to text fields and lists that took clicks; the rest takes no focus, a list's viewport aside.

        :param root: widget under test
        :param kind: widget class
        :param expected: its focus policy afterward
        :return: None
        """
        # Arrange
        widget: QWidget = root.findChild(kind)  # type: ignore[assignment]
        # Act
        MouseFocus.apply(root=root)
        # Assert
        assert widget.focusPolicy() == expected

    def test_apply_no_tab(self, root: QWidget) -> None:
        """
        Leaves nothing reachable by Tab, the tab bar inside the tabs included.

        :param root: widget under test
        :return: None
        """
        # Arrange & Act
        MouseFocus.apply(root=root)
        # Assert
        assert not any(
            widget.focusPolicy().value & Qt.FocusPolicy.TabFocus.value for widget in root.findChildren(QWidget)
        )
