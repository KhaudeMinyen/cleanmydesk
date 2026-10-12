"""A pane with a title bar and a − button that closes it.

Closed panes are opened again from the sidebar."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


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


class Pane(QFrame):
    """One of the main window's panes.

    The − button only emits a signal. The pane area turns it into an
    undoable command.
    """

    close_clicked = Signal()

    def __init__(self, pane_id: str, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pane_id = pane_id
        self.title = title
        self.content = content

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName(f"pane_{pane_id}")

        # Title bar: "Title .............. −"
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 2, 2, 2)
        title_label = QLabel(title)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        self.close_button = _small_button("−", f"Close {title}")
        header_layout.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(content, 1)

        self.close_button.clicked.connect(self.close_clicked)
