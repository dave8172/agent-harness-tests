"""Send one recorded request body to the real API, to see whether the provider accepts it.

Phase 0 only records; this checks the handful of recorded shapes whose validity we
can't know from the docs (a system message between a call and its result, a request
that ends on an assistant turn). Prints the status and the start of the reply or error.
Costs a fraction of a cent per call.

    python wire/replay.py results/phase0/wire/pydantic-openai-responses/04.json
"""

import json
import os
import sys
from pathlib import Path

try:
    import httpx2 as httpx  # what the SDKs use as of late 2026
except ImportError:
    import httpx



def main(path):
    rec = json.loads(Path(path).read_text())
    body = rec["body"]
    body.pop("stream", None)
    if rec["path"].endswith("/messages"):
        url = "https://api.anthropic.com/v1/messages"
        key = os.environ["ANTHROPIC_API_KEY"]
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body["max_tokens"] = 200
    else:
        url = "https://api.openai.com/v1" + rec["path"][len("/v1"):]
        key = os.environ["OPENAI_API_KEY"]
        headers = {"authorization": f"Bearer {key}"}
        if rec["path"].endswith("/responses"):
            body["max_output_tokens"] = 300
            # ids of items the fake server made up would be looked up server-side
            for it in body.get("input", []):
                if isinstance(it, dict):
                    it.pop("id", None)
        else:
            body["max_completion_tokens"] = 300
    r = httpx.post(url, json=body, headers=headers, timeout=60)
    print(r.status_code)
    print(r.text[:1200])


if __name__ == "__main__":
    main(sys.argv[1])
