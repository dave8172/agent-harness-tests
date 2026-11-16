// pi harness (pi-agent-core + pi-ai): the probe conversation through pi's own building blocks.
//
//   operator          agent.state.systemPrompt
//   tool result       a normal AgentTool return
//   mid-conversation  pi's model messages are only user / assistant / toolResult, so there is
//                     no system voice mid-conversation. Two ways a pi user would do it:
//                       --mid sysprompt  append to agent.state.systemPrompt (it moves to the top)
//                       --mid steer      agent.steer(): a user message, the documented mid-run inject
//   background result agent.followUp(): a user message in <task-notification> tags, delivered when
//                     the agent would otherwise stop
//
//   node harnesses/pi_driver.mjs --provider anthropic --base-url http://127.0.0.1:8765/pi-anthropic
//   providers: anthropic | openai-responses (pi's default for OpenAI) | openai-chat | ollama
//
// Phase 0 points --base-url at wire/fake_server.py ($0).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
import { Agent } from "@mariozechner/pi-agent-core";
import { getModel, Type } from "@mariozechner/pi-ai";

export const PROBE = JSON.parse(readFileSync(join(here, "..", "wire", "probe.json"), "utf8"));

export function makeModel(provider, baseUrl, modelId) {
  if (provider === "anthropic") {
    // pi 0.73 lists no Haiku 5.5 yet: same entry as Haiku 4.5, new id, our prices.
    const m = { ...getModel("anthropic", "claude-haiku-4-5"), id: modelId || "claude-haiku-5-5",
                name: "Claude Haiku 5.5", cost: { input: 0.1, output: 0.5, cacheRead: 0.01, cacheWrite: 0.125 } };
    if (baseUrl) m.baseUrl = baseUrl;
    return m;
  }
  if (provider === "ollama") {
    // How pi's docs add a local model (~/.pi/agent/models.json): an OpenAI-compatible entry.
    return { id: modelId || "qwen3:8b", name: "Qwen3 8B (Ollama)", api: "openai-completions", provider: "ollama",
             baseUrl: baseUrl || "http://localhost:11434/v1", reasoning: false, input: ["text"],
             cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 32768, maxTokens: 4096 };
  }
  const m = { ...getModel("openai", modelId || "gpt-5.4-nano") };
  if (provider === "openai-chat") m.api = "openai-completions";
  if (baseUrl) m.baseUrl = baseUrl;
  return m;
}

const text = (t) => ({ content: [{ type: "text", text: t }], details: {} });

function args() {
  const a = { mid: "sysprompt" };
  const v = process.argv.slice(2);
  for (let i = 0; i < v.length; i += 2) a[v[i].replace(/^--/, "").replace(/-(.)/g, (_, c) => c.toUpperCase())] = v[i + 1];
  return a;
}

async function main() {
  const a = args();
  process.env.ANTHROPIC_API_KEY ||= "fake";
  process.env.OPENAI_API_KEY ||= "fake";
  const apiKey = a.provider === "ollama" ? "ollama" : undefined; // pi wants a key even for a local server
  let agent;
  const tools = [
    { name: "read_email", label: "Read email", description: PROBE.tools.read_email,
      parameters: Type.Object({ id: Type.Integer() }),
      execute: async () => {
        if (a.mid === "steer") agent.steer({ role: "user", content: PROBE.midsys, timestamp: Date.now() });
        return text(PROBE.email);
      } },
    { name: "fetch_report", label: "Fetch report", description: PROBE.tools.fetch_report,
      parameters: Type.Object({}),
      execute: async () => {
        agent.followUp({ role: "user", content: `<task-notification>${PROBE.bg_result}</task-notification>`,
                         timestamp: Date.now() });
        return text(PROBE.bg_ack);
      } },
    { name: "check_job", label: "Check job", description: PROBE.tools.check_job,
      parameters: Type.Object({ id: Type.Integer() }),
      execute: async () => text(PROBE.bg_result) },
  ];
  agent = new Agent({ initialState: { systemPrompt: PROBE.system, model: makeModel(a.provider, a.baseUrl),
                                      thinkingLevel: "off", tools },
                      ...(apiKey ? { getApiKey: async () => apiKey } : {}) });
  agent.subscribe((e) => {
    // pi applies a new system prompt from the next request on: the closest it gets to "from now on".
    if (a.mid === "sysprompt" && e.type === "turn_end" && e.toolResults?.length)
      agent.state.systemPrompt = PROBE.system + "\n\n" + PROBE.midsys;
  });
  await agent.prompt(PROBE.user1);
  await agent.prompt(PROBE.user2);
  if (agent.state.errorMessage) { console.error("pi error:", agent.state.errorMessage); process.exit(1); }
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
