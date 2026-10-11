"""Read-only list of the items on the desk, for the Items on desk pane."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from cleanmydesk.document import ProjectDocument
from cleanmydesk.model.project import SIZE_SOURCE_AI

SOURCE_LABELS = {SIZE_SOURCE_AI: "AI estimate", "manual": "Measured"}


class ItemsListView(QStackedWidget):
    def __init__(self, doc: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "W × D × H (cm)", "Size from"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setStretchLastSection(False)
        for column in (1, 2):
            self.tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        self.empty_label = QLabel("No items yet.\nAdd them in the Item dimensions pane.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.addWidget(self.tree)
        self.addWidget(self.empty_label)

        for signal in (doc.project_replaced, doc.items_reset):
            signal.connect(self.refresh)
        doc.item_changed.connect(lambda _item_id: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        for item in self.doc.project.items:
            size = f"{item.width_cm:g} × {item.depth_cm:g} × {item.height_cm:g}"
            row = QTreeWidgetItem([item.name, size, SOURCE_LABELS.get(item.size_source, item.size_source)])
            self.tree.addTopLevelItem(row)
        self.setCurrentWidget(self.tree if self.doc.project.items else self.empty_label)
