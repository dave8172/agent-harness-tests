"""A fake model endpoint that records every request body a harness sends.

Speaks three wire formats, streaming and not:
    POST /<label>/v1/messages          Anthropic Messages
    POST /<label>/v1/chat/completions  OpenAI Chat Completions
    POST /<label>/v1/responses         OpenAI Responses

<label> is the first path segment of the base URL each harness is given, so one
server records every harness apart: base_url = http://127.0.0.1:8765/pydantic-anthropic

The model is scripted, not real ($0): the first request in a conversation (no
assistant turn yet) gets a call to every probe tool it offers (read_email,
fetch_report); every later request gets the text "Done." Each request body is
saved as <out>/<label>/<NN>.json, headers without keys.

    python wire/fake_server.py --out results/phase0/wire --port 8765
"""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROBE_CALLS = {"read_email": {"id": 1}, "fetch_report": {}}
COUNTERS: dict[str, int] = {}
LOCK = threading.Lock()
OUT = Path(".")


def save(label: str, path: str, headers: dict, body: dict) -> None:
    with LOCK:
        n = COUNTERS.get(label, 0) + 1
        COUNTERS[label] = n
    d = OUT / label
    d.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in headers.items()
            if k.lower() not in ("authorization", "x-api-key", "cookie")}
    (d / f"{n:02d}.json").write_text(json.dumps(
        {"path": path, "headers": keep, "body": body}, indent=2, ensure_ascii=False))


def tool_names(body: dict, fmt: str) -> list[str]:
    names = []
    for t in body.get("tools") or []:
        if fmt == "chat":
            names.append((t.get("function") or {}).get("name"))
        else:
            names.append(t.get("name"))
    return [n for n in names if n in PROBE_CALLS]


def has_assistant_turn(body: dict, fmt: str) -> bool:
    if fmt in ("anthropic", "chat"):
        return any(m.get("role") == "assistant" for m in body.get("messages", []))
    items = body.get("input") or []
    if isinstance(items, str):
        return False
    return any(i.get("type") in ("function_call", "function_call_output")
               or i.get("role") == "assistant" for i in items)


# ── Replies ──────────────────────────────────────────────────────────

def anthropic_reply(calls):
    if calls:
        content = [{"type": "tool_use", "id": f"toolu_fake_{i}", "name": n, "input": PROBE_CALLS[n]}
                   for i, n in enumerate(calls)]
        stop = "tool_use"
    else:
        content = [{"type": "text", "text": "Done."}]
        stop = "end_turn"
    return {"id": "msg_fake", "type": "message", "role": "assistant", "model": "fake",
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1}}


def anthropic_sse(msg):
    ev = []
    start = dict(msg, content=[], stop_reason=None)
    ev.append(("message_start", {"type": "message_start", "message": start}))
    for i, b in enumerate(msg["content"]):
        if b["type"] == "text":
            ev.append(("content_block_start", {"type": "content_block_start", "index": i,
                                               "content_block": {"type": "text", "text": ""}}))
            ev.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                               "delta": {"type": "text_delta", "text": b["text"]}}))
        else:
            ev.append(("content_block_start", {"type": "content_block_start", "index": i,
                                               "content_block": dict(b, input={})}))
            ev.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                               "delta": {"type": "input_json_delta",
                                                         "partial_json": json.dumps(b["input"])}}))
        ev.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    ev.append(("message_delta", {"type": "message_delta",
                                 "delta": {"stop_reason": msg["stop_reason"], "stop_sequence": None},
                                 "usage": {"output_tokens": 1}}))
    ev.append(("message_stop", {"type": "message_stop"}))
    return ev


