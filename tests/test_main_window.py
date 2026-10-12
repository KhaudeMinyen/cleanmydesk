import pytest
from PySide6.QtCore import Qt

from cleanmydesk.commands import AddItemCommand
from cleanmydesk.model.project import Item
from cleanmydesk.storage.project_file import load_project
from cleanmydesk.ui.dimensions_editor import COLUMN_OF
from cleanmydesk.ui.main_window import CANCEL, DISCARD, SAVE, MainWindow


@pytest.fixture
def window(qapp):
    w = MainWindow()
    w.show()
    yield w
    w._ask_save_changes = lambda: DISCARD  # skip the save prompt when the window closes
    w.close()
    w.deleteLater()


def add_item(window, name="Mug", size_source="manual"):
    item = Item(name, 9, 9, 10, size_source=size_source)
    window.undo_stack.push(AddItemCommand(window.doc, item))
    return item


def test_closing_every_pane_shows_add_pane_button(window):
    area = window.pane_area
    assert area.empty_state.isHidden()
    for pane in area.panes.values():
        pane.close_button.click()
    assert not area.empty_state.isHidden()
    assert not area.main_splitter.isVisible()
    assert window.add_pane_action.isEnabled()

    window.undo_action.trigger()  # reopens the last pane closed
    assert area.panes["profile"].isVisible()
    assert area.empty_state.isHidden()


def test_close_pane_and_undo_redo(window):
    area = window.pane_area
    area.request_open("items", False)
    assert not area.panes["items"].isVisible()
    window.undo_action.trigger()
    assert area.panes["items"].isVisible()
    window.redo_action.trigger()
    assert not area.panes["items"].isVisible()


def test_panes_have_only_a_close_button(window):
    pane = window.pane_area.panes["layout"]
    assert not hasattr(pane, "add_button")
    assert pane.close_button.isEnabled()


def test_sidebar_opens_closed_panes(window):
    area = window.pane_area
    assert not window.add_pane_action.isEnabled()
    area.request_open("items", False)
    assert window.add_pane_action.isEnabled()
    window._fill_add_pane_menu()
    [action] = window.add_pane_menu.actions()
    assert action.text() == "Items on desk"
    action.trigger()
    assert area.panes["items"].isVisible()
    assert not window.add_pane_action.isEnabled()


def test_ai_button_is_in_the_sidebar_below_open_a_pane(window):
    actions = window.sidebar.actions()
    assert actions.index(window.ai_action) == actions.index(window.add_pane_action) + 1
    assert window.ai_action.isEnabled()
    assert not hasattr(window, "close_pane_action")


def test_closing_panes_is_not_an_unsaved_change(window, monkeypatch):
    window.pane_area.request_open("layout", False)
    window.pane_area.request_open("items", False)
    assert not window.is_modified()
    assert not window.isWindowModified()
    monkeypatch.setattr(window, "_ask_save_changes", lambda: pytest.fail("should not ask to save"))
    assert window.new_project()


def test_undoing_back_to_the_saved_state_clears_unsaved_mark(window):
    add_item(window)
    assert window.isWindowModified()
    window.undo_action.trigger()
    assert not window.is_modified()
    assert not window.isWindowModified()


def test_editing_a_size_is_undoable_and_marks_it_measured(window):
    item = add_item(window, size_source="ai")
    model = window.dimensions_editor.model
    width_index = model.index(0, COLUMN_OF["width_cm"])

    assert model.setData(width_index, 12.0, Qt.ItemDataRole.EditRole)
    assert item.width_cm == 12.0
    assert item.size_source == "manual"

    window.undo_action.trigger()
    assert item.width_cm == 9
    assert item.size_source == "ai"


def test_invalid_size_is_rejected_with_a_message(window):
    add_item(window)
    messages = []
    window.dimensions_editor.model.message.connect(messages.append)
    count = window.undo_stack.count()
    assert not window.dimensions_editor.model.setData(window.dimensions_editor.model.index(0, COLUMN_OF["width_cm"]), 500.0)
    assert window.undo_stack.count() == count
    assert "larger than" in messages[0]


def test_first_save_asks_for_a_file_then_saves_in_place(window, tmp_path, monkeypatch):
    asked = []

    def choose():
        asked.append(True)
        return tmp_path / "my desk"

    monkeypatch.setattr(window, "_choose_save_path", choose)
    add_item(window)
    assert window.save()
    path = tmp_path / "my desk.cmdesk"
    assert load_project(path).items[0].name == "Mug"
    assert not window.is_modified()

    add_item(window, "Lamp")
    assert window.save()
    assert len(asked) == 1
    assert [i.name for i in load_project(path).items] == ["Mug", "Lamp"]


