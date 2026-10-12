"""The open project, wrapped so the screens are told when it changes.

The methods here change the project directly. The screens never call them
on their own: they push a command from `commands.py` onto the undo stack,
and the command calls these methods. That is what makes every change
undoable.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from cleanmydesk.model.project import Item, Project, WorkProfile


class ProjectDocument(QObject):
    project_replaced = Signal()
    desk_changed = Signal()
    items_reset = Signal()
    item_changed = Signal(str)  # item id
    profile_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = Project()
        self.path: Path | None = None

    def replace_project(self, project: Project, path: Path | None) -> None:
        self.project = project
        self.path = path
        self.project_replaced.emit()

    # Work profile

    def set_profile(self, profile: WorkProfile) -> None:
        self.project.profile = profile
        self.profile_changed.emit()

    # Desk

    def set_desk_size(self, width_cm: float, depth_cm: float) -> None:
        self.project.desk.width_cm = width_cm
        self.project.desk.depth_cm = depth_cm
        self.desk_changed.emit()

    # Items

    def set_item_field(self, item_id: str, field_name: str, value) -> None:
        setattr(self.project.item(item_id), field_name, value)
        self.item_changed.emit(item_id)

    def insert_item(self, row: int, item: Item) -> None:
        self.project.items.insert(row, item)
        self.items_reset.emit()

    def remove_item(self, item_id: str) -> tuple[int, Item]:
        row = self.project.index_of(item_id)
        item = self.project.items.pop(row)
        self.items_reset.emit()
        return row, item
