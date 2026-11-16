"""Pydantic AI harness: the probe conversation through Pydantic AI's own building blocks.

    operator          `instructions=` on the Agent
    tool result       a normal @agent.tool return
    mid-conversation  `ctx.enqueue(SystemPromptPart(...))` from inside the tool (the documented
                      way to add an instruction during a run)
    background result `ctx.enqueue(..., priority="when_idle")`: delivered when the run would
                      otherwise end, the way a finished background job reports back. Two forms:
                        --bg user        a <task-notification> string (becomes a UserPromptPart)
                        --bg toolreturn  a ToolReturnPart for check_job with no call before it

    python harnesses/pydantic_driver.py --provider anthropic --base-url http://127.0.0.1:8765/pydantic-anthropic
    providers: anthropic | openai-chat | openai-responses | ollama (OpenAI-compatible, qwen3:8b)

Phase 0 points --base-url at wire/fake_server.py ($0).
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import SystemPromptPart, ToolReturnPart

PROBE = json.loads((Path(__file__).parent.parent / "wire" / "probe.json").read_text())


def make_model(provider: str, base_url: str | None, model_name: str | None = None):
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        return AnthropicModel(model_name or "claude-haiku-5-5", provider=AnthropicProvider(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "fake"), base_url=base_url))
    if provider == "ollama":
        from pydantic_ai.models.ollama import OllamaModel
        from pydantic_ai.providers.ollama import OllamaProvider
        return OllamaModel(model_name or "qwen3:8b", provider=OllamaProvider(base_url=base_url))
    from pydantic_ai.providers.openai import OpenAIProvider
    prov = OpenAIProvider(api_key=os.environ.get("OPENAI_API_KEY", "fake"), base_url=base_url)
    if provider == "openai-chat":
        from pydantic_ai.models.openai import OpenAIChatModel
        return OpenAIChatModel(model_name or "gpt-5.4-nano", provider=prov)
    from pydantic_ai.models.openai import OpenAIResponsesModel
    return OpenAIResponsesModel(model_name or "gpt-5.4-nano", provider=prov)


def build_agent(model, bg: str) -> Agent:
    agent = Agent(model, instructions=PROBE["system"])

    @agent.tool(description=PROBE["tools"]["read_email"])
    def read_email(ctx: RunContext, id: int) -> str:
        ctx.enqueue(SystemPromptPart(PROBE["midsys"]))
        return PROBE["email"]

    @agent.tool(description=PROBE["tools"]["fetch_report"])
    def fetch_report(ctx: RunContext) -> str:
        if bg == "user":
            ctx.enqueue(f"<task-notification>{PROBE['bg_result']}</task-notification>", priority="when_idle")
        else:
            ctx.enqueue(ToolReturnPart(tool_name="check_job", content=PROBE["bg_result"],
                                       tool_call_id="bg_42"), priority="when_idle")
        return PROBE["bg_ack"]

    @agent.tool(description=PROBE["tools"]["check_job"])
    def check_job(ctx: RunContext, id: int) -> str:
        return PROBE["bg_result"]

    return agent


async def main(provider, base_url, bg):
    agent = build_agent(make_model(provider, base_url), bg)
    r1 = await agent.run(PROBE["user1"])
    await agent.run(PROBE["user2"], message_history=r1.all_messages())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openai-chat", "openai-responses", "ollama"], required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--bg", choices=["user", "toolreturn"], default="user")
    a = ap.parse_args()
    asyncio.run(main(a.provider, a.base_url, a.bg))