@pytest.mark.parametrize("action", ["new_project", "open_project"])
def test_unsaved_changes_cancel_keeps_project(window, monkeypatch, action):
    add_item(window)
    monkeypatch.setattr(window, "_ask_save_changes", lambda: CANCEL)
    monkeypatch.setattr(window, "_choose_open_path", lambda: pytest.fail("should not ask for a file"))
    assert not getattr(window, action)()
    assert len(window.doc.project.items) == 1


def test_unsaved_changes_discard_starts_new_project(window, monkeypatch):
    add_item(window)
    monkeypatch.setattr(window, "_ask_save_changes", lambda: DISCARD)
    assert window.new_project()
    assert window.doc.project.items == []
    assert window.undo_stack.count() == 0


def test_unsaved_changes_save_then_open(window, tmp_path, monkeypatch):
    other = MainWindow()
    other.doc.project.items.append(Item("Plant", 20, 20, 30))
    other._write(tmp_path / "other.cmdesk")
    other.deleteLater()

    add_item(window)
    monkeypatch.setattr(window, "_ask_save_changes", lambda: SAVE)
    monkeypatch.setattr(window, "_choose_save_path", lambda: tmp_path / "first.cmdesk")
    monkeypatch.setattr(window, "_choose_open_path", lambda: tmp_path / "other.cmdesk")
    assert window.open_project()
    assert load_project(tmp_path / "first.cmdesk").items[0].name == "Mug"
    assert [i.name for i in window.doc.project.items] == ["Plant"]
    assert window.windowTitle().startswith("other.cmdesk")


def test_cancelling_the_save_dialog_cancels_new_project(window, monkeypatch):
    add_item(window)
    monkeypatch.setattr(window, "_ask_save_changes", lambda: SAVE)
    monkeypatch.setattr(window, "_choose_save_path", lambda: None)
    assert not window.new_project()
    assert len(window.doc.project.items) == 1


def test_remove_several_items_is_one_undo_step(window):
    for name in ("A", "B", "C"):
        add_item(window, name)
    editor = window.dimensions_editor
    editor.table.selectAll()
    editor.remove_selected()
    assert window.doc.project.items == []
    window.undo_action.trigger()
    assert [i.name for i in window.doc.project.items] == ["A", "B", "C"]


def test_ai_button_opens_the_chat_window(window):
    window.ai_action.trigger()
    dialog = window.ai_dialog
    assert dialog is not None and dialog.isVisible()
    window.ai_action.trigger()
    assert window.ai_dialog is dialog  # the same window is reused
    dialog.close()


def test_work_profile_change_is_undoable_and_unsaved(window):
    editor = window.pane_area.panes["profile"].content
    editor.task_boxes["writing"].setChecked(True)
    assert "writing" in window.doc.project.profile.tasks
    assert window.is_modified()
    editor.handedness.setCurrentIndex(editor.handedness.findData("left"))
    editor.handedness.activated.emit(editor.handedness.currentIndex())
    assert window.doc.project.profile.handedness == "left"
    window.undo_action.trigger()
    assert window.doc.project.profile.handedness == "right"
    assert editor.handedness.currentData() == "right"
    window.undo_action.trigger()
    assert "writing" not in window.doc.project.profile.tasks
    assert not editor.task_boxes["writing"].isChecked()


def test_type_and_use_columns_change_the_suggested_layout(window):
    item = add_item(window, "Thing")
    model = window.dimensions_editor.model
    before = window.suggestions.result.reasons[item.id]
    assert model.setData(model.index(0, COLUMN_OF["usage"]), "rarely")
    assert item.usage == "rarely"
    assert model.data(model.index(0, COLUMN_OF["usage"])) == "Rarely"
    assert not model.setData(model.index(0, COLUMN_OF["kind"]), "spaceship")
    assert model.setData(model.index(0, COLUMN_OF["kind"]), "drink")
    assert window.suggestions.result.reasons[item.id] != before
    window.undo_action.trigger()
    assert item.kind == "other"


def test_renaming_an_item_guesses_its_type(window):
    item = add_item(window, "New item")
    model = window.dimensions_editor.model
    assert model.setData(model.index(0, COLUMN_OF["name"]), "Coffee mug")
    assert item.kind == "drink"
    window.undo_action.trigger()
    assert item.name == "New item" and item.kind == "other"
    # A type the user chose is kept when renaming.
    assert model.setData(model.index(0, COLUMN_OF["kind"]), "lamp")
    assert model.setData(model.index(0, COLUMN_OF["name"]), "Phone stand")
    assert item.kind == "lamp"


def test_desk_layout_lists_a_reason_for_every_item(window):
    for name in ("Monitor", "Mug"):
        add_item(window, name)
    window.suggestions.changed.emit()
    panel = window.pane_area.panes["layout"].content
    texts = [panel.reasons.item(n).text() for n in range(panel.reasons.count())]
    assert len(texts) == 2 and texts[0].startswith("Monitor: ")
