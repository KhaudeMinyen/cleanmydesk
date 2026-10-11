"""Arranges the three panes and shows "Add pane" when all are closed.

    +---------------------------+-------------+
    | Desk layout               | Items on    |
    |                           | desk        |
    +---------------------------+             |
    | Item dimensions           |             |
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
        layout_pane: Pane,
        dimensions_pane: Pane,
        items_pane: Pane,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.panes = {p.pane_id: p for p in (layout_pane, dimensions_pane, items_pane)}
        self._open = {pane_id: True for pane_id in self.panes}

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(layout_pane)
        self.left_splitter.addWidget(dimensions_pane)
        self.left_splitter.setSizes([400, 250])

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(items_pane)
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
        left_open = any(self._open[self.left_splitter.widget(i).pane_id] for i in range(self.left_splitter.count()))
        any_open = any(self._open.values())
        self.left_splitter.setVisible(left_open)
        self.main_splitter.setVisible(any_open)
        self.empty_state.setVisible(not any_open)
