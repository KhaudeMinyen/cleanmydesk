"""The "Ask AI" window, opened from the sidebar's AI button.

It stays open next to the main window, so the user can keep changing the
desk and ask again. Every question is sent together with the desk as it is
at that moment.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from cleanmydesk.ai.ollama_client import DEFAULT_MODEL, ChatMessage, OllamaClient, OllamaError
from cleanmydesk.ai.prompts import PRESET_QUESTIONS, system_message
from cleanmydesk.document import ProjectDocument

MODEL_SETTING = "ai/model"


class _Bridge(QObject):
    """Carries results from background threads back to the window.

    Each signal carries the id of the request it belongs to, so results
    from a request the user stopped or replaced are ignored.
    """

    models_listed = Signal(int, list)
    models_failed = Signal(int, str)
    chunk = Signal(int, str)
    answer_failed = Signal(int, str)
    answer_done = Signal(int)


class AIChatDialog(QDialog):
    def __init__(
        self,
        doc: ProjectDocument,
        settings: QSettings,
        client_factory: Callable[[], OllamaClient] = OllamaClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.settings = settings
        self.client_factory = client_factory
        self.setWindowTitle("Ask AI - CleanMyDesk")
        self.resize(520, 600)

        self.history: list[ChatMessage] = []  # user and assistant turns sent to the AI
        self.transcript: list[tuple[str, str]] = []  # (kind, text) shown on screen
        self._request_id = 0  # the answer being shown
        self._models_request_id = 0  # the latest check for downloaded models
        self._cancel: threading.Event | None = None
        self._answer = ""
        self._populating = False

        self._bridge = _Bridge(self)
        self._bridge.models_listed.connect(self._on_models_listed)
        self._bridge.models_failed.connect(self._on_models_failed)
        self._bridge.chunk.connect(self._on_chunk)
        self._bridge.answer_failed.connect(self._on_answer_failed)
        self._bridge.answer_done.connect(self._on_answer_done)

        # Model picker
        self.model_box = QComboBox()
        self.model_box.setEditable(True)  # a model name can also be typed in
        self.model_box.setMinimumContentsLength(18)
        self.model_box.setEditText(str(settings.value(MODEL_SETTING, DEFAULT_MODEL)))
        # Connected after the initial text, so only the user's own choices are saved.
        self.model_box.currentTextChanged.connect(self._save_model)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Check Ollama again for downloaded models")
        self.refresh_button.clicked.connect(self.refresh_models)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model"))
        model_row.addWidget(self.model_box, 1)
        model_row.addWidget(self.refresh_button)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setEnabled(False)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)

        # Ready-made questions
        self.preset_buttons: list[QPushButton] = []
        preset_row = QHBoxLayout()
        for label, question in PRESET_QUESTIONS.items():
            button = QPushButton(label)
            button.setToolTip(question)
            button.clicked.connect(lambda _checked=False, q=question: self.ask(q))
            preset_row.addWidget(button)
            self.preset_buttons.append(button)

        # Question box
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask anything about your desk…")
        self.input.returnPressed.connect(self._send_typed)
        self.send_button = QPushButton("Send")
        self.send_button.setDefault(True)
        self.send_button.clicked.connect(self._send_typed)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.hide()
        self.new_chat_button = QPushButton("New chat")
        self.new_chat_button.clicked.connect(self.new_chat)
        input_row = QHBoxLayout()
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_button)
        input_row.addWidget(self.stop_button)
        input_row.addWidget(self.new_chat_button)

        layout = QVBoxLayout(self)
        layout.addLayout(model_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.view, 1)
        layout.addLayout(preset_row)
        layout.addLayout(input_row)

        self._render()
        self.refresh_models()

    # Models

    def refresh_models(self) -> None:
        self._models_request_id += 1
        request_id = self._models_request_id
        self.status_label.setText("Looking for Ollama…")
        client = self.client_factory()

        def work() -> None:
            try:
                models = client.list_models()
            except OllamaError as exc:
                self._bridge.models_failed.emit(request_id, str(exc))
            else:
                self._bridge.models_listed.emit(request_id, models)

        threading.Thread(target=work, daemon=True).start()

    def _on_models_listed(self, request_id: int, models: list) -> None:
        if request_id != self._models_request_id:
            return
        wanted = self.model_box.currentText().strip() or DEFAULT_MODEL
        self._populating = True
        self.model_box.clear()
        self.model_box.addItems(models)
        if wanted in models or not models:
            self.model_box.setEditText(wanted)
        else:
            self.model_box.setCurrentIndex(0)
        self._populating = False
        if models:
            count = f"{len(models)} model{'s' if len(models) != 1 else ''}"
            self.status_label.setText(f"Connected to Ollama ({count} downloaded).")
        else:
            self.status_label.setText(
                f"Ollama is running, but no models are downloaded yet. "
                f"In a terminal, run: ollama pull {DEFAULT_MODEL}"
            )

    def _on_models_failed(self, request_id: int, message: str) -> None:
        if request_id == self._models_request_id:
            self.status_label.setText(message.replace("`", ""))

    def _save_model(self, name: str) -> None:
        if not self._populating and name.strip():
            self.settings.setValue(MODEL_SETTING, name.strip())

    # Asking

    def is_busy(self) -> bool:
        return self._cancel is not None

    def ask(self, question: str) -> None:
        question = question.strip()
        model = self.model_box.currentText().strip()
        if not question or self.is_busy():
            return
        if not model:
            self.transcript.append(("error", "Choose a model first."))
            self._render()
            return

        self.history.append(ChatMessage("user", question))
        self.transcript.append(("user", question))
        self.transcript.append(("assistant", ""))
        self._answer = ""
        messages = [ChatMessage("system", system_message(self.doc.project)), *self.history]

        self._request_id += 1
        request_id = self._request_id
        cancel = threading.Event()
        self._cancel = cancel
        client = self.client_factory()

        def work() -> None:
            stream = client.stream_chat(model, messages)
            try:
                for piece in stream:
                    if cancel.is_set():
                        return
                    self._bridge.chunk.emit(request_id, piece)
            except OllamaError as exc:
                self._bridge.answer_failed.emit(request_id, str(exc))
                return
            finally:
                stream.close()  # also closes the connection, so Ollama stops
            self._bridge.answer_done.emit(request_id)

        threading.Thread(target=work, daemon=True).start()
        self._set_busy(True)
        self._render()

    def stop(self) -> None:
        if not self.is_busy():
            return
        self._cancel.set()
        self._request_id += 1  # ignore anything still arriving
        if self._answer:
            self.history.append(ChatMessage("assistant", self._answer))
            self.transcript[-1] = ("assistant", self._answer + "\n\n*(stopped)*")
        else:
            self.history.pop()
            self.transcript[-1] = ("error", "Stopped before the AI answered.")
        self._set_busy(False)
        self._render()

    def new_chat(self) -> None:
        if self.is_busy():
            self.stop()
        self.history.clear()
        self.transcript.clear()
        self._render()

    def _send_typed(self) -> None:
        text = self.input.text()
        if text.strip() and not self.is_busy():
            self.input.clear()
            self.ask(text)

    def _on_chunk(self, request_id: int, piece: str) -> None:
        if request_id != self._request_id:
            return
        self._answer += piece
        self.transcript[-1] = ("assistant", self._answer)
        self._render()

    def _on_answer_done(self, request_id: int) -> None:
        if request_id != self._request_id:
            return
        if self._answer:
            self.history.append(ChatMessage("assistant", self._answer))
        else:
            self.history.pop()
            self.transcript[-1] = ("error", "The AI sent an empty answer. Try asking again.")
        self._set_busy(False)
        self._render()

    def _on_answer_failed(self, request_id: int, message: str) -> None:
        if request_id != self._request_id:
            return
        if self._answer:
            self.history.append(ChatMessage("assistant", self._answer))
        else:
            self.history.pop()
            self.transcript.pop()  # the empty answer
        self.transcript.append(("error", message))
        self._set_busy(False)
        self._render()

    # Display

    def _set_busy(self, busy: bool) -> None:
        if not busy:
            self._cancel = None
        for widget in (*self.preset_buttons, self.send_button, self.model_box, self.refresh_button):
            widget.setEnabled(not busy)
        self.send_button.setVisible(not busy)
        self.stop_button.setVisible(busy)

    def _render(self) -> None:
        if not self.transcript:
            self.view.setMarkdown(
                "Ask the AI about your desk. It can explain the current arrangement, "
                "suggest changes, or give general tips.\n\n"
                "The AI runs on this computer with Ollama, so your desk details stay private."
            )
            return
        parts = []
        for kind, text in self.transcript:
            if kind == "user":
                parts.append(f"**You:** {text}")
            elif kind == "assistant":
                parts.append(f"**AI:** {text or '*thinking…*'}")
            else:
                parts.append(f"**Problem:** {text}")
        self.view.setMarkdown("\n\n---\n\n".join(parts))
        self.view.moveCursor(QTextCursor.MoveOperation.End)
        self.view.ensureCursorVisible()

    def closeEvent(self, event) -> None:
        self.stop()
        super().closeEvent(event)

