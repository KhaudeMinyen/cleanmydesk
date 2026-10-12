"""Save and load projects as JSON files (*.cmdesk)."""

from __future__ import annotations

import json
from pathlib import Path

from cleanmydesk.model.project import (
    HANDEDNESS,
    KINDS,
    SIZE_SOURCES,
    TASKS,
    USAGE_LEVELS,
    Desk,
    Item,
    Project,
    WorkProfile,
)

FILE_EXTENSION = ".cmdesk"
FILE_FORMAT = "cleanmydesk-project"
FILE_VERSION = 1


class ProjectFileError(Exception):
    """The file could not be read as a CleanMyDesk project."""


def project_to_dict(project: Project) -> dict:
    return {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "desk": {"width_cm": project.desk.width_cm, "depth_cm": project.desk.depth_cm},
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "width_cm": item.width_cm,
                "depth_cm": item.depth_cm,
                "height_cm": item.height_cm,
                "size_source": item.size_source,
                "kind": item.kind,
                "usage": item.usage,
            }
            for item in project.items
        ],
        "profile": {
            "handedness": project.profile.handedness,
            "tasks": list(project.profile.tasks),
        },
    }


def project_from_dict(data: dict) -> Project:
    try:
        if data.get("format") != FILE_FORMAT:
            raise ProjectFileError("This is not a CleanMyDesk project file.")
        if data.get("version") != FILE_VERSION:
            raise ProjectFileError(
                f"This project uses file version {data.get('version')}, "
                f"but this app reads version {FILE_VERSION}."
            )
        desk = Desk(
            width_cm=_positive(data["desk"]["width_cm"]),
            depth_cm=_positive(data["desk"]["depth_cm"]),
        )
        items = []
        for raw in data["items"]:
            source = raw.get("size_source", "manual")
            if source not in SIZE_SOURCES:
                raise ProjectFileError(f"Unknown size source: {source!r}")
            items.append(
                Item(
                    id=str(raw["id"]),
                    name=str(raw["name"]),
                    width_cm=_positive(raw["width_cm"]),
                    depth_cm=_positive(raw["depth_cm"]),
                    height_cm=_positive(raw["height_cm"]),
                    size_source=source,
                    # Files saved before these were added get the defaults.
                    kind=raw.get("kind") if raw.get("kind") in KINDS else "other",
                    usage=raw.get("usage") if raw.get("usage") in USAGE_LEVELS else "sometimes",
                )
            )
        raw_profile = data.get("profile") or {}
        handedness = raw_profile.get("handedness")
        tasks = [task for task in raw_profile.get("tasks", ["typing"]) if task in TASKS]
        profile = WorkProfile(
            handedness=handedness if handedness in HANDEDNESS else "right",
            tasks=tuple(task for task in TASKS if task in tasks),
        )
    except ProjectFileError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProjectFileError(f"The project file is damaged or incomplete ({exc}).") from exc
    return Project(desk=desk, items=items, profile=profile)


def save_project(project: Project, path: Path) -> None:
    text = json.dumps(project_to_dict(project), indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def load_project(path: Path) -> Project:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectFileError("This file is not a CleanMyDesk project.") from exc
    if not isinstance(data, dict):
        raise ProjectFileError("This file is not a CleanMyDesk project.")
    return project_from_dict(data)


def _positive(value) -> float:
    number = float(value)
    if not number > 0:
        raise ValueError(f"expected a positive number, got {value!r}")
    return number
