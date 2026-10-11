"""A pane with a title bar and + / − buttons to expand and collapse it."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cleanmydesk.document import PANE_CLOSED, PANE_COLLAPSED, PANE_EXPANDED

MAX_SIZE = 16777215  # Qt's QWIDGETSIZE_MAX


def _small_button(text: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setText(text)
    button.setToolTip(tooltip)
    button.setAutoRaise(True)
    button.setFixedSize(24, 24)
    font = button.font()
    font.setPointSizeF(font.pointSizeF() + 3)
    font.setBold(True)
    button.setFont(font)
    return button


class VerticalLabel(QWidget):
    """Text drawn bottom-to-top, for a pane collapsed to a side strip."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        return QSize(metrics.height() + 4, metrics.horizontalAdvance(self._text) + 8)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.translate(0, self.height())
        painter.rotate(-90)
        painter.drawText(4, 0, self.height() - 4, self.width(), Qt.AlignmentFlag.AlignVCenter, self._text)


class Pane(QFrame):
    """One of the main window's panes.

    `collapse_to` decides what a collapsed pane looks like: "top" keeps
    only the title bar (for panes stacked on top of each other), "side"
    shrinks the pane to a thin vertical strip (for a pane in a column).

    The +/− buttons only emit signals. The pane area turns those into
    undoable commands and then calls `apply_state`.
    """

    expand_clicked = Signal()
    collapse_clicked = Signal()

    def __init__(
        self,
        pane_id: str,
        title: str,
        content: QWidget,
        collapse_to: str = "top",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pane_id = pane_id
        self.title = title
        self.content = content
        self.collapse_to = collapse_to
        self.state = PANE_EXPANDED
        self.last_expanded_size = 0  # along the splitter, saved when collapsing

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName(f"pane_{pane_id}")

        # Title bar: "Title ............ + −"
        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 2, 2, 2)
        title_label = QLabel(title)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        self.expand_button = _small_button("+", f"Expand {title}")
        self.collapse_button = _small_button("−", f"Collapse {title}")
        header_layout.addWidget(self.expand_button)
        header_layout.addWidget(self.collapse_button)

        # Thin strip used when a "side" pane is collapsed.
        self.strip = QWidget()
        strip_layout = QVBoxLayout(self.strip)
        strip_layout.setContentsMargins(2, 2, 2, 2)
        self.strip_expand_button = _small_button("+", f"Expand {title}")
        self.strip_collapse_button = _small_button("−", f"Collapse {title}")
        self.strip_collapse_button.setEnabled(False)
        strip_layout.addWidget(self.strip_expand_button)
        strip_layout.addWidget(self.strip_collapse_button)
        strip_layout.addWidget(VerticalLabel(title), 0, Qt.AlignmentFlag.AlignHCenter)
        strip_layout.addStretch(1)
        self.strip.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.strip)
        layout.addWidget(content, 1)

        for button in (self.expand_button, self.strip_expand_button):
            button.clicked.connect(self.expand_clicked)
        self.collapse_button.clicked.connect(self.collapse_clicked)
        self._update_buttons()

    def apply_state(self, state: str) -> None:
        if state == self.state:
            return
        if self.state == PANE_EXPANDED and state != PANE_EXPANDED:
            self.last_expanded_size = self.width() if self.collapse_to == "side" else self.height()
        self.state = state

        self.setVisible(state != PANE_CLOSED)
        expanded = state == PANE_EXPANDED
        side_strip = state == PANE_COLLAPSED and self.collapse_to == "side"
        self.content.setVisible(expanded)
        self.header.setVisible(not side_strip)
        self.strip.setVisible(side_strip)

        self.setMaximumSize(MAX_SIZE, MAX_SIZE)
        if state == PANE_COLLAPSED:
            hint = self.sizeHint()
            if side_strip:
                self.setMaximumWidth(hint.width())
            else:
                self.setMaximumHeight(hint.height())
        self._update_buttons()

    def _update_buttons(self) -> None:
        expanded = self.state == PANE_EXPANDED
        self.expand_button.setEnabled(not expanded)
        self.collapse_button.setEnabled(expanded)
