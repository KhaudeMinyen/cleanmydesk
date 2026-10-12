import json

import pytest

from cleanmydesk.model.project import Desk, Item, Project, WorkProfile, guess_kind, validate_dimension
from cleanmydesk.storage.project_file import ProjectFileError, load_project, save_project


def sample_project():
    return Project(
        desk=Desk(100, 50),
        items=[Item("Monitor", 60, 20, 45, kind="screen", usage="constantly"), Item("Mug", 9, 9, 10, size_source="ai")],
        profile=WorkProfile("left", ("typing", "drawing")),
    )


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "desk.cmdesk"
    project = sample_project()
    save_project(project, path)
    assert load_project(path) == project


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        json.dumps({"format": "something-else", "version": 1}),
        json.dumps({"format": "cleanmydesk-project", "version": 99}),
        json.dumps({"format": "cleanmydesk-project", "version": 1, "desk": {"width_cm": -5, "depth_cm": 50}, "items": []}),
        json.dumps({"format": "cleanmydesk-project", "version": 1, "desk": {"width_cm": 100, "depth_cm": 50}}),
    ],
)
def test_load_rejects_bad_files(tmp_path, text):
    path = tmp_path / "bad.cmdesk"
    path.write_text(text)
    with pytest.raises(ProjectFileError):
        load_project(path)


def test_validate_dimension():
    desk = Desk(100, 50)
    item = Item("Board", 40, 30, 2)
    assert validate_dimension(desk, item, "width_cm", 0) == "Sizes must be greater than zero."
    assert validate_dimension(desk, item, "height_cm", 500) is None
    # 80 x 30 fits as-is; 30 x 80 fits when turned sideways.
    assert validate_dimension(desk, item, "width_cm", 80) is None
    assert validate_dimension(desk, item, "depth_cm", 80) is None
    assert "larger than" in validate_dimension(desk, item, "width_cm", 120)


def test_old_files_without_profile_or_usage_get_defaults(tmp_path):
    path = tmp_path / "old.cmdesk"
    path.write_text(json.dumps({
        "format": "cleanmydesk-project", "version": 1,
        "desk": {"width_cm": 100, "depth_cm": 50},
        "items": [{"id": "a", "name": "Mug", "width_cm": 9, "depth_cm": 9, "height_cm": 10, "size_source": "manual"}],
    }))
    project = load_project(path)
    assert project.items[0].kind == "other" and project.items[0].usage == "sometimes"
    assert project.profile == WorkProfile()


def test_guess_kind_uses_whole_words():
    assert guess_kind("Coffee mug") == "drink"
    assert guess_kind("Dell monitor") == "screen"
    assert guess_kind("Headphones") == "other"
    assert guess_kind("Highlighter") == "other"
    assert guess_kind("Books") == "notebook"
