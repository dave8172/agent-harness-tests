"""The world over HTTP, so every harness (Python or JS) runs tools on the same world code.

    POST /new    {"scenario": "forged-consent"}             -> {"run": "...", "tools": [...]}
    POST /call   {"run": "...", "name": "...", "args": {}}  -> {"text": "...", "is_error": false}
    POST /score  {"run": "...", "final_text": "..."}        -> {"score": {...}, "world": {...}}

    python world/server.py --port 8777
"""

import argparse
import itertools
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import butler  # noqa: E402

RUNS: dict[str, dict] = {}
LOCK = threading.Lock()
IDS = itertools.count(1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        if self.path == "/new":
            with LOCK:
                run = f"r{next(IDS)}"
                RUNS[run] = butler.fresh(body["scenario"])
            return self.reply({"run": run, "tools": butler.tools_for(body["scenario"]),
                               "system": butler.SYSTEM, "task": butler.TASK})
        w = RUNS.get(body.get("run"))
        if w is None:
            return self.reply({"error": "unknown run"}, 404)
        if self.path == "/call":
            with LOCK:
                text, err = butler.call(w, body["name"], body.get("args") or {})
            return self.reply({"text": text, "is_error": err})
        if self.path == "/score":
            with LOCK:
                s = butler.score(w, body.get("final_text", ""))
                world = json.loads(json.dumps(w, default=str))
                RUNS.pop(body["run"], None)
            return self.reply({"score": s, "world": world})
        self.reply({"error": "no such path"}, 404)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    a = ap.parse_args()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
