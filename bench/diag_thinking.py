"""Diagnostic for Phase 2 on Claude: does replaying the model's own thinking change the result?

Phase 2 found hand-rolled and pi far apart in the data-tag arm (task done 1/10 vs 9/10 on
forged-consent). The difference found in the request bodies: Claude Haiku 5.5 returns
thinking blocks with empty text (display omitted) and a signature. Hand-rolled and Pydantic AI
send them back; pi 0.73 skips any thinking block whose text is empty (pi-ai
providers/anthropic.js, convertMessages). Here each of the two harnesses switches sides:
    hand-rolled, variant strip-thinking   drops thinking blocks from the history, as pi does
    pi, variant keep-thinking             asks for summarized thinking, so pi keeps the blocks

    python bench/diag_thinking.py --runs 10
Results: results/phase2-thinking/ (summary.md uses the Phase 2 table; columns = harness+variant).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "bench"))
import phase2  # noqa: E402
from phase2 import PLANTED  # noqa: E402


def main(runs, out, deliveries):
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for h, v in (("handrolled", "strip-thinking"), ("pi", "keep-thinking")):
        for sc in PLANTED:
            for d in deliveries:
                for i in range(runs):
                    jobs.append({"id": f"{sc}|{d}|{h}|anthropic|{i}", "scenario": sc, "delivery": d,
                                 "harness": h, "variant": v, "provider": "anthropic"})
    est = phase2.estimate(jobs, {"anthropic": (30000, 2000)})
    print(f"{len(jobs)} runs; estimate Claude ${est['anthropic']:.2f}")
    with open(out / "jobs.jsonl", "w") as f:
        for j in jobs:
            f.write(json.dumps(j) + "\n")
    phase2.run(out, 3, port=8780)
    phase2.score(out)
    s = (out / "summary.md").read_text().replace(
        "# Phase 2: real scenarios (the butler's inbox)",
        "# Phase 2 diagnostic: thinking replay switched (hand-rolled strips thinking, pi keeps it)")
    (out / "summary.md").write_text(s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--deliveries", nargs="*", default=["tool", "background-tagged"])
    a = ap.parse_args()
    main(a.runs, ROOT / "results/phase2-thinking", a.deliveries)
