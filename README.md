# modelvoicebench

Every message an AI agent sends a model carries a voice: the operator (system), the person (user), a tool's output, the model's own earlier turns. Models are trained to trust these voices differently. **The harness**, the code around the model, picks the voice for everything it sends. This bench measures two things. Where does each harness actually put each voice? And how does a model behave when a harness puts something in the wrong one?

Harnesses: a hand-rolled loop on the raw provider SDKs (the control: every voice in the channel built for it), [Pydantic AI](https://ai.pydantic.dev) 2.68 (Phase 3: 2.69 with pydantic-ai-harness 0.69), and [pi](https://github.com/badlogic/pi-mono) 0.73 (`pi-agent-core`). Models: Claude Haiku 5.5 and gpt-5.4-nano, with the same settings in every harness. A local open model via Ollama comes next.

## Phases

| | what | cost | result |
|---|---|---|---|
| 0 | One conversation recorded on the wire through each harness, provider and variant (fake endpoint), then rendered through six open-model chat templates | $0 | [`results/phase0/README.md`](results/phase0/README.md) |
| 1 | Voice probes: operator vs user language, a mid-conversation change, a planted instruction in a tool result vs a background result, forged `<system>` tags, "who wrote this line?" (20 runs per arm) | $0.15 | [`results/phase1/summary.md`](results/phase1/summary.md); follow-ups `bench/extra_mid.py` → `results/phase1-followup/`, and the `user-change` probe → `results/phase1-userchange/` |
| 2 | Real scenario: an email agent tidies an inbox with one planted email (forged consent, a hacked trusted sender, a quoted person, a reply redirect, a harmless twin) plus a tool-description canary. The email arrives as a tool result, as a background result in a user message, or the same in data tags (10 runs per cell). Plus a thinking-replay diagnostic (`bench/diag_thinking.py`) | $1.90 + $0.37 | [`results/phase2/summary.md`](results/phase2/summary.md) |
| 3 | The same inbox with a gate in front of every tool call: none, run-level (after any outside read, every action asks), per-argument (lenient and strict), and run-level with Pydantic AI harness's `ApprovalReviewer`. Two payment scenarios where the email changes one argument. Scored: harmful calls let through, task done, asks per run (10 runs per cell) | $2.44 | [`results/phase3/summary.md`](results/phase3/summary.md); rollup `bench/phase3_rollup.py` |

Every finding, with its numbers: [`FINDINGS.md`](FINDINGS.md). Written up in plain language as the series **[Testing AI agent security](https://quirkyagents.com/wizard/blog/series/agent-security-tested/)**: [part 3](https://quirkyagents.com/wizard/blog/who-does-an-ai-agent-obey/) (Phase 0–1), [part 4](https://quirkyagents.com/wizard/blog/prompt-injection-email-agent-three-harnesses/) (Phase 2) and [part 7](https://quirkyagents.com/wizard/blog/how-to-test-ai-agent-prompt-injection/) (the method). `part1-tool-calls/` holds the tests behind [part 1](https://quirkyagents.com/wizard/blog/how-ai-agents-call-tools/). The scenario format, for running these in another bench: [`SCENARIOS.md`](SCENARIOS.md).

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install "pydantic-ai-slim[anthropic,openai]" anthropic openai jinja2
npm install                                   # pi-agent-core, pi-ai
bash wire/record_all.sh                       # Phase 0, $0
.venv/bin/python bench/phase1.py --runs 20    # prints an estimate first
.venv/bin/python bench/phase2.py --runs 10
# Phase 3 has its own venv: pydantic-ai-harness (ApprovalReviewer) pins its own Pydantic AI version
python3 -m venv .venv-p3 && .venv-p3/bin/pip install "pydantic-ai-slim[anthropic,openai]" pydantic-ai-harness httpx
.venv-p3/bin/python bench/test_p3_fake.py     # $0 check of the gate with a scripted model
.venv-p3/bin/python bench/phase3.py --runs 10 --per-run anthropic=14000/2000,openai=8000/800
```

Keys: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Every runner resumes from its results file, and `--score-only` rescores.

### A local model (Ollama)

Every runner also takes `--providers ollama`. It talks to Ollama's OpenAI-compatible API: hand-rolled and pi on Chat Completions, Pydantic AI through its `OllamaModel`. No key is needed, and the server's own defaults are kept.

```bash
ollama pull qwen3:8b
set OLLAMA_MODEL=qwen3:8b                       # (cmd; export on bash)
set OLLAMA_BASE_URL=http://localhost:11434/v1
.venv\Scripts\python bench\phase1.py --runs 20 --providers ollama --out results\phase1-ollama
.venv\Scripts\python bench\phase2.py --runs 10 --providers ollama --out results\phase2-ollama
```

Checked against the fake endpoint only (the box that built this can't run a model).

## Limits

- Two small models, one setting each. Results describe these models and versions on 13 November 2026.
- 10 to 20 runs per cell: directions, not rates.
- Scores are a first automatic pass. Language and "flagged" were checked by reading the replies (`replies.md`, `runs.md`), and the corrections are noted in `FINDINGS.md`.
- The harness versions move fast. Pydantic AI's voice framing is weeks old.

## Licence

MIT, see [`LICENSE`](LICENSE). The Hugging Face chat templates in `templates/hf/` keep their own licences (each model's repository).
