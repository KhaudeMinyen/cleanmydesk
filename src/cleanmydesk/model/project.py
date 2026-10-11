"""Plain data classes for a CleanMyDesk project (no Qt here)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

SIZE_SOURCE_MANUAL = "manual"
SIZE_SOURCE_AI = "ai"
SIZE_SOURCES = (SIZE_SOURCE_MANUAL, SIZE_SOURCE_AI)

DIMENSION_FIELDS = ("width_cm", "depth_cm", "height_cm")


def new_item_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Desk:
    width_cm: float = 120.0
    depth_cm: float = 60.0


@dataclass
class Item:
    name: str
    width_cm: float
    depth_cm: float
    height_cm: float
    size_source: str = SIZE_SOURCE_MANUAL
    id: str = field(default_factory=new_item_id)


@dataclass
class Project:
    desk: Desk = field(default_factory=Desk)
    items: list[Item] = field(default_factory=list)

    def index_of(self, item_id: str) -> int:
        for row, item in enumerate(self.items):
            if item.id == item_id:
                return row
        raise KeyError(item_id)

    def item(self, item_id: str) -> Item:
        return self.items[self.index_of(item_id)]


def validate_dimension(desk: Desk, item: Item, field_name: str, value: float) -> str | None:
    """Return an error message if `value` is not allowed, else None.

    Sizes must be positive, and the item's footprint must fit on the desk
    in at least one orientation (it may be turned sideways).
    """
    if field_name not in DIMENSION_FIELDS:
        raise ValueError(f"not a dimension: {field_name}")
    if value <= 0:
        return "Sizes must be greater than zero."
    if field_name == "height_cm":
        return None
    width = value if field_name == "width_cm" else item.width_cm
    depth = value if field_name == "depth_cm" else item.depth_cm
    if not footprint_fits(desk, width, depth):
        return (
            f"{item.name or 'This item'} would be {width:g} × {depth:g} cm, "
            f"which is larger than the {desk.width_cm:g} × {desk.depth_cm:g} cm desk."
        )
    return None


def footprint_fits(desk: Desk, width: float, depth: float) -> bool:
    return (width <= desk.width_cm and depth <= desk.depth_cm) or (
        depth <= desk.width_cm and width <= desk.depth_cm
    )
