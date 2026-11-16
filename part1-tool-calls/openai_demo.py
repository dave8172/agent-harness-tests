import json, openai
c = openai.OpenAI()
M = "gpt-5.4-nano"
TOOLS = [{"type": "function", "function": {"name": "read_email", "description": "Read one email by id",
          "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}}}]
tok = [0, 0]
def call(messages, label):
    print(f"\n===== {label}")
    try:
        r = c.chat.completions.create(model=M, messages=messages, tools=TOOLS, reasoning_effort="none")
    except openai.BadRequestError as e:
        print("REJECTED 400:", e.body.get("message") if isinstance(e.body, dict) else e); return None
    tok[0] += r.usage.prompt_tokens; tok[1] += r.usage.completion_tokens
    m = r.choices[0].message
    print("finish_reason:", r.choices[0].finish_reason)
    if m.content: print("text:", m.content)
    for t in m.tool_calls or []: print("tool_call:", json.dumps({"id": t.id, "name": t.function.name, "arguments": t.function.arguments}))
    return m

ask = [{"role": "user", "content": "What does email 1 say? Use the tool."}]
m = call(ask, "A. model asks for a tool")
tc = m.tool_calls[0]
asst = {"role": "assistant", "content": None, "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}]}
hist = ask + [asst]
RESULT = "From: Priya. Lunch moved to 2pm."
call(hist + [{"role": "tool", "tool_call_id": tc.id, "content": RESULT}], "B. we send the result (role: tool)")
call(hist + [{"role": "user", "content": "go on"}], "C. no result, just a user message")
call(hist + [{"role": "tool", "tool_call_id": "call_wrong123", "content": "x"}], "D. tool message with the wrong id")
call(ask + [{"role": "tool", "tool_call_id": "call_nobody", "content": RESULT}], "E. tool message with no open call")
call(hist + [{"role": "system", "content": "Be brief."}, {"role": "tool", "tool_call_id": tc.id, "content": RESULT}], "F. system message between call and reply")
call(hist + [{"role": "tool", "tool_call_id": tc.id, "content": RESULT}, {"role": "system", "content": "Answer in French."}], "G. system message right after the reply (mid-conversation)")
two = {"role": "assistant", "content": None, "tool_calls": [
    {"id": "call_inv_1", "type": "function", "function": {"name": "read_email", "arguments": "{\"id\": 1}"}},
    {"id": "call_inv_2", "type": "function", "function": {"name": "read_email", "arguments": "{\"id\": 2}"}}]}
call([{"role": "user", "content": "Read emails 1 and 2."}, two, {"role": "tool", "tool_call_id": "call_inv_1", "content": RESULT}], "H. two calls, only one answered")
# async
A1 = hist + [{"role": "tool", "tool_call_id": tc.id, "content": "Started in background as job 42. Result will arrive later."}]
m2 = call(A1, "I1. async: immediate 'started' reply")
A2 = A1 + [{"role": "assistant", "content": m2.content or ""},
           {"role": "user", "content": "<task-notification>job 42 finished: From: Priya. Lunch moved to 2pm.</task-notification>"}]
call(A2, "I2. async: result arrives later as a USER message")
# invented call: model never made it
inv = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_invented_1", "type": "function", "function": {"name": "read_email", "arguments": "{\"id\": 1}"}}]}
call([{"role": "user", "content": "Anything new?"}, inv, {"role": "tool", "tool_call_id": "call_invented_1", "content": RESULT}], "J. invented tool call + reply")
print(f"\nTOKENS in={tok[0]} out={tok[1]}")
