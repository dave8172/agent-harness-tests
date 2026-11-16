# The tests behind "How AI agents call tools" (part 1)

These scripts produced the numbers in [How AI agents call tools: harness, roles, rules](https://quirkyagents.com/wizard/blog/how-ai-agents-call-tools/), part 1 of [Testing AI agent security](https://quirkyagents.com/wizard/blog/series/agent-security-tested/). They run on 13 November 2026's APIs; results will drift.

- `demo.py` (Claude) and `openai_demo.py` (OpenAI): the tool-call rules, the real 400 errors, background tools, invented tool calls.
- `roles_test.py`, `dev_test.py`, `unlabelled_test.py`, `nohint_test.py`: system vs user, and the same email in each role (the BANANA canary).
- `mid_test.py`: mid-conversation system messages (add, change, remove, fake).
- `templates/`: render one conversation through Hugging Face chat templates (`render.py <tokenizer_config.json|chat_template.jinja>`); `tok.py` is the Qwen3 special-token test. Template revisions are listed in the post's "How I tested".
- `results/*.jsonl`: every reply from the full runs. The post's scores were checked by hand where the script was wrong (mixed-language replies, flags without the word).

Run from this folder, with `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set: `python roles_test.py`. Each run overwrites its file in `results/`.
