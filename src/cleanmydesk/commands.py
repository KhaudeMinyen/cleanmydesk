"""Undoable changes. Each one is pushed onto the window's QUndoStack."""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from cleanmydesk.document import ProjectDocument
from cleanmydesk.model.project import DIMENSION_FIELDS, SIZE_SOURCE_MANUAL, Item

FIELD_LABELS = {
    "name": "name",
    "width_cm": "width",
    "depth_cm": "depth",
    "height_cm": "height",
}


class SetPaneStateCommand(QUndoCommand):
    def __init__(self, doc: ProjectDocument, pane_id: str, title: str, state: str) -> None:
        verbs = {"expanded": "Expand", "collapsed": "Collapse", "closed": "Close"}
        super().__init__(f"{verbs[state]} {title} pane")
        self.doc = doc
        self.pane_id = pane_id
        self.old_state = doc.pane_state(pane_id)
        self.new_state = state

    def redo(self) -> None:
        self.doc.set_pane_state(self.pane_id, self.new_state)

    def undo(self) -> None:
        self.doc.set_pane_state(self.pane_id, self.old_state)


class SetItemFieldCommand(QUndoCommand):
    """Change an item's name or one of its sizes.

    Typing in a size counts as a manual measurement, so the item's size
    source switches to "manual" (and switches back on undo).
    """

    def __init__(self, doc: ProjectDocument, item_id: str, field_name: str, value) -> None:
        item = doc.project.item(item_id)
        super().__init__(f"Change {FIELD_LABELS[field_name]} of {item.name or 'item'}")
        self.doc = doc
        self.item_id = item_id
        self.field_name = field_name
        self.old_value = getattr(item, field_name)
        self.new_value = value
        self.old_source = item.size_source

    def redo(self) -> None:
        self.doc.set_item_field(self.item_id, self.field_name, self.new_value)
        if self.field_name in DIMENSION_FIELDS:
            self.doc.set_item_field(self.item_id, "size_source", SIZE_SOURCE_MANUAL)

    def undo(self) -> None:
        self.doc.set_item_field(self.item_id, self.field_name, self.old_value)
        self.doc.set_item_field(self.item_id, "size_source", self.old_source)


class AddItemCommand(QUndoCommand):
    def __init__(self, doc: ProjectDocument, item: Item, row: int | None = None) -> None:
        super().__init__(f"Add {item.name or 'item'}")
        self.doc = doc
        self.item = item
        self.row = len(doc.project.items) if row is None else row

    def redo(self) -> None:
        self.doc.insert_item(self.row, self.item)

    def undo(self) -> None:
        self.doc.remove_item(self.item.id)


class RemoveItemCommand(QUndoCommand):
    def __init__(self, doc: ProjectDocument, item_id: str) -> None:
        self.doc = doc
        self.row = doc.project.index_of(item_id)
        self.item = doc.project.items[self.row]
        super().__init__(f"Remove {self.item.name or 'item'}")

    def redo(self) -> None:
        self.doc.remove_item(self.item.id)

    def undo(self) -> None:
        self.doc.insert_item(self.row, self.item)


class SetDeskSizeCommand(QUndoCommand):
    def __init__(self, doc: ProjectDocument, width_cm: float, depth_cm: float) -> None:
        super().__init__("Change desk size")
        self.doc = doc
        self.old_size = (doc.project.desk.width_cm, doc.project.desk.depth_cm)
        self.new_size = (width_cm, depth_cm)

    def redo(self) -> None:
        self.doc.set_desk_size(*self.new_size)

    def undo(self) -> None:
        self.doc.set_desk_size(*self.old_size)
