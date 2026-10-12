"""A tiny stand-in for the Ollama server, so the AI code can be tested
without downloading a model. It speaks the same /api/tags and /api/chat
protocol as Ollama, with canned answers."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self) -> None:
        self.models = ["llama3.1:8b", "qwen2.5:7b"]
        self.answer = ["Put the ", "mug on the ", "right."]
        self.chunk_delay_s = 0.0
        self.missing_model = False
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                if self.path != "/api/tags":
                    self.send_error(404)
                    return
                self._send_json(200, {"models": [{"name": name} for name in fake.models]})

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(body)
                if fake.missing_model:
                    self._send_json(404, {"error": f"model '{body['model']}' not found"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                try:
                    for piece in fake.answer:
                        line = {"model": body["model"], "message": {"role": "assistant", "content": piece}, "done": False}
                        self.wfile.write((json.dumps(line) + "\n").encode())
                        self.wfile.flush()
                        time.sleep(fake.chunk_delay_s)
                    done = {"model": body["model"], "message": {"role": "assistant", "content": ""}, "done": True}
                    self.wfile.write((json.dumps(done) + "\n").encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the app stopped listening, as Stop does

            def _send_json(self, status: int, data: dict) -> None:
                payload = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
