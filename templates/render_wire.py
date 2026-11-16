"""Render recorded Chat Completions bodies through open models' chat templates.

This is the last translation step before an open model reads anything: an
OpenAI-compatible server (vLLM, SGLang, llama.cpp, LM Studio...) turns the
request's messages into one string with the model's chat template. So what a
harness sends over the wire is not what the model reads; this shows the second.

For each recorded run (Chat Completions format) and each template in
templates/hf/, it renders the last request and finds the turn every [V:...]
marker landed in. Ollama ships its own Go templates (not these Jinja files),
so for Ollama this is an approximation: check `ollama show --template <model>`.

    python templates/render_wire.py results/phase0/wire results/phase0/templates

Templates are the files at the revisions the article used (2026-11-13), from
templates/hf/: chat_template.jinja, or chat_template inside tokenizer_config.json.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import jinja2
from jinja2.sandbox import ImmutableSandboxedEnvironment

HERE = Path(__file__).parent
MARK = re.compile(r"\[V:([a-z0-9-]+)\]")
# Turn openers across the six templates, each with the label it carries.
TURN = re.compile(
    r"<\|im_start\|>(?P<qwen>\w+)"                        # Qwen3
    r"|<\|im_(?P<kimi>system|user|assistant)\|>(?P<kiminame>[\w.]*)<\|im_middle\|>"  # Kimi K2
    r"|<\|start_header_id\|>(?P<llama>\w+)<\|end_header_id\|>"  # Llama 3.1
    r"|<｜(?P<ds>User|Assistant)｜>|<｜(?P<dstool>tool▁output▁begin)｜>"  # DeepSeek V3
    r"|<\|start\|>(?P<oss>[^<]+?)<\|(?:message|channel)\|>"  # gpt-oss (harmony)
    r"|<start_of_turn>(?P<gemma>\w+)"                    # Gemma 3
)


def env():
    def raise_exception(m):
        raise jinja2.TemplateError(m)
    e = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                      extensions=["jinja2.ext.loopcontrols"])
    e.globals.update(raise_exception=raise_exception,
                     strftime_now=lambda f: datetime(2026, 11, 13).strftime(f))
    e.filters["tojson"] = (lambda x, indent=None, ensure_ascii=False, separators=None, sort_keys=False:
                           json.dumps(x, indent=indent, ensure_ascii=ensure_ascii,
                                      separators=separators, sort_keys=sort_keys))
    return e


def load_templates():
    out = {}
    for f in sorted((HERE / "hf").iterdir()):
        name = f.name.split(".")[0]
        if f.name.endswith(".chat_template.jinja"):
            out[name] = f.read_text()
        elif f.name.endswith(".tokenizer_config.json") and name not in out:
            t = json.loads(f.read_text()).get("chat_template")
            if isinstance(t, list):
                t = next(x["template"] for x in t if x["name"] == "default")
            if t and not (HERE / "hf" / f"{name}.chat_template.jinja").exists():
                out[name] = t
    return out


def to_template_messages(messages):
    """What an OpenAI-compatible server does before templating: arguments JSON -> dict."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("tool_calls"):
            calls = []
            for tc in m["tool_calls"]:
                fn = dict(tc["function"])
                if isinstance(fn.get("arguments"), str):
                    fn["arguments"] = json.loads(fn["arguments"] or "{}")
                calls.append(dict(tc, function=fn))
            m["tool_calls"] = calls
        if m.get("content") is None:
            m["content"] = ""
        if isinstance(m["content"], list):  # text parts -> one string, as vLLM does for string-format templates
            m["content"] = "".join(p.get("text", "") for p in m["content"] if p.get("type") == "text")
        out.append(m)
    # Templates that name the tool in its result (Kimi, gpt-oss) look for `name` on the tool message.
    ids = {tc["id"]: tc["function"]["name"] for m in out for tc in m.get("tool_calls") or []}
    for m in out:
        if m["role"] == "tool" and "name" not in m and m.get("tool_call_id") in ids:
            m["name"] = ids[m["tool_call_id"]]
    return out


def label_at(text, pos):
    last = "before any turn (system preamble)"
    for t in TURN.finditer(text, 0, pos):
        g = {k: v for k, v in t.groupdict().items() if v}
        if "kimi" in g:
            last = g["kimi"] + (f" ({g['kiminame']})" if g.get("kiminame") else "")
        else:
            last = next(iter(g.values()))
    return last


def main(wire_root, out_root):
    wire_root, out_root = Path(wire_root), Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    templates = load_templates()
    e = env()
    rows = []
    for run in sorted(p for p in wire_root.iterdir() if p.is_dir()):
        last = json.loads(sorted(run.glob("*.json"))[-1].read_text())
        if not last["path"].endswith("/chat/completions"):
            continue
        body = last["body"]
        msgs = to_template_messages(body["messages"])
        tools = body.get("tools")
        for tname, src in templates.items():
            try:
                text = e.from_string(src).render(messages=msgs, tools=tools, add_generation_prompt=True,
                                                 bos_token="<BOS>", eos_token="<EOS>",
                                                 date_string="13 Nov 2026")
            except Exception as ex:  # a template refusing the conversation is a result too
                rows.append((run.name, tname, f"ERROR: {type(ex).__name__}: {str(ex)[:120]}", {}))
                continue
            (out_root / f"{run.name}__{tname}.txt").write_text(text)
            where = {}
            for mm in MARK.finditer(text):
                where.setdefault(mm.group(1), []).append(label_at(text, mm.start()))
            special = ("broken by the harness" if "<\u200d|im_start|>" in text
                       else "intact" if "<|im_start|>" in text else "not in output")
            rows.append((run.name, tname, "ok", dict(where, _special=[special])))
    cols = ["operator", "midsys", "toolresult", "bg-result", "user2"]
    print("# Phase 0b: what an open model reads (chat templates)\n")
    print("Each recorded Chat Completions run, rendered through each template "
          "(`templates/render_wire.py`). A cell names the turn the marker landed in; "
          "**missing** = the template dropped it. Full renders: `results/phase0/templates/`.\n")
    print("| run | template | " + " | ".join(cols) + " | literal `<|im_start|>` in tool result |")
    print("|---|---|" + "---|" * (len(cols) + 1))
    for run, tname, status, where in rows:
        if status != "ok":
            print(f"| `{run}` | {tname} | {status} |" + " |" * len(cols))
            continue
        cells = [", ".join(sorted(set(where.get(c, [])))) or "**missing**" for c in cols]
        print(f"| `{run}` | {tname} | " + " | ".join(cells) + f" | {where['_special'][0]} |")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
