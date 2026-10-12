"""What the app tells the AI: its instructions and a description of the desk."""

from __future__ import annotations

from cleanmydesk.engine.layout import suggest_layout, zone_of
from cleanmydesk.model.project import HANDEDNESS, KINDS, SIZE_SOURCE_AI, TASKS, USAGE_LEVELS, Project

SYSTEM_PROMPT = """\
You are the desk organization assistant inside CleanMyDesk, an app that \
helps people arrange the items on their desk.

The user's work profile, desk, and items are described below. Sizes are in \
centimeters. Positions are measured from the left edge and from the back \
edge of the desk, as seen from above. The user sits at the front edge.

The arrangement below was suggested by the app's layout engine. The engine \
gives each kind of item a rule (for example, the mouse goes beside the \
keyboard on the dominant-hand side), pulls items the user uses more often \
closer, and searches for the arrangement that fits these rules best. The \
reason it gives for each item is included.

How to answer:
- Be specific and practical. Name the items and say where they are or \
should go.
- When explaining the arrangement, use the reasons given, in your own words.
- You may suggest improvements, but say why.
- Keep answers short: a few bullet points or short paragraphs.
- Only talk about the items listed. Do not invent items.
- If there are no items yet, tell the user to add them in the Item \
dimensions pane.
"""

PRESET_QUESTIONS = {
    "Explain this arrangement": (
        "Explain the suggested arrangement shown in the Desk layout pane. "
        "Why is each item where it is?"
    ),
    "Suggest changes": (
        "Is there anything you would change about the suggested arrangement, "
        "or about which items I keep on my desk? Say what and why."
    ),
    "General tips": (
        "Give me general tips for keeping a desk organized and comfortable "
        "to work at, based on my items and how I work."
    ),
}

ZONE_WORDS = {"easy": "easy-reach zone", "arm": "arm's-reach zone", "stretch": "stretch zone"}


def describe_profile(project: Project) -> str:
    profile = project.profile
    hand = HANDEDNESS.get(profile.handedness, profile.handedness)
    tasks = ", ".join(TASKS[task].lower() for task in profile.tasks if task in TASKS) or "not given"
    return f"Work profile: {hand}. Tasks at this desk: {tasks}."


def describe_desk(project: Project) -> str:
    desk = project.desk
    lines = [f"Desk: {desk.width_cm:g} cm wide, {desk.depth_cm:g} cm deep."]
    if not project.items:
        lines.append("Items: none yet.")
        return "\n".join(lines)

    result = suggest_layout(desk, project.items, project.profile)
    by_id = {placement.item_id: placement for placement in result.placements}
    lines.append("Items, in the suggested arrangement:")
    for item in project.items:
        kind = KINDS.get(item.kind, item.kind).lower()
        usage = USAGE_LEVELS.get(item.usage, item.usage).lower()
        size = f"{item.width_cm:g} x {item.depth_cm:g} x {item.height_cm:g} cm"
        if item.size_source == SIZE_SOURCE_AI:
            size += " (size estimated by AI)"
        placement = by_id.get(item.id)
        if placement is None:
            where = "off the desk (put away)"
        else:
            where = (
                f"{placement.x_cm:.0f}-{placement.x_cm + placement.width_cm:.0f} cm from the left, "
                f"{placement.y_cm:.0f}-{placement.y_cm + placement.depth_cm:.0f} cm from the back, "
                f"in the {ZONE_WORDS[zone_of(desk, placement)]}"
            )
            if placement.rotated:
                where += ", turned sideways"
        lines.append(f"- {item.name} ({kind}, used {usage}): {size}; {where}.")
        lines.append(f"  Reason: {result.reasons[item.id]}")
    return "\n".join(lines)


def system_message(project: Project) -> str:
    """Instructions plus the profile and desk as they are right now."""
    return (
        f"{SYSTEM_PROMPT}\n{describe_profile(project)}\n\n"
        f"The user's desk right now:\n{describe_desk(project)}\n"
    )
