"""Top-down drawing of the desk for the Desk layout pane."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

from cleanmydesk.document import ProjectDocument
from cleanmydesk.layout_preview import arrange_items

MARGIN = 16
NOTE = "Preview: AI suggestions are not built yet, so items are lined up by size."


class DeskLayoutView(QWidget):
    def __init__(self, doc: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.setMinimumSize(200, 140)
        for signal in (doc.project_replaced, doc.desk_changed, doc.items_reset):
            signal.connect(self.update)
        doc.item_changed.connect(lambda _item_id: self.update())

    def sizeHint(self) -> QSize:
        return QSize(560, 360)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        text_color = palette.color(QPalette.ColorRole.WindowText)
        muted = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
        accent = palette.color(QPalette.ColorRole.Highlight)
        metrics = QFontMetrics(self.font())
        line = metrics.height()

        desk = self.doc.project.desk
        placements, unplaced = arrange_items(desk, self.doc.project.items)

        # Notes above and below the desk drawing.
        painter.setPen(muted)
        top_note = metrics.elidedText(NOTE, Qt.TextElideMode.ElideRight, self.width() - 2 * MARGIN)
        painter.drawText(MARGIN, MARGIN + metrics.ascent(), top_note)
        bottom_lines = [f"Desk: {desk.width_cm:g} × {desk.depth_cm:g} cm. You sit at the bottom edge."]
        if unplaced:
            names = ", ".join(item.name for item in unplaced)
            bottom_lines.append(f"Does not fit: {names}")

        area = QRectF(
            MARGIN,
            MARGIN + line + 8,
            self.width() - 2 * MARGIN,
            self.height() - 2 * MARGIN - line * (1 + len(bottom_lines)) - 16,
        )
        if area.width() <= 10 or area.height() <= 10:
            return
        scale = min(area.width() / desk.width_cm, area.height() / desk.depth_cm)
        desk_rect = QRectF(0, 0, desk.width_cm * scale, desk.depth_cm * scale)
        desk_rect.moveCenter(area.center())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Base))
        painter.drawRoundedRect(desk_rect, 4, 4)

        names = {item.id: item.name for item in self.doc.project.items}
        fill = QColor(accent)
        fill.setAlpha(50)
        for placement in placements:
            rect = QRectF(
                desk_rect.left() + placement.x_cm * scale,
                desk_rect.top() + placement.y_cm * scale,
                placement.width_cm * scale,
                placement.depth_cm * scale,
            )
            painter.setPen(QPen(accent, 1.5))
            painter.setBrush(fill)
            painter.drawRect(rect)
            label = metrics.elidedText(names[placement.item_id], Qt.TextElideMode.ElideRight, int(rect.width()) - 4)
            if label not in ("", "…") and rect.height() >= line:
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        # Desk edge last, so it stays visible where items touch it.
        painter.setPen(QPen(text_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(desk_rect, 4, 4)

        painter.setPen(muted)
        y = desk_rect.bottom() + 8 + metrics.ascent()
        for text in bottom_lines:
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, self.width() - 2 * MARGIN)
            painter.drawText(QRectF(MARGIN, y - metrics.ascent(), self.width() - 2 * MARGIN, line),
                             Qt.AlignmentFlag.AlignHCenter, text)
            y += line
