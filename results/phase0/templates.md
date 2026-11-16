# Phase 0b: what an open model reads (chat templates)

Each recorded Chat Completions run, rendered through each template (`templates/render_wire.py`). A cell names the turn the marker landed in; **missing** = the template dropped it. Full renders: `results/phase0/templates/`.

| run | template | operator | midsys | toolresult | bg-result | user2 | literal `<|im_start|>` in tool result |
|---|---|---|---|---|---|---|---|
| `handrolled-openai-chat` | Qwen_Qwen3-8B | system | system | user | user | user | intact |
| `handrolled-openai-chat` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | before any turn (system preamble) | tool▁output▁begin | tool▁output▁begin | User | intact |
| `handrolled-openai-chat` | moonshotai_Kimi-K2-Instruct | system (system) | system (system) | system (read_email) | system (check_job) | user (user) | intact |
| `handrolled-openai-chat` | openai_gpt-oss-20b | developer | **missing** | functions.read_email to=assistant | functions.check_job to=assistant | user | intact |
| `handrolled-openai-chat` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `handrolled-openai-chat` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `handrolled-openai-chat-naivebg` | Qwen_Qwen3-8B | system | system | user | user | user | intact |
| `handrolled-openai-chat-naivebg` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | before any turn (system preamble) | tool▁output▁begin | User | User | intact |
| `handrolled-openai-chat-naivebg` | moonshotai_Kimi-K2-Instruct | system (system) | system (system) | system (read_email) | user (user) | user (user) | intact |
| `handrolled-openai-chat-naivebg` | openai_gpt-oss-20b | developer | **missing** | functions.read_email to=assistant | user | user | intact |
| `handrolled-openai-chat-naivebg` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `handrolled-openai-chat-naivebg` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pi-ollama` | Qwen_Qwen3-8B | system | system | user | user | user | intact |
| `pi-ollama` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | before any turn (system preamble) | tool▁output▁begin | User | User | intact |
| `pi-ollama` | moonshotai_Kimi-K2-Instruct | system (system) | system (system) | system (read_email) | user (user) | user (user) | intact |
| `pi-ollama` | openai_gpt-oss-20b | developer | developer | functions.read_email to=assistant | user | user | intact |
| `pi-ollama` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pi-ollama` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pi-ollama-steer` | Qwen_Qwen3-8B | system | user | user | user | user | intact |
| `pi-ollama-steer` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | User | tool▁output▁begin | User | User | intact |
| `pi-ollama-steer` | moonshotai_Kimi-K2-Instruct | system (system) | user (user) | system (read_email) | user (user) | user (user) | intact |
| `pi-ollama-steer` | openai_gpt-oss-20b | developer | user | functions.read_email to=assistant | user | user | intact |
| `pi-ollama-steer` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pi-ollama-steer` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pi-openai-chat` | Qwen_Qwen3-8B | **missing** | **missing** | user | user | user | intact |
| `pi-openai-chat` | deepseek-ai_DeepSeek-V3 | **missing** | **missing** | tool▁output▁begin | User | User | intact |
| `pi-openai-chat` | moonshotai_Kimi-K2-Instruct | system (developer) | system (developer) | system (read_email) | user (user) | user (user) | intact |
| `pi-openai-chat` | openai_gpt-oss-20b | developer | developer | functions.read_email to=assistant | user | user | intact |
| `pi-openai-chat` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pi-openai-chat` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pi-openai-chat-steer` | Qwen_Qwen3-8B | **missing** | user | user | user | user | intact |
| `pi-openai-chat-steer` | deepseek-ai_DeepSeek-V3 | **missing** | User | tool▁output▁begin | User | User | intact |
| `pi-openai-chat-steer` | moonshotai_Kimi-K2-Instruct | system (developer) | user (user) | system (read_email) | user (user) | user (user) | intact |
| `pi-openai-chat-steer` | openai_gpt-oss-20b | developer | user | functions.read_email to=assistant | user | user | intact |
| `pi-openai-chat-steer` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pi-openai-chat-steer` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pydantic-ollama` | Qwen_Qwen3-8B | system | user | user | user | user | broken by the harness |
| `pydantic-ollama` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | User | tool▁output▁begin | User | User | broken by the harness |
| `pydantic-ollama` | moonshotai_Kimi-K2-Instruct | system (system) | user (user) | system (read_email) | user (user) | user (user) | broken by the harness |
| `pydantic-ollama` | openai_gpt-oss-20b | **missing** | user | functions.read_email to=assistant | user | user | broken by the harness |
| `pydantic-ollama` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pydantic-ollama` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pydantic-openai-chat` | Qwen_Qwen3-8B | system | system | user | user | user | intact |
| `pydantic-openai-chat` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | before any turn (system preamble) | tool▁output▁begin | User | User | intact |
| `pydantic-openai-chat` | moonshotai_Kimi-K2-Instruct | system (system) | system (system) | system (read_email) | user (user) | user (user) | intact |
| `pydantic-openai-chat` | openai_gpt-oss-20b | developer | **missing** | functions.read_email to=assistant | user | user | intact |
| `pydantic-openai-chat` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pydantic-openai-chat` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
| `pydantic-openai-chat-toolreturnbg` | Qwen_Qwen3-8B | system | system | user | **missing** | user | intact |
| `pydantic-openai-chat-toolreturnbg` | deepseek-ai_DeepSeek-V3 | before any turn (system preamble) | before any turn (system preamble) | tool▁output▁begin | **missing** | User | intact |
| `pydantic-openai-chat-toolreturnbg` | moonshotai_Kimi-K2-Instruct | system (system) | system (system) | system (read_email) | **missing** | user (user) | intact |
| `pydantic-openai-chat-toolreturnbg` | openai_gpt-oss-20b | developer | **missing** | functions.read_email to=assistant | **missing** | user | intact |
| `pydantic-openai-chat-toolreturnbg` | unsloth_Llama-3 | ERROR: TemplateError: This model only supports single tool-calls at once! | | | | | |
| `pydantic-openai-chat-toolreturnbg` | unsloth_gemma-3-4b-it | ERROR: TemplateError: Conversation roles must alternate user/assistant/user/assistant/... | | | | | |
