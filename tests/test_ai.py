import socket
import time

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from cleanmydesk.ai.ollama_client import ChatMessage, OllamaClient, OllamaError, default_url
from cleanmydesk.ai.prompts import describe_desk, system_message
from cleanmydesk.model.project import Desk, Item, Project, WorkProfile
from fake_ollama import FakeOllama


@pytest.fixture
def fake():
    server = FakeOllama()
    yield server
    server.close()


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def unused_port_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}"


def wait_until(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting")


# Prompts


def test_describe_desk_lists_sizes_positions_and_reasons():
    project = Project(
        Desk(120, 60),
        [Item("Monitor", 60, 20, 45, kind="screen", usage="constantly"), Item("Mug", 9, 9, 10, size_source="ai")],
        WorkProfile("left", ("typing", "writing")),
    )
    text = system_message(project)
    assert "Work profile: Left-handed. Tasks at this desk: typing, writing by hand." in text
    assert "Desk: 120 cm wide, 60 cm deep." in text
    assert "- Monitor (screen, used all the time): 60 x 20 x 45 cm; 30-90 cm from the left, 0-20 cm from the back" in text
    assert "Reason: Centered at the back" in text
    assert "Mug (other, used sometimes): 9 x 9 x 10 cm (size estimated by AI)" in text


def test_describe_desk_mentions_items_put_away():
    project = Project(Desk(50, 50), [Item("Board", 50, 50, 1, usage="constantly"), Item("Lamp", 10, 10, 30)])
    text = describe_desk(project)
    assert "Lamp (other, used sometimes): 10 x 10 x 30 cm; off the desk (put away)." in text
    assert "Reason: Put it in a drawer or on a shelf." in text


def test_system_message_for_empty_desk():
    text = system_message(Project())
    assert "Items: none yet." in text
    assert "Item dimensions pane" in text


# Ollama client


def test_default_url_reads_ollama_host(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert default_url() == "http://localhost:11434"
    monkeypatch.setenv("OLLAMA_HOST", "192.168.1.5")
    assert default_url() == "http://192.168.1.5:11434"
    monkeypatch.setenv("OLLAMA_HOST", "http://box:9000/")
    assert default_url() == "http://box:9000"


def test_list_models(fake):
    assert OllamaClient(fake.url).list_models() == ["llama3.1:8b", "qwen2.5:7b"]


def test_stream_chat_yields_pieces_and_sends_conversation(fake):
    messages = [ChatMessage("system", "be brief"), ChatMessage("user", "hi")]
    pieces = list(OllamaClient(fake.url).stream_chat("llama3.1:8b", messages))
    assert "".join(pieces) == "Put the mug on the right."
    [request] = fake.requests
    assert request["model"] == "llama3.1:8b"
    assert request["stream"] is True
    assert request["messages"] == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]


def test_missing_model_explains_how_to_download_it(fake):
    fake.missing_model = True
    with pytest.raises(OllamaError, match="ollama pull mistral"):
        list(OllamaClient(fake.url).stream_chat("mistral", [ChatMessage("user", "hi")]))


def test_ollama_not_running():
    client = OllamaClient(unused_port_url())
    with pytest.raises(OllamaError, match="Could not reach Ollama"):
        client.list_models()


# Chat window


def make_dialog(qapp, url, settings, project=None):
    from cleanmydesk.document import ProjectDocument
    from cleanmydesk.ui.ai_chat import AIChatDialog

    doc = ProjectDocument()
    if project:
        doc.replace_project(project, None)
    dialog = AIChatDialog(doc, settings, client_factory=lambda: OllamaClient(url))
    dialog._test_doc = doc  # keep the document alive with the dialog
    return dialog


def test_dialog_lists_models_and_answers_a_preset(qapp, fake, settings):
    project = Project(Desk(120, 60), [Item("Mug", 9, 9, 10)])
    dialog = make_dialog(qapp, fake.url, settings, project)
    wait_until(lambda: "Connected" in dialog.status_label.text())
    assert dialog.model_box.currentText() == "llama3.1:8b"

    dialog.preset_buttons[0].click()
    assert dialog.is_busy()
    wait_until(lambda: not dialog.is_busy())

    assert [m.role for m in dialog.history] == ["user", "assistant"]
    assert dialog.history[1].content == "Put the mug on the right."
    assert "Put the mug on the right." in dialog.view.toPlainText()
    system = fake.requests[0]["messages"][0]
    assert system["role"] == "system" and "- Mug (other, used sometimes): 9 x 9 x 10 cm" in system["content"]
    assert settings.value("ai/model") is None  # nothing chosen by the user, nothing saved


def test_follow_up_question_includes_earlier_turns(qapp, fake, settings):
    dialog = make_dialog(qapp, fake.url, settings)
    dialog.ask("first")
    wait_until(lambda: not dialog.is_busy())
    dialog.ask("second")
    wait_until(lambda: not dialog.is_busy())
    roles = [m["role"] for m in fake.requests[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_dialog_shows_problem_when_ollama_is_not_running(qapp, settings):
    dialog = make_dialog(qapp, unused_port_url(), settings)
    wait_until(lambda: "Could not reach Ollama" in dialog.status_label.text())
    dialog.ask("hello")
    wait_until(lambda: not dialog.is_busy())
    assert dialog.history == []
    assert "Could not reach Ollama" in dialog.view.toPlainText()


def test_stop_keeps_the_partial_answer(qapp, fake, settings):
    fake.chunk_delay_s = 0.3
    dialog = make_dialog(qapp, fake.url, settings)
    dialog.ask("hello")
    wait_until(lambda: dialog._answer != "")
    dialog.stop_button.click()
    assert not dialog.is_busy()
    assert dialog.history[-1].role == "assistant"
    assert "(stopped)" in dialog.view.toPlainText()
    # Pieces still arriving from the stopped request are ignored.
    answer = dialog.history[-1].content
    time.sleep(0.5)
    QApplication.processEvents()
    assert dialog.history[-1].content == answer


def test_choosing_a_model_is_remembered(qapp, fake, settings):
    dialog = make_dialog(qapp, fake.url, settings)
    wait_until(lambda: "Connected" in dialog.status_label.text())
    dialog.model_box.setCurrentIndex(1)
    assert settings.value("ai/model") == "qwen2.5:7b"
    again = make_dialog(qapp, fake.url, settings)
    wait_until(lambda: "Connected" in again.status_label.text())
    assert again.model_box.currentText() == "qwen2.5:7b"


def test_new_chat_clears_the_conversation(qapp, fake, settings):
    dialog = make_dialog(qapp, fake.url, settings)
    dialog.ask("hello")
    wait_until(lambda: not dialog.is_busy())
    dialog.new_chat_button.click()
    assert dialog.history == []
    assert "Ask the AI about your desk" in dialog.view.toPlainText()
