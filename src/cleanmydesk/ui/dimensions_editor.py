"""The Item dimensions pane: desk size, plus a table to add and edit items.

Besides sizes, each item has a type and how often it is used; the
layout engine uses both."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cleanmydesk.commands import (
    AddItemCommand,
    RemoveItemCommand,
    SetDeskSizeCommand,
    SetItemFieldCommand,
)
from cleanmydesk.document import ProjectDocument
from cleanmydesk.model.project import DIMENSION_FIELDS, KINDS, USAGE_LEVELS, Item, validate_dimension
from cleanmydesk.ui.items_list import SOURCE_LABELS

COLUMNS = [
    ("name", "Item"),
    ("kind", "Type"),
    ("usage", "Use"),
    ("width_cm", "Width (cm)"),
    ("depth_cm", "Depth (cm)"),
    ("height_cm", "Height (cm)"),
    ("size_source", "Size from"),
]
COLUMN_OF = {field_name: n for n, (field_name, _label) in enumerate(COLUMNS)}
CHOICES = {"kind": KINDS, "usage": USAGE_LEVELS}  # columns edited with a drop-down list
MAX_CM = 1000.0


def _cm_spinbox() -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0.1, MAX_CM)
    box.setDecimals(1)
    box.setSuffix(" cm")
    return box


class ItemsTableModel(QAbstractTableModel):
    """Table of items. Edits are pushed to the undo stack, not applied directly."""

    message = Signal(str)

    def __init__(self, doc: ProjectDocument, undo_stack: QUndoStack, parent=None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.undo_stack = undo_stack
        for signal in (doc.project_replaced, doc.items_reset):
            signal.connect(self._reset)
        doc.item_changed.connect(self._item_changed)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.doc.project.items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][1]
        return None

    def flags(self, index: QModelIndex):
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if COLUMNS[index.column()][0] != "size_source":
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.doc.project.items[index.row()]
        field_name = COLUMNS[index.column()][0]
        value = getattr(item, field_name)
        if role == Qt.ItemDataRole.DisplayRole:
            if field_name in DIMENSION_FIELDS:
                return f"{value:g}"
            if field_name == "size_source":
                return SOURCE_LABELS.get(value, value)
            if field_name in CHOICES:
                return CHOICES[field_name].get(value, value)
            return value
        if role == Qt.ItemDataRole.EditRole:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole and field_name in DIMENSION_FIELDS:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        item = self.doc.project.items[index.row()]
        field_name = COLUMNS[index.column()][0]
        if field_name == "name":
            value = str(value).strip()
            if not value:
                self.message.emit("Item names cannot be empty.")
                return False
        elif field_name in DIMENSION_FIELDS:
            value = round(float(value), 1)
            error = validate_dimension(self.doc.project.desk, item, field_name, value)
            if error:
                self.message.emit(error)
                return False
        elif field_name in CHOICES:
            if value not in CHOICES[field_name]:
                return False
        else:
            return False
        if value == getattr(item, field_name):
            return False
        self.undo_stack.push(SetItemFieldCommand(self.doc, item.id, field_name, value))
        return True

    def _reset(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def _item_changed(self, item_id: str) -> None:
        row = self.doc.project.index_of(item_id)
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLUMNS) - 1))


class DimensionDelegate(QStyledItemDelegate):
    """Edits sizes with a spin box (up to 1000 cm), and type and use with a list."""

    def createEditor(self, parent, option, index):
        field_name = COLUMNS[index.column()][0]
        if field_name in DIMENSION_FIELDS:
            box = _cm_spinbox()
            box.setParent(parent)
            box.setFrame(False)
            return box
        if field_name in CHOICES:
            combo = QComboBox(parent)
            for code, label in CHOICES[field_name].items():
                combo.addItem(label, code)
            # Picking from the list saves the choice straight away.
            combo.activated.connect(lambda _n: (self.commitData.emit(combo), self.closeEditor.emit(combo)))
            return combo
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index) -> None:
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(max(editor.findData(index.data(Qt.ItemDataRole.EditRole)), 0))
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index) -> None:
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)
            return
        super().setModelData(editor, model, index)


class DimensionsEditor(QWidget):
    message = Signal(str)

    def __init__(self, doc: ProjectDocument, undo_stack: QUndoStack, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.undo_stack = undo_stack

        # Desk size row
        self.desk_width = _cm_spinbox()
        self.desk_depth = _cm_spinbox()
        desk_row = QHBoxLayout()
        desk_row.addWidget(QLabel("Desk width"))
        desk_row.addWidget(self.desk_width)
        desk_row.addSpacing(12)
        desk_row.addWidget(QLabel("Desk depth"))
        desk_row.addWidget(self.desk_depth)
        desk_row.addStretch(1)
        for box in (self.desk_width, self.desk_depth):
            box.editingFinished.connect(self._commit_desk_size)

        # Items table
        self.model = ItemsTableModel(doc, undo_stack, self)
        self.model.message.connect(self.message)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegate(DimensionDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COLUMNS)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )

        self.add_button = QPushButton("Add item")
        self.remove_button = QPushButton("Remove item")
        self.add_button.clicked.connect(self.add_item)
        self.remove_button.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        hint = QLabel("Double-click a cell to change it.")
        hint.setEnabled(False)
        buttons.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.addLayout(desk_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self.model.modelReset.connect(self._update_buttons)
        doc.project_replaced.connect(self._sync_desk_size)
        doc.desk_changed.connect(self._sync_desk_size)
        self._sync_desk_size()
        self._update_buttons()

    def add_item(self) -> None:
        item = Item(name="New item", width_cm=10.0, depth_cm=10.0, height_cm=10.0)
        self.undo_stack.push(AddItemCommand(self.doc, item))
        row = self.doc.project.index_of(item.id)
        index = self.model.index(row, 0)
        self.table.setCurrentIndex(index)
        self.table.edit(index)

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        ids = [self.doc.project.items[row].id for row in rows]
        if not ids:
            return
        if len(ids) == 1:
            self.undo_stack.push(RemoveItemCommand(self.doc, ids[0]))
            return
        self.undo_stack.beginMacro(f"Remove {len(ids)} items")
        for item_id in ids:
            self.undo_stack.push(RemoveItemCommand(self.doc, item_id))
        self.undo_stack.endMacro()

    def _commit_desk_size(self) -> None:
        width = round(self.desk_width.value(), 1)
        depth = round(self.desk_depth.value(), 1)
        desk = self.doc.project.desk
        if (width, depth) != (desk.width_cm, desk.depth_cm):
            self.undo_stack.push(SetDeskSizeCommand(self.doc, width, depth))

    def _sync_desk_size(self) -> None:
        desk = self.doc.project.desk
        for box, value in ((self.desk_width, desk.width_cm), (self.desk_depth, desk.depth_cm)):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)

    def _update_buttons(self) -> None:
        self.remove_button.setEnabled(self.table.selectionModel().hasSelection())
