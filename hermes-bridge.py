from __future__ import annotations

import hmac
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HERMES_PYTHON = "/Users/yucai/.hermes/hermes-agent/venv/bin/python"
PROFILE = "su_shi_yu"
PROFILE_ROOT = "/Users/yucai/.hermes/profiles/su_shi_yu"
TOKEN = os.environ["HERMES_ANALYSIS_TOKEN"]


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._reply(200, {"status": "ok", "model": "hermes/kimi-k2.6"})
        else:
            self._reply(404, {"detail": "not found"})

    def do_POST(self) -> None:
        if self.path != "/analyze":
            self._reply(404, {"detail": "not found"})
            return
        if not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {TOKEN}"):
            self._reply(401, {"detail": "unauthorized"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 180_000:
                raise ValueError("请求体大小无效")
            payload = json.loads(self.rfile.read(size))
            prompt = str(payload["prompt"])
            result = subprocess.run(
                [HERMES_PYTHON, "-m", "hermes_cli.main", "--profile", PROFILE, "--ignore-rules", "--oneshot", prompt],
                cwd=PROFILE_ROOT,
                text=True,
                capture_output=True,
                timeout=140,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Hermes 未返回有效结果")
            self._reply(200, {"model": "hermes/kimi-k2.6", "output": result.stdout.strip()})
        except Exception as error:
            self._reply(502, {"detail": str(error)})

    def log_message(self, *_: object) -> None:
        return


ThreadingHTTPServer(("127.0.0.1", 8120), Handler).serve_forever()
