import math

from cleanmydesk.engine.layout import suggest_layout, zone_of
from cleanmydesk.model.project import Desk, Item, WorkProfile, guess_kind


def item(name, w, d, h=5, usage="sometimes", kind=None):
    return Item(name, w, d, h, kind=kind or guess_kind(name), usage=usage)


def office_items():
    return [
        item("Monitor", 60, 20, 45, "constantly"),
        item("Keyboard", 44, 14, 3, "constantly"),
        item("Mouse", 7, 12, 4, "constantly"),
        item("Coffee mug", 9, 9, 10, "often"),
        item("Desk lamp", 15, 15, 40),
        item("Phone", 8, 16, 1, "often"),
        item("Notebook", 21, 30, 1),
        item("Stapler", 15, 5, 6, "rarely"),
    ]


def by_name(result, items):
    names = {i.id: i.name for i in items}
    return {names[p.item_id]: p for p in result.placements}


def center(p):
    return p.x_cm + p.width_cm / 2, p.y_cm + p.depth_cm / 2


def assert_valid(desk, result):
    for p in result.placements:
        assert -1e-6 <= p.x_cm and p.x_cm + p.width_cm <= desk.width_cm + 1e-6
        assert -1e-6 <= p.y_cm and p.y_cm + p.depth_cm <= desk.depth_cm + 1e-6
    for n, a in enumerate(result.placements):
        for b in result.placements[n + 1:]:
            overlap_x = min(a.x_cm + a.width_cm, b.x_cm + b.width_cm) - max(a.x_cm, b.x_cm)
            overlap_y = min(a.y_cm + a.depth_cm, b.y_cm + b.depth_cm) - max(a.y_cm, b.y_cm)
            assert not (overlap_x > 0.01 and overlap_y > 0.01), (a, b)


def test_empty_desk():
    result = suggest_layout(Desk(), [], WorkProfile())
    assert result.placements == [] and result.off_desk == [] and result.reasons == {}


def test_layout_stays_on_desk_without_overlaps_and_explains_everything():
    desk, items = Desk(120, 60), office_items()
    result = suggest_layout(desk, items, WorkProfile())
    assert_valid(desk, result)
    assert len(result.placements) + len(result.off_desk) == len(items)
    assert set(result.reasons) == {i.id for i in items}
    assert all(result.reasons.values())


def test_same_input_gives_same_layout():
    items = office_items()
    assert suggest_layout(Desk(), items, WorkProfile()) == suggest_layout(Desk(), items, WorkProfile())


def test_keyboard_front_center_and_screen_centered_at_back():
    desk, items = Desk(120, 60), office_items()
    placed = by_name(suggest_layout(desk, items, WorkProfile()), items)
    kx, ky = center(placed["Keyboard"])
    sx, sy = center(placed["Monitor"])
    assert abs(kx - 60) < 5 and ky > 40
    assert abs(sx - 60) < 5 and placed["Monitor"].y_cm < 1


def test_mouse_goes_on_the_dominant_hand_side():
    desk, items = Desk(120, 60), office_items()
    for handedness, side in (("right", 1), ("left", -1)):
        placed = by_name(suggest_layout(desk, items, WorkProfile(handedness)), items)
        mouse_x, _ = center(placed["Mouse"])
        keyboard_x, _ = center(placed["Keyboard"])
        assert (mouse_x - keyboard_x) * side > 20
        lamp_x, _ = center(placed["Desk lamp"])
        assert (lamp_x - 60) * side < 0  # lamp opposite the writing hand


def test_screens_keyboards_and_mice_are_never_turned():
    desk, items = Desk(100, 45), office_items()
    result = suggest_layout(desk, items, WorkProfile())
    for name in ("Monitor", "Keyboard", "Mouse"):
        p = by_name(result, items).get(name)
        assert p is None or not p.rotated


def test_often_used_items_end_up_closer_than_rarely_used_ones():
    desk = Desk(120, 60)
    items = [item("Box A", 12, 12, usage="constantly"), item("Box B", 12, 12, usage="rarely")]
    placed = by_name(suggest_layout(desk, items, WorkProfile()), items)
    seat = (60, 60)
    assert math.dist(center(placed["Box A"]), seat) < math.dist(center(placed["Box B"]), seat)
    assert zone_of(desk, placed["Box A"]) == "easy"


def test_crowded_desk_puts_away_the_least_used_items():
    desk = Desk(50, 30)
    items = [item("Big", 45, 25, usage="constantly"), item("Spare", 20, 20, usage="rarely")]
    result = suggest_layout(desk, items, WorkProfile())
    assert [i.name for i in result.off_desk] == ["Spare"]
    assert "drawer or on a shelf" in result.reasons[items[1].id]
    assert_valid(desk, result)


def test_item_used_all_the_time_is_not_put_away_to_keep_space_clear():
    desk = Desk(50, 50)
    board, lamp = item("Board", 50, 50, 1, "constantly"), item("Lamp", 10, 10, 30, kind="other")
    result = suggest_layout(desk, [board, lamp], WorkProfile())
    assert [i.name for i in result.off_desk] == ["Lamp"]
