"""Arranges the three panes and shows "Add pane" when none is expanded.

    +---------------------------+-------------+
    | Desk layout               | Items on    |
    |                           | desk        |
    +---------------------------+             |
    | Item dimensions           |             |
    +---------------------------+-------------+
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

from cleanmydesk.commands import SetPaneStateCommand
from cleanmydesk.document import (
    PANE_CLOSED,
    PANE_COLLAPSED,
    PANE_EXPANDED,
    ProjectDocument,
)
from cleanmydesk.ui.icons import icon
from cleanmydesk.ui.pane import MAX_SIZE, Pane


class PaneArea(QWidget):
    add_pane_clicked = Signal()

    def __init__(
        self,
        doc: ProjectDocument,
        undo_stack: QUndoStack,
        layout_pane: Pane,
        dimensions_pane: Pane,
        items_pane: Pane,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.undo_stack = undo_stack
        self.panes = {p.pane_id: p for p in (layout_pane, dimensions_pane, items_pane)}

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(layout_pane)
        self.left_splitter.addWidget(dimensions_pane)
        self.left_splitter.setSizes([400, 250])

        # Shown in place of the panes when none of them is expanded.
        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.addStretch(1)
        hint = QLabel("All panes are collapsed or closed.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_pane_button = QPushButton(icon("add_pane"), "Add pane")
        self.add_pane_button.clicked.connect(self.add_pane_clicked)
        empty_layout.addWidget(hint)
        empty_layout.addWidget(self.add_pane_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)

        self.left_column = QWidget()
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.left_splitter, 1)
        left_layout.addWidget(self.empty_state, 1)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_column)
        self.main_splitter.addWidget(items_pane)
        self.main_splitter.setSizes([650, 300])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.main_splitter)

        for pane in self.panes.values():
            pane.expand_clicked.connect(lambda p=pane: self.request_state(p.pane_id, PANE_EXPANDED))
            pane.collapse_clicked.connect(lambda p=pane: self.request_state(p.pane_id, PANE_COLLAPSED))

        doc.pane_state_changed.connect(self._on_pane_state_changed)
        doc.project_replaced.connect(self.sync_from_document)
        self.sync_from_document()

    # Called by the +/− buttons and by the sidebar menus.
    def request_state(self, pane_id: str, state: str) -> None:
        if self.doc.pane_state(pane_id) != state:
            self.undo_stack.push(
                SetPaneStateCommand(self.doc, pane_id, self.panes[pane_id].title, state)
            )

    def panes_not_expanded(self) -> list[Pane]:
        return [p for p in self.panes.values() if p.state != PANE_EXPANDED]

    def panes_open(self) -> list[Pane]:
        return [p for p in self.panes.values() if p.state != PANE_CLOSED]

    def sync_from_document(self) -> None:
        for pane_id, pane in self.panes.items():
            pane.apply_state(self.doc.pane_state(pane_id))
        self._update_layout()

    def _on_pane_state_changed(self, pane_id: str, state: str) -> None:
        pane = self.panes[pane_id]
        was_collapsed = pane.state == PANE_COLLAPSED
        pane.apply_state(state)
        self._update_layout()
        if was_collapsed and state == PANE_EXPANDED:
            self._restore_size(pane)

    def _update_layout(self) -> None:
        states = {pane_id: pane.state for pane_id, pane in self.panes.items()}
        any_expanded = PANE_EXPANDED in states.values()
        left_ids = [self.left_splitter.widget(i).pane_id for i in range(self.left_splitter.count())]
        left_states = [states[pane_id] for pane_id in left_ids]
        left_open = any(s != PANE_CLOSED for s in left_states)

        self.empty_state.setVisible(not any_expanded)
        self.left_splitter.setVisible(left_open)
        self.left_column.setVisible(left_open or not any_expanded)

        # With nothing expanded on the left, the splitter only needs room
        # for the title bars; the rest of the column stays free.
        if left_open and PANE_EXPANDED not in left_states:
            bars = [p.maximumHeight() for p in self.panes.values() if p.pane_id in left_ids and p.isVisibleTo(self)]
            handles = self.left_splitter.handleWidth() * (len(bars) - 1)
            self.left_splitter.setMaximumHeight(sum(bars) + handles)
        else:
            self.left_splitter.setMaximumHeight(MAX_SIZE)

    def _restore_size(self, pane: Pane) -> None:
        """Give a re-expanded pane back the size it had before collapsing."""
        splitter = pane.parentWidget()
        if not isinstance(splitter, QSplitter) or pane.last_expanded_size <= 0:
            return
        sizes = splitter.sizes()
        index = splitter.indexOf(pane)
        total = sum(sizes)
        others = total - sizes[index]
        wanted = min(pane.last_expanded_size, max(total - 60, 0))
        if others <= 0:
            return
        scale = (total - wanted) / others
        new_sizes = [round(size * scale) for size in sizes]
        new_sizes[index] = wanted
        splitter.setSizes(new_sizes)
