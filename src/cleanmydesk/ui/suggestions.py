"""Keeps the suggested layout up to date as the project changes."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from cleanmydesk.document import ProjectDocument
from cleanmydesk.engine.layout import LayoutResult, suggest_layout


class LayoutSuggestions(QObject):
    """Works out the suggested layout once per batch of changes.

    Several changes can arrive together (an undo of "Remove 3 items", for
    example), so the work waits until they are all in, then runs once.
    """

    changed = Signal()

    def __init__(self, doc: ProjectDocument, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self._result: LayoutResult | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.changed)
        for signal in (doc.project_replaced, doc.desk_changed, doc.items_reset, doc.profile_changed):
            signal.connect(self._invalidate)
        doc.item_changed.connect(self._invalidate)

    @property
    def result(self) -> LayoutResult:
        if self._result is None:
            project = self.doc.project
            self._result = suggest_layout(project.desk, project.items, project.profile)
        return self._result

    def _invalidate(self, *_args) -> None:
        self._result = None
        self._timer.start()
