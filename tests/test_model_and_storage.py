import json

import pytest

from cleanmydesk.layout_preview import arrange_items
from cleanmydesk.model.project import Desk, Item, Project, validate_dimension
from cleanmydesk.storage.project_file import ProjectFileError, load_project, save_project


def sample_project():
    return Project(
        desk=Desk(100, 50),
        items=[Item("Monitor", 60, 20, 45), Item("Mug", 9, 9, 10, size_source="ai")],
        panes={"layout": "collapsed", "items": "closed"},
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


def test_arrange_items_stays_on_desk_without_overlap():
    desk = Desk(120, 60)
    items = [Item(f"Item {n}", 10 + n * 3, 8 + n, 5) for n in range(12)]
    placements, unplaced = arrange_items(desk, items)
    assert len(placements) + len(unplaced) == len(items)
    for p in placements:
        assert 0 <= p.x_cm and p.x_cm + p.width_cm <= desk.width_cm
        assert 0 <= p.y_cm and p.y_cm + p.depth_cm <= desk.depth_cm
    for i, a in enumerate(placements):
        for b in placements[i + 1:]:
            overlap_x = a.x_cm < b.x_cm + b.width_cm and b.x_cm < a.x_cm + a.width_cm
            overlap_y = a.y_cm < b.y_cm + b.depth_cm and b.y_cm < a.y_cm + a.depth_cm
            assert not (overlap_x and overlap_y)


def test_arrange_items_reports_items_that_do_not_fit():
    desk = Desk(50, 50)
    big = Item("Big", 50, 50, 1)
    other = Item("Other", 10, 10, 1)
    placements, unplaced = arrange_items(desk, [big, other])
    assert [p.item_id for p in placements] == [big.id]
    assert unplaced == [other]
