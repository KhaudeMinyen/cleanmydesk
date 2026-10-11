import pytest
from PySide6.QtCore import Qt

from cleanmydesk.commands import AddItemCommand
from cleanmydesk.model.project import Item
from cleanmydesk.storage.project_file import load_project
from cleanmydesk.ui.main_window import CANCEL, DISCARD, SAVE, MainWindow


@pytest.fixture
def window(qapp):
    w = MainWindow()
    w.show()
    yield w
    w.undo_stack.setClean()  # skip the save prompt when the window closes
    w.close()
    w.deleteLater()


def add_item(window, name="Mug", size_source="manual"):
    item = Item(name, 9, 9, 10, size_source=size_source)
    window.undo_stack.push(AddItemCommand(window.doc, item))
    return item


def test_collapsing_every_pane_shows_add_pane_button(window):
    area = window.pane_area
    assert area.empty_state.isHidden()
    for pane_id in ("layout", "dimensions", "items"):
        area.request_state(pane_id, "collapsed")
    assert not area.empty_state.isHidden()
    assert area.panes["layout"].isVisible()  # title bar still showing

    window.undo_action.trigger()
    assert area.panes["items"].state == "expanded"
    assert area.empty_state.isHidden()


def test_close_pane_and_undo_redo(window):
    area = window.pane_area
    area.request_state("items", "closed")
    assert not area.panes["items"].isVisible()
    window.undo_action.trigger()
    assert area.panes["items"].isVisible()
    window.redo_action.trigger()
    assert not area.panes["items"].isVisible()


def test_closing_every_pane_disables_close_button(window):
    for pane_id in ("layout", "dimensions", "items"):
        window.pane_area.request_state(pane_id, "closed")
    assert not window.close_pane_action.isEnabled()
    assert window.add_pane_action.isEnabled()
    assert not window.pane_area.empty_state.isHidden()


def test_editing_a_size_is_undoable_and_marks_it_measured(window):
    item = add_item(window, size_source="ai")
    model = window.dimensions_editor.model
    width_index = model.index(0, 1)

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
    assert not window.dimensions_editor.model.setData(window.dimensions_editor.model.index(0, 1), 500.0)
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
    assert window.undo_stack.isClean()

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
    other.undo_stack.setClean()
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


def test_pane_layout_is_saved_with_the_project(window, tmp_path, monkeypatch):
    window.pane_area.request_state("items", "closed")
    monkeypatch.setattr(window, "_choose_save_path", lambda: tmp_path / "p.cmdesk")
    window.save()
    monkeypatch.setattr(window, "_ask_save_changes", lambda: DISCARD)
    window.new_project()
    assert window.pane_area.panes["items"].state == "expanded"
    assert window.open_path(tmp_path / "p.cmdesk")
    assert window.pane_area.panes["items"].state == "closed"


def test_remove_several_items_is_one_undo_step(window):
    for name in ("A", "B", "C"):
        add_item(window, name)
    editor = window.dimensions_editor
    editor.table.selectAll()
    editor.remove_selected()
    assert window.doc.project.items == []
    window.undo_action.trigger()
    assert [i.name for i in window.doc.project.items] == ["A", "B", "C"]
