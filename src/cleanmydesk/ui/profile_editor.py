"""The Work profile pane: how the person works at the desk."""

from __future__ import annotations

from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QGridLayout, QLabel, QVBoxLayout, QWidget

from cleanmydesk.commands import SetProfileCommand
from cleanmydesk.document import ProjectDocument
from cleanmydesk.model.project import HANDEDNESS, TASKS, WorkProfile


class ProfileEditor(QWidget):
    def __init__(self, doc: ProjectDocument, undo_stack: QUndoStack, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.undo_stack = undo_stack

        self.handedness = QComboBox()
        for code, label in HANDEDNESS.items():
            self.handedness.addItem(label, code)
        self.handedness.activated.connect(self._commit)

        self.task_boxes: dict[str, QCheckBox] = {}
        tasks = QGridLayout()
        for n, (code, label) in enumerate(TASKS.items()):
            box = QCheckBox(label)
            box.toggled.connect(self._commit)
            tasks.addWidget(box, n // 2, n % 2)
            self.task_boxes[code] = box

        form = QFormLayout()
        form.addRow("I am", self.handedness)
        hint = QLabel("The suggested layout and the AI use this to fit the desk to how you work.")
        hint.setWordWrap(True)
        hint.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.addLayout(form)
        layout.addWidget(QLabel("At this desk I do:"))
        layout.addLayout(tasks)
        layout.addWidget(hint)
        layout.addStretch(1)

        doc.profile_changed.connect(self._sync)
        doc.project_replaced.connect(self._sync)
        self._sync()

    def _commit(self, *_args) -> None:
        profile = WorkProfile(
            handedness=self.handedness.currentData(),
            tasks=tuple(code for code, box in self.task_boxes.items() if box.isChecked()),
        )
        if profile != self.doc.project.profile:
            self.undo_stack.push(SetProfileCommand(self.doc, profile))

    def _sync(self) -> None:
        profile = self.doc.project.profile
        widgets = (self.handedness, *self.task_boxes.values())
        for widget in widgets:
            widget.blockSignals(True)
        self.handedness.setCurrentIndex(max(self.handedness.findData(profile.handedness), 0))
        for code, box in self.task_boxes.items():
            box.setChecked(code in profile.tasks)
        for widget in widgets:
            widget.blockSignals(False)
