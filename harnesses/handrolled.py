"""Hand-rolled harness: the raw provider SDK and a loop we write ourselves.

It is the bench's control: every voice goes in the channel built for it.
    operator          top-level system (Claude) / first system message (OpenAI)
    mid-conversation  a system message in place (both APIs accept one, 2026-11)
    tool result       tool_result block (Claude) / role "tool" (OpenAI)
    background result an invented check_job call + its result, so it stays a tool result
                      (--naive: a user message in <task-notification> tags instead,
                      the way most harnesses deliver it)

    python harnesses/handrolled.py --provider anthropic --base-url http://127.0.0.1:8765/handrolled-anthropic
    python harnesses/handrolled.py --provider openai-chat --base-url http://127.0.0.1:8765/handrolled-openai-chat/v1

Phase 0 points --base-url at wire/fake_server.py ($0). Phases 1-2 import the
`Conversation` helpers below to send real requests.
"""

import argparse
import json
import os
from pathlib import Path

PROBE = json.loads((Path(__file__).parent.parent / "wire" / "probe.json").read_text())

ANTHROPIC_TOOLS = [
    {"name": "read_email", "description": PROBE["tools"]["read_email"],
     "input_schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
    {"name": "fetch_report", "description": PROBE["tools"]["fetch_report"],
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_job", "description": PROBE["tools"]["check_job"],
     "input_schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
]
OPENAI_TOOLS = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                   "parameters": t["input_schema"]}} for t in ANTHROPIC_TOOLS]


def run_tool(name, args):
    return {"read_email": PROBE["email"], "fetch_report": PROBE["bg_ack"]}.get(name, "unknown tool")


def drive_anthropic(base_url, naive):
    import anthropic
    client = anthropic.Anthropic(base_url=base_url, api_key=os.environ.get("ANTHROPIC_API_KEY", "fake"))
    messages = [{"role": "user", "content": PROBE["user1"]}]

    def ask():
        r = client.messages.create(model="claude-haiku-5-5", max_tokens=500, system=PROBE["system"],
                                   tools=ANTHROPIC_TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
        return r

    r = ask()
    messages.append({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": b.id, "content": run_tool(b.name, b.input)}
        for b in r.content if b.type == "tool_use"]})
    messages.append({"role": "system", "content": PROBE["midsys"]})
    ask()
    if naive:
        messages.append({"role": "user", "content": f"<task-notification>{PROBE['bg_result']}</task-notification>"})
    else:
        # The last message is the model's own reply; the invented call joins that turn,
        # since the Messages API merges consecutive turns of one role anyway.
        messages[-1]["content"].append(
            {"type": "tool_use", "id": "toolu_bg_42", "name": "check_job", "input": {"id": 42}})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_bg_42", "content": PROBE["bg_result"]}]})
    ask()
    messages.append({"role": "user", "content": PROBE["user2"]})
    ask()


def drive_openai_chat(base_url, naive):
    import openai
    client = openai.OpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "fake"))
    messages = [{"role": "system", "content": PROBE["system"]},
                {"role": "user", "content": PROBE["user1"]}]

    def ask():
        r = client.chat.completions.create(model="gpt-5.4-nano", messages=messages, tools=OPENAI_TOOLS)
        m = r.choices[0].message
        messages.append(m.model_dump(exclude_none=True))
        return m

    m = ask()
    for tc in m.tool_calls or []:
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": run_tool(tc.function.name, json.loads(tc.function.arguments))})
    messages.append({"role": "system", "content": PROBE["midsys"]})
    ask()
    if naive:
        messages.append({"role": "user", "content": f"<task-notification>{PROBE['bg_result']}</task-notification>"})
    else:
        messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_bg_42", "type": "function",
             "function": {"name": "check_job", "arguments": json.dumps({"id": 42})}}]})
        messages.append({"role": "tool", "tool_call_id": "call_bg_42", "content": PROBE["bg_result"]})
    ask()
    messages.append({"role": "user", "content": PROBE["user2"]})
    ask()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openai-chat"], required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--naive", action="store_true")
    a = ap.parse_args()
    {"anthropic": drive_anthropic, "openai-chat": drive_openai_chat}[a.provider](a.base_url, a.naive)
