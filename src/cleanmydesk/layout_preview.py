"""A stand-in arrangement for the Desk layout pane.

The AI suggestion engine (readme section 5) is not built yet. Until it
is, the Desk layout pane shows items lined up in rows, biggest first,
starting at the back of the desk. This keeps every item drawn to scale.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleanmydesk.model.project import Desk, Item

GAP_CM = 2.0


@dataclass
class Placement:
    item_id: str
    x_cm: float  # from the left edge of the desk
    y_cm: float  # from the back edge of the desk
    width_cm: float  # as placed (swapped with depth if rotated)
    depth_cm: float
    rotated: bool


def arrange_items(desk: Desk, items: list[Item]) -> tuple[list[Placement], list[Item]]:
    """Return (placements, items that did not fit)."""
    placements: list[Placement] = []
    unplaced: list[Item] = []
    row_y = 0.0
    row_x = 0.0
    row_depth = 0.0

    for item in sorted(items, key=lambda i: (max(i.depth_cm, i.width_cm), i.width_cm), reverse=True):
        placed = False
        for width, depth, rotated in _orientations(item):
            x = row_x + (GAP_CM if row_x > 0 else 0)
            if x + width <= desk.width_cm and row_y + depth <= desk.depth_cm:
                placements.append(Placement(item.id, x, row_y, width, depth, rotated))
                row_x = x + width
                row_depth = max(row_depth, depth)
                placed = True
                break
        if placed:
            continue
        # Start a new row in front of the current one.
        next_y = row_y + row_depth + (GAP_CM if row_depth > 0 else 0)
        for width, depth, rotated in _orientations(item):
            if width <= desk.width_cm and next_y + depth <= desk.depth_cm:
                placements.append(Placement(item.id, 0.0, next_y, width, depth, rotated))
                row_y, row_x, row_depth = next_y, width, depth
                placed = True
                break
        if not placed:
            unplaced.append(item)

    return placements, unplaced


def _orientations(item: Item):
    yield item.width_cm, item.depth_cm, False
    if item.width_cm != item.depth_cm:
        yield item.depth_cm, item.width_cm, True
