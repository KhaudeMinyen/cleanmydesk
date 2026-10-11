"""Sidebar icons, drawn from small inline SVGs so no image files are needed."""

from __future__ import annotations

import math

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


def _gear_paths() -> list[str]:
    paths = ["M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7z"]
    for step in range(8):
        angle = step * math.pi / 4
        x1, y1 = 12 + 6 * math.cos(angle), 12 + 6 * math.sin(angle)
        x2, y2 = 12 + 9 * math.cos(angle), 12 + 9 * math.sin(angle)
        paths.append(f"M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}")
    paths.append("M12 6a6 6 0 1 0 0 12a6 6 0 1 0 0-12z")
    return paths


# Each icon is a list of SVG path strings on a 24 x 24 grid, drawn as lines.
ICON_PATHS = {
    "undo": ["M9 14 4 9l5-5", "M4 9h10.5a5.5 5.5 0 0 1 0 11H11"],
    "redo": ["M15 14l5-5-5-5", "M20 9H9.5a5.5 5.5 0 0 0 0 11H13"],
    "new": [
        "M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z",
        "M14 3v5h5",
        "M12 11v6",
        "M9 14h6",
    ],
    "save": [
        "M6 3h10l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z",
        "M8 3v5h7V3",
        "M8 21v-6h8v6",
    ],
    "open": ["M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"],
    "add_pane": ["M4 4h16v16H4z", "M12 8v8", "M8 12h8"],
    "ai": ["M10 4Q11 11 18 12Q11 13 10 20Q9 13 2 12Q9 11 10 4z", "M19 2v6", "M16 5h6"],
    "gear": _gear_paths(),
}


def _svg(paths: list[str], color: str) -> bytes:
    body = "".join(f'<path d="{d}"/>' for d in paths)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    ).encode()


def _pixmap(paths: list[str], color: str, size: int) -> QPixmap:
    ratio = 2.0  # draw at double size so icons stay sharp on high-DPI screens
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(_svg(paths, color))).render(painter, QRectF(pixmap.rect()))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon(name: str, size: int = 24) -> QIcon:
    palette = QApplication.palette()
    normal = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText).name()
    disabled = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText).name()
    result = QIcon()
    result.addPixmap(_pixmap(ICON_PATHS[name], normal, size), QIcon.Mode.Normal)
    result.addPixmap(_pixmap(ICON_PATHS[name], disabled, size), QIcon.Mode.Disabled)
    return result
