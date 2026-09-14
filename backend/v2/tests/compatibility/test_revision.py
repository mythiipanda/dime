from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from v2.tests.compatibility.harness import RevisionFingerprint, assert_server_revision


class Handler(BaseHTTPRequestHandler):
    payload = {"revision": "new", "executable_sha256": "sha"}

    def do_GET(self):
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def test_runner_rejects_stale_server_revision():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert_server_revision(base, RevisionFingerprint("new", "sha"))
        with pytest.raises(RuntimeError, match="server revision mismatch"):
            assert_server_revision(base, RevisionFingerprint("expected", "sha"))
    finally:
        server.shutdown()
        server.server_close()
