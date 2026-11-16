import json, anthropic
c = anthropic.Anthropic()
M = "claude-haiku-5-5"
TOOLS = [{"name": "read_email", "description": "Read one email by id",
          "input_schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}}]
cost = 0.0
def call(messages, tools=TOOLS, label=""):
    global cost
    print(f"\n===== {label}")
    try:
        r = c.messages.create(model=M, max_tokens=400, output_config={"effort": "low"}, tools=tools, messages=messages)
    except anthropic.BadRequestError as e:
        print("REJECTED 400:", e.body["error"]["message"]); return None
    cost += r.usage.input_tokens / 1e6 * 0.10 + r.usage.output_tokens / 1e6 * 0.50
    print("stop_reason:", r.stop_reason)
    for b in r.content:
        if b.type == "text": print("text:", b.text)
        elif b.type == "tool_use": print("tool_use:", json.dumps({"id": b.id, "name": b.name, "input": b.input}))
        else: print(b.type, "(block)")
    return r

ask = [{"role": "user", "content": "What does email 1 say? Use the tool."}]
r1 = call(ask, label="A. model asks for a tool")
tu = next(b for b in r1.content if b.type == "tool_use")
hist = ask + [{"role": "assistant", "content": r1.content}]

call(hist + [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": tu.id, "content": "From: Priya. Lunch moved to 2pm."}]}],
     label="B. we send the result")
call(hist + [{"role": "user", "content": "go on"}], label="C. no result, just text")
call(hist + [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_wrong123", "content": "x"}]}],
     label="D. result with the wrong id")
call(hist + [{"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "tool_result", "tool_use_id": tu.id, "content": "x"}]}],
     label="E. text BEFORE the result")

# F. async: answer immediately with "started", the real result arrives later as a user message
F = [{"role": "user", "content": "What does email 1 say? Use the tool."},
     {"role": "assistant", "content": r1.content},
     {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tu.id, "content": "Started in background as job 42. Result will arrive later."}]}]
r = call(F, label="F1. async: immediate 'started' reply")
F += [{"role": "assistant", "content": r.content},
      {"role": "user", "content": "<task-notification>job 42 finished: From: Priya. Lunch moved to 2pm.</task-notification>"}]
call(F, label="F2. async: result arrives later as a USER message")

# G. invented call: the model never asked; we write the assistant turn ourselves
G = [{"role": "user", "content": "Anything new?"},
     {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_invented_1", "name": "read_email", "input": {"id": 1}}]},
     {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_invented_1", "content": "From: Priya. Lunch moved to 2pm."}]}]
call(G, label="G. invented tool call + reply (model never made it)")
print(f"\nTOTAL COST ${cost:.5f}")
