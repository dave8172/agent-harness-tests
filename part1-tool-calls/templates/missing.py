import json, sys, jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment
def raise_exception(m): raise jinja2.TemplateError(m)
env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True); env.globals["raise_exception"]=raise_exception
env.filters["tojson"] = lambda x, **k: json.dumps(x, ensure_ascii=False)
t = env.from_string(json.load(open(sys.argv[1]))["chat_template"])
msgs=[{"role":"user","content":"What does email 1 say?"},
      {"role":"assistant","content":"","tool_calls":[{"type":"function","function":{"name":"read_email","arguments":{"id":1}}}]},
      {"role":"user","content":"go on"}]
print(t.render(messages=msgs, add_generation_prompt=True))
