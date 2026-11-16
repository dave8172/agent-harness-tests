#!/usr/bin/env bash
# Phase 0: record every harness x provider x variant against the fake endpoint ($0),
# then write the "where each voice lands" table.
#   bash wire/record_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=results/phase0/wire
rm -rf "$OUT"; mkdir -p "$OUT"
PORT=8766
.venv/bin/python wire/fake_server.py --out "$OUT" --port $PORT &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null || true' EXIT
sleep 1
B=http://127.0.0.1:$PORT
PY=.venv/bin/python

$PY harnesses/handrolled.py --provider anthropic   --base-url $B/handrolled-anthropic
$PY harnesses/handrolled.py --provider anthropic   --base-url $B/handrolled-anthropic-naivebg --naive
$PY harnesses/handrolled.py --provider openai-chat --base-url $B/handrolled-openai-chat/v1
$PY harnesses/handrolled.py --provider openai-chat --base-url $B/handrolled-openai-chat-naivebg/v1 --naive

for p in anthropic openai-chat openai-responses; do
  sfx=""; [ "$p" != anthropic ] && sfx=/v1
  $PY harnesses/pydantic_driver.py --provider $p --base-url $B/pydantic-$p$sfx
  $PY harnesses/pydantic_driver.py --provider $p --base-url $B/pydantic-$p-toolreturnbg$sfx --bg toolreturn
  node harnesses/pi_driver.mjs --provider $p --base-url $B/pi-$p$sfx
  node harnesses/pi_driver.mjs --provider $p --base-url $B/pi-$p-steer$sfx --mid steer
done

# A self-hosted open model behind an OpenAI-compatible server (Ollama's API shape)
$PY harnesses/pydantic_driver.py --provider ollama --base-url $B/pydantic-ollama/v1
node harnesses/pi_driver.mjs --provider ollama --base-url $B/pi-ollama/v1
node harnesses/pi_driver.mjs --provider ollama --base-url $B/pi-ollama-steer/v1 --mid steer

$PY wire/where.py "$OUT" > results/phase0/where.md
echo "wrote results/phase0/where.md"
