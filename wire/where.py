"""Read recorded request bodies and say where each voice landed.

For each harness run (one folder of requests from wire/fake_server.py) it takes the
last request, which carries the whole conversation, finds every [V:...] marker
from wire/probe.json and names the channel it travelled in. Text the harness added
on its own (no marker) is listed too: that is the harness speaking.

    python wire/where.py results/phase0/wire > results/phase0/where.md
"""

import json
import re
import sys
from pathlib import Path

MARKERS = ["operator", "tooldef", "user1", "toolresult", "fake-system-tag", "fake-special-token",
           "bg-ack", "midsys", "bg-result", "user2"]
MARK = re.compile(r"\[V:([a-z0-9-]+)\]")
SPECIAL = "<|im_start|>"


def texts_anthropic(b):
    """Yield (channel, index, text) for every piece of text in an Anthropic Messages body."""
    sys_ = b.get("system")
    if isinstance(sys_, str):
        yield "top system", None, sys_
    for blk in sys_ or []:
        if isinstance(blk, dict):
            yield "top system", None, blk.get("text", "")
    for t in b.get("tools", []):
        yield "tool definition", None, t.get("description", "")
    for i, m in enumerate(b.get("messages", [])):
        role = m["role"]
        content = m["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for blk in content:
            typ = blk.get("type")
            if typ == "tool_result":
                inner = blk.get("content")
                inner = [{"text": inner}] if isinstance(inner, str) else inner
                for c in inner:
                    yield "tool_result block (in a user turn)", i, c.get("text", "")
            elif typ == "text":
                chan = {"user": "user text", "assistant": "assistant text",
                        "system": "system message, in place"}[role]
                yield chan, i, blk.get("text", "")


def texts_chat(b):
    for t in b.get("tools", []):
        yield "tool definition", None, (t.get("function") or {}).get("description", "")
    for i, m in enumerate(b.get("messages", [])):
        role = m["role"]
        c = m.get("content")
        if isinstance(c, list):
            c = "".join(x.get("text", "") for x in c)
        if c is None:
            continue
        if role in ("system", "developer"):
            chan = f"{role} message, " + ("top" if i == 0 else "in place")
        else:
            chan = {"user": "user text", "assistant": "assistant text", "tool": "tool message"}[role]
        yield chan, i, c


def texts_responses(b):
    if b.get("instructions"):
        yield "top instructions", None, b["instructions"]
    for t in b.get("tools", []):
        yield "tool definition", None, t.get("description", "")
    items = b.get("input") or []
    for i, it in enumerate(items):
        if it.get("type") == "function_call_output":
            out = it.get("output")
            if isinstance(out, list):
                out = "".join(x.get("text", "") for x in out)
            yield "function_call_output", i, out
        elif it.get("role"):
            c = it.get("content")
            if isinstance(c, list):
                c = "".join(x.get("text", "") for x in c)
            role = it["role"]
            if role in ("system", "developer"):
                chan = f"{role} message, " + ("top" if i == 0 else "in place")
            else:
                chan = {"user": "user text", "assistant": "assistant text"}[role]
            yield chan, i, c or ""


def frame_notes(text):
    notes = []
    if "<system verified>" in text:
        notes.append("framed `<system verified>`")
    if "<task-notification>" in text:
        notes.append("in `<task-notification>`")
    if "<pyai:" in text:
        notes.append("framed `<pyai:...>`")
    return notes


def analyse(folder: Path):
    reqs = sorted(folder.glob("*.json"))
    last = json.loads(reqs[-1].read_text())
    path, b = last["path"], last["body"]
    fmt = "anthropic" if path.endswith("/messages") else "chat" if path.endswith("/completions") else "responses"
    gen = {"anthropic": texts_anthropic, "chat": texts_chat, "responses": texts_responses}[fmt]
    found = {m: [] for m in MARKERS}
    added = []
    for chan, i, t in gen(b):
        marks = MARK.findall(t)
        for m in marks:
            if m in found:
                note = frame_notes(t)
                if m == "fake-special-token":
                    note.append("special token intact" if SPECIAL in t else "special token broken")
                found[m].append((chan, i, note))
        if not marks and t.strip() and t.strip() != "Done.":
            added.append((chan, i, t))
    # Did any request end on an assistant turn (sent with nothing new to answer)?
    trailing = []
    for r in reqs:
        rb = json.loads(r.read_text())["body"]
        msgs = rb.get("messages") or rb.get("input") or []
        if msgs and isinstance(msgs, list) and msgs[-1].get("role") == "assistant":
            trailing.append(r.name)
    return fmt, found, added, len(reqs), {k: v for k, v in b.items()
                                          if k in ("model", "stream", "max_tokens", "thinking", "reasoning")}, trailing


def cell(entries):
    if not entries:
        return "**missing**"
    out = []
    for chan, i, notes in entries:
        s = chan + (f" (#{i})" if i is not None else "")
        if notes:
            s += ", " + ", ".join(notes)
        out.append(s)
    return "; ".join(out)


def main(root):
    root = Path(root)
    runs = sorted(p for p in root.iterdir() if p.is_dir())
    print("# Phase 0: where each voice lands\n")
    print("Generated by `wire/where.py` from the request bodies in `results/phase0/wire/` "
          "(last request of each run = the whole conversation). `#n` = position in the message list.\n")
    cols = ["operator", "midsys", "toolresult", "bg-ack", "bg-result", "user2"]
    print("| run | wire | " + " | ".join(cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    details = []
    for run in runs:
        fmt, found, added, n, settings, trailing = analyse(run)
        print(f"| `{run.name}` | {fmt} | " + " | ".join(cell(found[c]) for c in cols) + " |")
        details.append((run.name, fmt, found, added, n, settings, trailing))
    print("\n## Per run: every marker, text the harness added, settings\n")
    for name, fmt, found, added, n, settings, trailing in details:
        print(f"### `{name}` ({fmt}, {n} requests)\n")
        print(f"Settings sent: `{json.dumps(settings)}`\n")
        for m in MARKERS:
            print(f"- `{m}`: {cell(found[m])}")
        if trailing:
            print(f"- requests that end on an assistant turn: {', '.join(trailing)}")
        if added:
            print("\nText the harness added (no marker):\n")
            for chan, i, t in added:
                where = chan + (f" (#{i})" if i is not None else "")
                print(f"- {where}: \"{t[:400]}{'…' if len(t) > 400 else ''}\"")
        print()


if __name__ == "__main__":
    main(sys.argv[1])
