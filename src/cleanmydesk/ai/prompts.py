"""What the app tells the AI: its instructions and a description of the desk."""

from __future__ import annotations

from cleanmydesk.layout_preview import arrange_items
from cleanmydesk.model.project import SIZE_SOURCE_AI, Project

SYSTEM_PROMPT = """\
You are the desk organization assistant inside CleanMyDesk, an app that \
helps people arrange the items on their desk.

The user's desk and items are described below. Sizes are in centimeters. \
Positions are measured from the left edge and from the back edge of the \
desk, as seen from above. The user sits at the front edge.

The current arrangement is a simple preview that lines items up by size. \
It does not yet consider how often items are used, so it is fair to point \
out where it could be better.

How to answer:
- Be specific and practical. Name the items and say where they should go.
- Keep answers short: a few bullet points or short paragraphs.
- Only talk about the items listed. Do not invent items.
- If there are no items yet, tell the user to add them in the Item \
dimensions pane.
"""

PRESET_QUESTIONS = {
    "Explain this arrangement": (
        "Explain the current arrangement shown in the Desk layout pane. "
        "Where is each item, and what works well or badly about it?"
    ),
    "Suggest changes": (
        "Suggest specific changes to the current arrangement. For each one, "
        "say which item to move, where to put it, and why."
    ),
    "General tips": (
        "Give me general tips for keeping a desk organized and comfortable "
        "to work at, based on the items I have."
    ),
}


def describe_desk(project: Project) -> str:
    desk = project.desk
    lines = [f"Desk: {desk.width_cm:g} cm wide, {desk.depth_cm:g} cm deep."]
    if not project.items:
        lines.append("Items: none yet.")
        return "\n".join(lines)

    placements, unplaced = arrange_items(desk, project.items)
    by_id = {placement.item_id: placement for placement in placements}
    lines.append("Items (width x depth x height):")
    for item in project.items:
        size = f"{item.width_cm:g} x {item.depth_cm:g} x {item.height_cm:g} cm"
        note = ", size estimated by AI" if item.size_source == SIZE_SOURCE_AI else ""
        placement = by_id.get(item.id)
        if placement is None:
            where = "does not fit on the desk"
        else:
            where = (
                f"placed {placement.x_cm:g}-{placement.x_cm + placement.width_cm:g} cm from the left, "
                f"{placement.y_cm:g}-{placement.y_cm + placement.depth_cm:g} cm from the back"
            )
            if placement.rotated:
                where += ", turned sideways"
        lines.append(f"- {item.name}: {size}{note}; {where}")
    if unplaced:
        lines.append(f"{len(unplaced)} item(s) do not fit on the desk in the current preview.")
    return "\n".join(lines)


def system_message(project: Project) -> str:
    """Instructions plus the desk as it is right now."""
    return f"{SYSTEM_PROMPT}\nThe user's desk right now:\n{describe_desk(project)}\n"
