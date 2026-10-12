"""The Desk layout pane: the suggested layout, drawn from above, and why."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QToolTip, QVBoxLayout, QWidget

from cleanmydesk.document import ProjectDocument
from cleanmydesk.engine.layout import ARM_REACH_CM, EASY_REACH_CM
from cleanmydesk.ui.suggestions import LayoutSuggestions

MARGIN = 16
NOTE = "Suggested layout. You sit at the bottom edge. Hover over an item to see why it is there."


class DeskLayoutView(QWidget):
    def __init__(self, doc: ProjectDocument, suggestions: LayoutSuggestions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.suggestions = suggestions
        self.setMinimumSize(200, 140)
        self.setMouseTracking(True)
        self._item_rects: list[tuple[QRectF, str]] = []  # (rect on screen, item id), for tooltips
        suggestions.changed.connect(self.update)

    def sizeHint(self) -> QSize:
        return QSize(560, 320)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ToolTip:
            for rect, item_id in self._item_rects:
                if rect.contains(QPointF(event.pos())):
                    item = self.doc.project.item(item_id)
                    reason = self.suggestions.result.reasons.get(item_id, "")
                    QToolTip.showText(event.globalPos(), f"<b>{item.name}</b><br>{reason}", self)
                    return True
            QToolTip.hideText()
            event.ignore()
            return True
        return super().event(event)

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
        result = self.suggestions.result
        self._item_rects = []

        painter.setPen(muted)
        top_note = metrics.elidedText(NOTE, Qt.TextElideMode.ElideRight, self.width() - 2 * MARGIN)
        painter.drawText(MARGIN, MARGIN + metrics.ascent(), top_note)
        bottom_lines = [f"Desk: {desk.width_cm:g} × {desk.depth_cm:g} cm."]
        if result.off_desk:
            names = ", ".join(item.name for item in result.off_desk)
            bottom_lines.append(f"Put away (no room on the desk): {names}")

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

        # Reach zones (readme section 3.3), centered where the user sits.
        seat = QPointF(desk_rect.center().x(), desk_rect.bottom())
        painter.save()
        painter.setClipRect(desk_rect)
        zone_color = QColor(accent)
        for radius_cm, alpha in ((ARM_REACH_CM, 14), (EASY_REACH_CM, 22)):
            zone_color.setAlpha(alpha)
            painter.setBrush(zone_color)
            radius = radius_cm * scale
            path = QPainterPath()
            path.addEllipse(seat, radius, radius)
            painter.drawPath(path)
        painter.restore()

        names = {item.id: item.name for item in self.doc.project.items}
        fill = QColor(accent)
        fill.setAlpha(60)
        for placement in result.placements:
            rect = QRectF(
                desk_rect.left() + placement.x_cm * scale,
                desk_rect.top() + placement.y_cm * scale,
                placement.width_cm * scale,
                placement.depth_cm * scale,
            )
            self._item_rects.append((rect, placement.item_id))
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


class DeskLayoutPanel(QWidget):
    """The drawing, with the reason for every item listed underneath."""

    def __init__(self, doc: ProjectDocument, suggestions: LayoutSuggestions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.suggestions = suggestions
        self.view = DeskLayoutView(doc, suggestions)
        self.reasons = QListWidget()
        self.reasons.setWordWrap(True)
        self.reasons.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.reasons.setMaximumHeight(130)
        heading = QLabel("Why things are here")
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(self.view, 1)
        layout.addWidget(heading)
        layout.addWidget(self.reasons)
        self._heading = heading
        suggestions.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.reasons.clear()
        result = self.suggestions.result
        for item in self.doc.project.items:
            reason = result.reasons.get(item.id)
            if reason:
                QListWidgetItem(f"{item.name}: {reason}", self.reasons)
        has_items = bool(self.doc.project.items)
        self._heading.setVisible(has_items)
        self.reasons.setVisible(has_items)