def chat_reply(calls):
    if calls:
        msg = {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call_fake_{i}", "type": "function",
             "function": {"name": n, "arguments": json.dumps(PROBE_CALLS[n])}}
            for i, n in enumerate(calls)]}
        finish = "tool_calls"
    else:
        msg = {"role": "assistant", "content": "Done."}
        finish = "stop"
    return {"id": "chatcmpl_fake", "object": "chat.completion", "created": int(time.time()),
            "model": "fake", "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def chat_sse(resp):
    msg = resp["choices"][0]["message"]
    base = {k: resp[k] for k in ("id", "object", "created", "model")}
    base["object"] = "chat.completion.chunk"
    ev = []
    if msg.get("tool_calls"):
        for i, tc in enumerate(msg["tool_calls"]):
            ev.append((None, dict(base, choices=[{"index": 0, "delta": {"role": "assistant", "tool_calls": [
                dict(tc, index=i)]}, "finish_reason": None}])))
    else:
        ev.append((None, dict(base, choices=[{"index": 0, "delta": {"role": "assistant", "content": msg["content"]},
                                               "finish_reason": None}])))
    ev.append((None, dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": resp["choices"][0]["finish_reason"]}],
                          usage=resp["usage"])))
    return ev


def responses_reply(calls):
    if calls:
        output = [{"type": "function_call", "id": f"fc_fake_{i}", "call_id": f"call_fake_{i}", "name": n,
                   "arguments": json.dumps(PROBE_CALLS[n]), "status": "completed"}
                  for i, n in enumerate(calls)]
    else:
        output = [{"type": "message", "id": "msg_fake", "role": "assistant", "status": "completed",
                   "content": [{"type": "output_text", "text": "Done.", "annotations": []}]}]
    return {"id": "resp_fake", "object": "response", "created_at": int(time.time()), "model": "fake",
            "status": "completed", "output": output, "parallel_tool_calls": True, "tool_choice": "auto",
            "tools": [], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                                   "input_tokens_details": {"cached_tokens": 0},
                                   "output_tokens_details": {"reasoning_tokens": 0}}}


def responses_sse(resp):
    ev = []
    seq = 0

    def add(t, **kw):
        nonlocal seq
        ev.append((t, dict(type=t, sequence_number=seq, **kw)))
        seq += 1
    add("response.created", response=dict(resp, status="in_progress", output=[]))
    for i, item in enumerate(resp["output"]):
        if item["type"] == "function_call":
            add("response.output_item.added", output_index=i, item=dict(item, arguments="", status="in_progress"))
            add("response.function_call_arguments.delta", output_index=i, item_id=item["id"], delta=item["arguments"])
            add("response.function_call_arguments.done", output_index=i, item_id=item["id"], arguments=item["arguments"])
        else:
            add("response.output_item.added", output_index=i, item=dict(item, content=[], status="in_progress"))
            add("response.content_part.added", output_index=i, item_id=item["id"], content_index=0,
                part={"type": "output_text", "text": "", "annotations": []})
            add("response.output_text.delta", output_index=i, item_id=item["id"], content_index=0,
                delta=item["content"][0]["text"])
        add("response.output_item.done", output_index=i, item=item)
    add("response.completed", response=resp)
    return ev


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        body = json.loads(raw or b"{}")
        parts = self.path.strip("/").split("/")
        label = parts[0]
        path = "/" + "/".join(parts[1:])
        save(label, path, dict(self.headers), body)
        if path.endswith("/messages"):
            fmt = "anthropic"
        elif path.endswith("/chat/completions"):
            fmt = "chat"
        elif path.endswith("/responses"):
            fmt = "responses"
        else:
            self.send_error(404)
            return
        calls = [] if has_assistant_turn(body, fmt) else tool_names(body, fmt)
        reply = {"anthropic": anthropic_reply, "chat": chat_reply, "responses": responses_reply}[fmt](calls)
        if body.get("stream"):
            events = {"anthropic": anthropic_sse, "chat": chat_sse, "responses": responses_sse}[fmt](reply)
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            for name, data in events:
                chunk = (f"event: {name}\n" if name else "") + f"data: {json.dumps(data)}\n\n"
                self.wfile.write(chunk.encode())
            if fmt == "chat":
                self.wfile.write(b"data: [DONE]\n\n")
        else:
            out = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/phase0/wire")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    OUT = Path(a.out)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
