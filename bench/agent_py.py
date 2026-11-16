"""Phase 2 runner for the Python harnesses: the agent works the world until it stops.

A job names the scenario (the planted email), the delivery arm, the harness and the
provider. Tools run on world/server.py, so every harness acts on the same world code.
In the background arms, read_email answers at once and the email arrives through the
harness's own way of reporting a finished background job:
    hand-rolled   a user message (text after the tool results in the same turn)
    Pydantic AI   ctx.enqueue(text) from the tool, delivered right after its tool result

    python bench/agent_py.py jobs.jsonl results.jsonl --world http://127.0.0.1:8777 [--concurrency 4]
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "world"))
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from butler import BG_ACK, bg_wrap  # noqa: E402
from run_py import CLAUDE, GPT, OLLAMA_MODEL, OLLAMA_URL, key  # noqa: E402

MAX_REQUESTS = 20


class World:
    def __init__(self, url, client):
        self.url, self.c = url, client

    async def new(self, scenario):
        r = await self.c.post(self.url + "/new", json={"scenario": scenario})
        d = r.json()
        self.run = d["run"]
        return d

    async def call(self, name, args):
        r = await self.c.post(self.url + "/call", json={"run": self.run, "name": name, "args": args})
        d = r.json()
        return d["text"], d["is_error"]

    async def score(self, final_text):
        r = await self.c.post(self.url + "/score", json={"run": self.run, "final_text": final_text})
        return r.json()


def dump(job, n, body):
    """MVB_DUMP=dir: write each request body (hand-rolled only; Pydantic AI: use its own instrumentation)."""
    d = os.environ.get("MVB_DUMP")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        (Path(d) / f"{job['id'].replace('|', '_')}_{n:02d}.json").write_text(json.dumps(body, indent=1, default=str))


async def tool_step(world, delivery, name, args):
    """Run a tool. Returns (text for the tool result, is_error, background text or None)."""
    text, err = await world.call(name, args)
    if name == "read_email" and delivery != "tool" and not err:
        return BG_ACK.format(id=args.get("id")), False, bg_wrap(text, delivery)
    return text, err, None


async def handrolled_anthropic(job, world, info):
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=key("anthropic"), max_retries=4)
    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
             for t in info["tools"]]
    msgs = [{"role": "user", "content": info["task"]}]
    usage, n, final = {"input": 0, "output": 0}, 0, ""
    while n < MAX_REQUESTS:
        dump(job, n + 1, {"system": info["system"], "messages": msgs})
        r = await client.messages.create(model=CLAUDE, max_tokens=2000, system=info["system"], tools=tools,
                                         messages=msgs, output_config={"effort": "low"})
        n += 1
        usage["input"] += r.usage.input_tokens
        usage["output"] += r.usage.output_tokens
        blocks = [b.model_dump(exclude_none=True) for b in r.content]
        if job.get("variant") == "strip-thinking":  # diagnostic: drop the model's thinking from history, as pi does
            blocks = [b for b in blocks if b.get("type") not in ("thinking", "redacted_thinking")]
        msgs.append({"role": "assistant", "content": blocks})
        final = "".join(b.text for b in r.content if b.type == "text") or final
        if r.stop_reason != "tool_use":
            break
        results, later = [], []
        for b in r.content:
            if b.type == "tool_use":
                text, err, bg = await tool_step(world, job["delivery"], b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": err})
                if bg:
                    later.append({"type": "text", "text": bg})
        msgs.append({"role": "user", "content": results + later})
    return final, usage, n


async def handrolled_openai(job, world, info):
    import openai
    client = openai.AsyncOpenAI(api_key=key("openai"), max_retries=4)
    tools = [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["parameters"]}
             for t in info["tools"]]
    items = [{"role": "user", "content": info["task"]}]
    usage, n, final = {"input": 0, "output": 0}, 0, ""
    while n < MAX_REQUESTS:
        r = await client.responses.create(model=GPT, instructions=info["system"], input=items, tools=tools,
                                          max_output_tokens=2000, reasoning={"effort": "none"}, store=False)
        n += 1
        usage["input"] += r.usage.input_tokens
        usage["output"] += r.usage.output_tokens
        final = r.output_text or final
        calls = [o for o in r.output if o.type == "function_call"]
        for o in r.output:
            if o.type == "message":
                items.append({"role": "assistant", "content": o.content[0].text if o.content else ""})
        if not calls:
            break
        later = []
        for c in calls:
            try:
                text, err, bg = await tool_step(world, job["delivery"], c.name, json.loads(c.arguments or "{}"))
            except json.JSONDecodeError:
                # Bad JSON from the model: say so in the tool result, as Pydantic AI and pi do.
                text, err, bg = "Error: the arguments were not valid JSON. Call the tool again.", True, None
            items.append({"type": "function_call", "call_id": c.call_id, "name": c.name, "arguments": c.arguments})
            items.append({"type": "function_call_output", "call_id": c.call_id, "output": text})
            if bg:
                later.append(bg)
        for t in later:
            items.append({"role": "user", "content": t})
    return final, usage, n


async def handrolled_ollama(job, world, info):
    """Chat Completions loop against a local OpenAI-compatible server (Ollama)."""
    import openai
    client = openai.AsyncOpenAI(api_key="ollama", base_url=OLLAMA_URL, max_retries=2, timeout=600)
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                               "parameters": t["parameters"]}} for t in info["tools"]]
    msgs = [{"role": "system", "content": info["system"]}, {"role": "user", "content": info["task"]}]
    usage, n, final = {"input": 0, "output": 0}, 0, ""
    while n < MAX_REQUESTS:
        r = await client.chat.completions.create(model=OLLAMA_MODEL, messages=msgs, tools=tools, max_tokens=2000)
        n += 1
        if r.usage:
            usage["input"] += r.usage.prompt_tokens
            usage["output"] += r.usage.completion_tokens
        m = r.choices[0].message
        msgs.append(m.model_dump(exclude_none=True))
        final = m.content or final
        if not m.tool_calls:
            break
        later = []
        for tc in m.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            text, err, bg = await tool_step(world, job["delivery"], tc.function.name, args)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": text})
            if bg:
                later.append(bg)
        for t in later:
            msgs.append({"role": "user", "content": t})
    return final, usage, n


async def pydantic_agent(job, world, info):
    from pydantic_ai import Agent, RunContext, UsageLimits
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.tools import Tool
    if job["provider"] == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
        from pydantic_ai.providers.anthropic import AnthropicProvider
        model = AnthropicModel(CLAUDE, provider=AnthropicProvider(api_key=key("anthropic")))
        settings = AnthropicModelSettings(max_tokens=2000, anthropic_effort="low")
    elif job["provider"] == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider
        from pydantic_ai.settings import ModelSettings
        model = OllamaModel(OLLAMA_MODEL, provider=OllamaProvider(base_url=OLLAMA_URL))
        settings = ModelSettings(max_tokens=2000)
    else:
        from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
        from pydantic_ai.providers.openai import OpenAIProvider
        model = OpenAIResponsesModel(GPT, provider=OpenAIProvider(api_key=key("openai")))
        settings = OpenAIResponsesModelSettings(max_tokens=2000, openai_reasoning_effort="none")
    from pydantic_ai import ModelRetry

    def make(t):
        async def fn(ctx: RunContext, **args) -> str:
            text, err, bg = await tool_step(world, job["delivery"], t["name"], args)
            if err:
                raise ModelRetry(text)
            if bg:
                ctx.enqueue(bg)
            return text
        return Tool.from_schema(fn, name=t["name"], description=t["description"], json_schema=t["parameters"],
                                takes_ctx=True)
    agent = Agent(model, instructions=info["system"], model_settings=settings, retries=3,
                  tools=[make(t) for t in info["tools"]])
    final, n = "", 0
    try:
        async with agent.iter(info["task"], usage_limits=UsageLimits(request_limit=MAX_REQUESTS)) as run:
            async for _node in run:
                pass
        r = run.result
        final = r.output
        u = r.usage
    except UsageLimitExceeded:
        u = run.usage
    n = u.requests
    return final, {"input": u.input_tokens, "output": u.output_tokens}, n


RUNNERS = {("handrolled", "anthropic"): handrolled_anthropic, ("handrolled", "openai"): handrolled_openai,
           ("pydantic", "anthropic"): pydantic_agent, ("pydantic", "openai"): pydantic_agent,
           ("handrolled", "ollama"): handrolled_ollama, ("pydantic", "ollama"): pydantic_agent}


async def run_all(jobs, out_path, world_url, conc):
    done = set()
    if Path(out_path).exists():
        done = {json.loads(l)["id"] for l in open(out_path) if json.loads(l)["error"] is None}
    out = open(out_path, "a")
    sem = asyncio.Semaphore(conc)
    async with httpx.AsyncClient(timeout=60) as hc:
        async def one(job):
            if job["id"] in done:
                return
            async with sem:
                t0 = time.time()
                world = World(world_url, hc)
                info = await world.new(job["scenario"])
                try:
                    final, usage, n = await RUNNERS[(job["harness"], job["provider"])](job, world, info)
                    err = None
                except Exception as e:
                    final, usage, n, err = "", {"input": 0, "output": 0}, 0, f"{type(e).__name__}: {str(e)[:400]}"
                sc = await world.score(final or "")
                out.write(json.dumps({"id": job["id"], "score": sc["score"], "final": final, "usage": usage,
                                      "requests": n, "error": err, "outbox": sc["world"]["outbox"],
                                      "calls": sc["world"]["calls"], "seconds": round(time.time() - t0, 1)},
                                     ensure_ascii=False) + "\n")
                out.flush()
        await asyncio.gather(*(one(j) for j in jobs))


if __name__ == "__main__":
    jobs_path, out_path = sys.argv[1], sys.argv[2]
    world = sys.argv[sys.argv.index("--world") + 1] if "--world" in sys.argv else "http://127.0.0.1:8777"
    conc = int(sys.argv[sys.argv.index("--concurrency") + 1]) if "--concurrency" in sys.argv else 4
    jobs = [j for j in map(json.loads, open(jobs_path)) if j["harness"] in ("handrolled", "pydantic")]
    asyncio.run(run_all(jobs, out_path, world, conc))
