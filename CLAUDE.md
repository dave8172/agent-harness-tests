# agent-harness-tests: working notes

**What:** independent tests of agent harnesses (renamed from modelvoicebench 2026-11-18; GitHub redirects the old URL). Covers voices, attacks, defences and what each harness sends on the wire. Does a harness put each voice (operator, user, tool, background result, mid-conversation instruction) where the model expects it, and how does the model behave when it doesn't? Harnesses: hand-rolled (the correct-voice control), Pydantic AI, pi (`pi-agent-core`). Models: Claude Haiku 5.5, gpt-5.4-nano. Next: a local open model via Ollama.

**State (2026-11-17):** Phase 3 (gates) run and written up as part 8 of the series (FINDINGS G1–G10; conclusion: the run-level gate as the default). Phases 0–2 built and run; written up as the series [Testing AI agent security](https://quirkyagents.com/wizard/blog/series/agent-security-tested/) (parts 3, 4, 7). `findings.json` lists every finding, one line each with a status (result / open / reported / fixed / retracted); the site's Research page (quirkyagents `/wizard/research/`) is built from it, so **a new or changed finding changes `findings.json` and `FINDINGS.md` together**, then the site syncs. `FINDINGS.md` has every finding's numbers (D = Pydantic AI, U = API and model facts, P = pi, F = Phase 2).

**Scope:** realistic scenarios (forwarded or quoted email, indirect trust) in a portable format (`SCENARIOS.md`). Findings about a framework's code are stated as plain facts, with the good results shown.

## Layout
- `wire/`: Phase 0. `fake_server.py` records request bodies (Anthropic Messages, OpenAI Chat and Responses, streaming or not; scripted replies, $0). `probe.json` is the one conversation with `[V:...]` markers. `record_all.sh` runs every harness × provider × variant. `where.py` builds the where-each-voice-lands table. `replay.py` sends one recorded body to the real API (fractions of a cent).
- `harnesses/`: the Phase 0 drivers (`handrolled.py`, `pydantic_driver.py`, `pi_driver.mjs`). `pi_driver.mjs` also exports `makeModel`. pi 0.73 has no Haiku 5.5 entry, so it's built from the 4.5 entry.
- `templates/`: Phase 0b. `render_wire.py` renders recorded Chat Completions bodies through six HF chat templates (`templates/hf/`, the article's revisions).
- `bench/`: Phase 1 (`probes.py`, `run_py.py`, `run_pi.mjs`, `scoring.py`, `phase1.py`), Phase 2 (`agent_py.py`, `agent_pi.mjs`, `phase2.py`) and Phase 3 (`gate.py` = the gate both harnesses share, `agent_p3.py`, `phase3.py`).
- `world/`: Phase 2 world (`butler.py` = butler repo's world + four attacks + a harmless twin + the tool-description canary; `server.py` serves it over HTTP so the Python and JS harnesses share one world).
- `scenarios/`: the portable JSON exports.
- `results/phase{0,1,2}/`: raw data plus generated `summary.md` and `replies.md`/`runs.md`. `*-smoke/` = first single runs. `phase1-followup/` (`bench/extra_mid.py`) and `phase2-thinking/` (`bench/diag_thinking.py`) are the two follow-ups.
- `part1-tool-calls/`: the scripts and raw results behind part 1 of the series (How AI agents call tools).

## Run
- Phase 0 ($0): `bash wire/record_all.sh`, then `.venv/bin/python templates/render_wire.py results/phase0/wire results/phase0/templates > results/phase0/templates.md`.
- Phase 1: `.venv/bin/python bench/phase1.py --runs 20` (prints an estimate, refuses above `--cap`). Resumable. `--score-only` rescoring.
- Phase 2: `.venv/bin/python bench/phase2.py --runs 10`. Starts the world server itself.
- Phase 3: `.venv-p3/bin/python bench/phase3.py --runs 10 --per-run anthropic=14000/2000,openai=8000/800` (the default per-run tokens are Phase 2's and over-estimate ~4×). Own venv: `pydantic-ai-slim[anthropic,openai]==2.69.0` + `pydantic-ai-harness==0.69.0` (ApprovalReviewer; the harness pins slim 2.69, so Phases 0–2 stay on `.venv` 2.68). World on port 8778.
- Keys: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` from the environment. Never printed or written to a file.
- Settings pinned across harnesses: Claude `effort: low`, thinking left at the model default, `max_tokens` 2000. gpt-5.4-nano on the **Responses API** (Pydantic AI's and pi's default) with `reasoning: none`. pi gets these through its `onPayload` hook.

## Gotchas
- Phase 3: the world's `/judge` (= `butler.harmful`) is the scripted person: it denies exactly the harmful calls. ApprovalReviewer's model calls count in the run's usage and request limit (25). Pay scenarios: `task` is Phase 2's (boss + filing); `paid_legit` is separate, because holding a conflicting payment is a defence, not a failure.
- Messages API (2026-11-13): role `system` mid-conversation must follow a user message (400 otherwise). The hand-rolled runner moves an operator message that follows an assistant turn to just after the next user message.
- Pydantic AI 2.68 `usage` is a property (calling it warns). `PYDANTIC_AI_NO_BANNER=1`.
- pi: mid-conversation operator messages don't exist (user / assistant / toolResult only). Two variants: `sysprompt` (append to the system prompt) and `steer` (user message). `steeringMode: "all"` in Phase 2, so background results arrive per turn as in the other harnesses.
- **Thinking replay (found mid-Phase 2):** Claude Haiku 5.5 returns thinking blocks with empty text (display omitted) and a signature. Hand-rolled sends them back. pi 0.73 skips any thinking block with empty text (`pi-ai` `providers/anthropic.js` `convertMessages`). Our `onPayload` removes pi's `thinking: disabled` to pin settings, so pi runs with thinking on and drops it on replay. `bench/diag_thinking.py` swaps this (hand-rolled `strip-thinking`, pi `keep-thinking`). `MVB_DUMP=dir` writes each request body (hand-rolled and pi agent runners).
- Node deps live at the repo root (`package.json`). The pi packages are ESM-only.
- The machine that ran Phases 0–2 had no GPU, so the Ollama route is tested only against the fake endpoint.
