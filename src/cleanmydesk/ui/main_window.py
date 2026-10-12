"""The main window: sidebar on the left, panes on the right."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from cleanmydesk.document import ProjectDocument
from cleanmydesk.model.project import Project
from cleanmydesk.storage.project_file import (
    FILE_EXTENSION,
    ProjectFileError,
    load_project,
    project_to_dict,
    save_project,
)
from cleanmydesk.ui.desk_view import DeskLayoutView
from cleanmydesk.ui.dimensions_editor import DimensionsEditor
from cleanmydesk.ui.icons import icon
from cleanmydesk.ui.items_list import ItemsListView
from cleanmydesk.ui.pane import Pane
from cleanmydesk.ui.pane_area import PaneArea

FILE_FILTER = f"CleanMyDesk project (*{FILE_EXTENSION})"

# Answers from the "save changes?" prompt.
SAVE, DISCARD, CANCEL = "save", "discard", "cancel"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc = ProjectDocument(self)
        self.undo_stack = QUndoStack(self)
        # A copy of the project as it was last saved (or opened). The project
        # has unsaved changes whenever it differs from this copy, so undoing
        # back to the saved state clears the "unsaved" mark again.
        self._saved_copy = project_to_dict(self.doc.project)
        for signal in (self.doc.project_replaced, self.doc.desk_changed, self.doc.items_reset):
            signal.connect(self._update_modified)
        self.doc.item_changed.connect(self._update_modified)

        self.dimensions_editor = DimensionsEditor(self.doc, self.undo_stack)
        self.dimensions_editor.message.connect(self._show_message)
        self.pane_area = PaneArea(
            self.undo_stack,
            layout_pane=Pane("layout", "Desk layout", DeskLayoutView(self.doc)),
            dimensions_pane=Pane("dimensions", "Item dimensions", self.dimensions_editor),
            items_pane=Pane("items", "Items on desk", ItemsListView(self.doc)),
        )
        self.pane_area.add_pane_clicked.connect(self._show_add_pane_menu_under)
        self.setCentralWidget(self.pane_area)

        self._build_sidebar()
        self.pane_area.panes_changed.connect(self._update_pane_actions)
        self._update_pane_actions()

        self.statusBar()
        self._update_title()
        self.resize(1000, 680)

    # Sidebar

    def _build_sidebar(self) -> None:
        bar = QToolBar("Sidebar")
        bar.setObjectName("sidebar")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setIconSize(QSize(22, 22))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, bar)
        self.sidebar = bar

        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setIcon(icon("undo"))
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setIcon(icon("redo"))
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)

        self.new_action = QAction(icon("new"), "New project", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self.new_project)
        self.save_action = QAction(icon("save"), "Save project", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save)
        self.open_action = QAction(icon("open"), "Open project", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_project)

        # Save As has no button, only a keyboard shortcut.
        self.save_as_action = QAction("Save project as", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.save_as)
        self.addAction(self.save_as_action)

        self.add_pane_menu = QMenu(self)
        self.add_pane_menu.aboutToShow.connect(self._fill_add_pane_menu)
        self.add_pane_action = QAction(icon("add_pane"), "Open a pane", self)
        self.add_pane_action.setMenu(self.add_pane_menu)

        # Will ask an AI to explain the arrangement, give general tips, and
        # suggest changes. Not connected to anything yet.
        self.ai_action = QAction(icon("ai"), "Ask AI about this desk (coming soon)", self)
        self.ai_action.setEnabled(False)

        # Placeholder for a future feature; it does nothing yet.
        self.spare_action = QAction(icon("gear"), "Not assigned yet", self)
        self.spare_action.setEnabled(False)

        for action in (
            self.undo_action,
            self.redo_action,
            self.new_action,
            self.save_action,
            self.open_action,
            self.add_pane_action,
            self.ai_action,
        ):
            bar.addAction(action)
        button = bar.widgetForAction(self.add_pane_action)
        if isinstance(button, QToolButton):
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        bar.addWidget(spacer)
        bar.addAction(self.spare_action)

    def _fill_add_pane_menu(self) -> None:
        self.add_pane_menu.clear()
        for pane in self.pane_area.closed_panes():
            action = self.add_pane_menu.addAction(pane.title)
            action.triggered.connect(lambda _checked=False, p=pane: self.pane_area.request_open(p.pane_id, True))

    def _show_add_pane_menu_under(self, button: QWidget) -> None:
        self.add_pane_menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _update_pane_actions(self) -> None:
        self.add_pane_action.setEnabled(bool(self.pane_area.closed_panes()))

    # Files

    def new_project(self) -> bool:
        if not self.maybe_save():
            return False
        self._load(Project(), None)
        self.statusBar().showMessage("Started a new project.", 4000)
        return True

    def open_project(self) -> bool:
        if not self.maybe_save():
            return False
        path = self._choose_open_path()
        if path is None:
            return False
        return self.open_path(path)

    def open_path(self, path: Path) -> bool:
        try:
            project = load_project(path)
        except (OSError, ProjectFileError) as exc:
            QMessageBox.critical(self, "Could not open project", f"{path.name} could not be opened.\n\n{exc}")
            return False
        self._load(project, path)
        self.statusBar().showMessage(f"Opened {path.name}.", 4000)
        return True

    def save(self) -> bool:
        """Save to the current file, or ask for a file name the first time."""
        if self.doc.path is None:
            return self.save_as()
        return self._write(self.doc.path)

    def save_as(self) -> bool:
        path = self._choose_save_path()
        if path is None:
            return False
        if path.suffix.lower() != FILE_EXTENSION:
            path = path.with_name(path.name + FILE_EXTENSION)
        return self._write(path)

    def maybe_save(self) -> bool:
        """Return True if it is OK to replace the current project."""
        if not self.is_modified():
            return True
        answer = self._ask_save_changes()
        if answer == SAVE:
            return self.save()
        return answer == DISCARD

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

    def _load(self, project: Project, path: Path | None) -> None:
        self._saved_copy = project_to_dict(project)
        self.doc.replace_project(project, path)
        self.undo_stack.clear()
        self._update_title()

    def _write(self, path: Path) -> bool:
        try:
            save_project(self.doc.project, path)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save project", f"{path.name} could not be saved.\n\n{exc}")
            return False
        self.doc.path = path
        self._saved_copy = project_to_dict(self.doc.project)
        self._update_title()
        self.statusBar().showMessage(f"Saved {path.name}.", 4000)
        return True

    def is_modified(self) -> bool:
        """True if the desk or items changed since the last save."""
        return project_to_dict(self.doc.project) != self._saved_copy

    def _update_modified(self, *_args) -> None:
        self.setWindowModified(self.is_modified())

    def _show_message(self, text: str) -> None:
        self.statusBar().showMessage(text, 6000)

    def _update_title(self) -> None:
        name = self.doc.path.name if self.doc.path else "Untitled"
        self.setWindowTitle(f"{name}[*] - CleanMyDesk")
        self._update_modified()

    # Dialogs, kept in small methods so tests can replace them.

    def _ask_save_changes(self) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        name = self.doc.path.name if self.doc.path else "This project"
        box.setText(f"{name} has unsaved changes.")
        box.setInformativeText("Do you want to save them first?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        return {
            QMessageBox.StandardButton.Save: SAVE,
            QMessageBox.StandardButton.Discard: DISCARD,
        }.get(QMessageBox.StandardButton(result), CANCEL)

    def _choose_save_path(self) -> Path | None:
        start = str(self.doc.path or Path.home() / f"My desk{FILE_EXTENSION}")
        name, _ = QFileDialog.getSaveFileName(self, "Save project", start, FILE_FILTER)
        return Path(name) if name else None

    def _choose_open_path(self) -> Path | None:
        start = str(self.doc.path.parent if self.doc.path else Path.home())
        name, _ = QFileDialog.getOpenFileName(self, "Open project", start, FILE_FILTER)
        return Path(name) if name else None
