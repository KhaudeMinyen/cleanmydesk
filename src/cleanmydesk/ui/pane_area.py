"""Arranges the panes in two columns and shows "Add pane" when all are closed.

    +---------------------------+-------------+
    | Desk layout               | Items on    |
    |                           | desk        |
    |                           +-------------+
    +---------------------------+ Work        |
    | Item dimensions           | profile     |
    +---------------------------+-------------+

Which panes are open is only how the window looks. It is not part of the
project, so it is not saved and never counts as an unsaved change, but
opening and closing panes can still be undone.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cleanmydesk.commands import SetPaneOpenCommand
from cleanmydesk.ui.icons import icon
from cleanmydesk.ui.pane import Pane


class PaneArea(QWidget):
    add_pane_clicked = Signal(QWidget)  # the button that was clicked
    panes_changed = Signal()

    def __init__(
        self,
        undo_stack: QUndoStack,
        left: list[Pane],
        right: list[Pane],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.panes = {p.pane_id: p for p in (*left, *right)}
        self._open = {pane_id: True for pane_id in self.panes}

        self.columns = []
        for panes, sizes in ((left, [420, 250]), (right, [380, 290])):
            column = QSplitter(Qt.Orientation.Vertical)
            column.setChildrenCollapsible(False)
            for pane in panes:
                column.addWidget(pane)
            column.setSizes(sizes[: len(panes)])
            self.columns.append(column)
        self.left_splitter, self.right_splitter = self.columns

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        for column in self.columns:
            self.main_splitter.addWidget(column)
        self.main_splitter.setSizes([650, 300])

        # Shown in place of the panes when every pane is closed.
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.addStretch(1)
        hint = QLabel("All panes are closed.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_pane_button = QPushButton(icon("add_pane"), "Add pane")
        self.add_pane_button.clicked.connect(lambda: self.add_pane_clicked.emit(self.add_pane_button))
        empty_layout.addWidget(hint)
        empty_layout.addWidget(self.add_pane_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.main_splitter)
        layout.addWidget(self.empty_state)

        for pane in self.panes.values():
            pane.close_clicked.connect(lambda p=pane: self.request_open(p.pane_id, False))
        self._update_layout()

    def is_open(self, pane_id: str) -> bool:
        return self._open[pane_id]

    def closed_panes(self) -> list[Pane]:
        return [p for p in self.panes.values() if not self._open[p.pane_id]]

    # Called by the − buttons and by the sidebar menu.
    def request_open(self, pane_id: str, is_open: bool) -> None:
        if self._open[pane_id] != is_open:
            self.undo_stack.push(SetPaneOpenCommand(self, pane_id, is_open))

    # Called by SetPaneOpenCommand.
    def set_pane_open(self, pane_id: str, is_open: bool) -> None:
        self._open[pane_id] = is_open
        self.panes[pane_id].setVisible(is_open)
        self._update_layout()
        self.panes_changed.emit()

    def _update_layout(self) -> None:
        for column in self.columns:
            column.setVisible(any(self._open[column.widget(i).pane_id] for i in range(column.count())))
        any_open = any(self._open.values())
        self.main_splitter.setVisible(any_open)
        self.empty_state.setVisible(not any_open)
