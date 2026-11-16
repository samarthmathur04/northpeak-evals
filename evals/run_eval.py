"""Run the agent on the golden set, grade with code graders, save results.

Usage:
  python3 -m evals.run_eval                 # all cases
  python3 -m evals.run_eval --ids tool_006 edge_001
  python3 -m evals.run_eval --category escalate
"""
import argparse
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.agent import MODEL, run_agent
from app.prompts import PROMPT_VERSION
from evals.graders.code_graders import grade_escalation, grade_tool_calls

GOLDEN = Path("evals/golden_v1.jsonl")
RESULTS = Path("evals/results")


def run_case(case: dict) -> dict:
    t0 = time.time()
    try:
        result = run_agent(case["message"])
        error = None
    except Exception as e:  # one crash shouldn't kill the whole run; it's a graded failure
        result, error = {"reply": "", "tool_calls": [], "stop": "error"}, repr(e)
    tools = grade_tool_calls(case, result)
    esc = grade_escalation(case, result)
    return {
        "id": case["id"], "category": case["category"], "message": case["message"],
        "reply": result["reply"], "stop": result["stop"], "error": error,
        "tool_calls": [{"name": c["name"], "input": c["input"], "output": c["output"]}
                       for c in result["tool_calls"]],
        "grades": {"tools": tools, "escalation": esc},
        "pass": tools["pass"] and esc["pass"] and error is None,
        "latency_s": round(time.time() - t0, 2),
    }


def summarize(rows: list[dict]) -> dict:
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    rate = lambda rs, f: round(sum(f(r) for r in rs) / len(rs), 3)
    summary = {cat: {"n": len(rs),
                     "pass": rate(rs, lambda r: r["pass"]),
                     "tools": rate(rs, lambda r: r["grades"]["tools"]["pass"]),
                     "escalation": rate(rs, lambda r: r["grades"]["escalation"]["pass"])}
               for cat, rs in sorted(by_cat.items())}
    summary["ALL"] = {"n": len(rows), "pass": rate(rows, lambda r: r["pass"]),
                      "tools": rate(rows, lambda r: r["grades"]["tools"]["pass"]),
                      "escalation": rate(rows, lambda r: r["grades"]["escalation"]["pass"])}
    kinds = defaultdict(int)
    for r in rows:
        kinds[r["grades"]["escalation"]["kind"]] += 1
    summary["escalation_confusion"] = dict(kinds)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--category")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    cases = [json.loads(l) for l in GOLDEN.read_text().splitlines() if l.strip()]
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(run_case, cases))

    summary = summarize(rows)
    print(f"\n{'category':<15}{'n':>4}{'pass':>8}{'tools':>8}{'esc':>8}")
    for cat, s in summary.items():
        if cat != "escalation_confusion":
            print(f"{cat:<15}{s['n']:>4}{s['pass']:>8.0%}{s['tools']:>8.0%}{s['escalation']:>8.0%}")
    print("escalation:", summary["escalation_confusion"])
    print("\nFAILED:", ", ".join(r["id"] for r in rows if not r["pass"]) or "none")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"agent_{MODEL}_{PROMPT_VERSION}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"model": MODEL, "prompt_version": PROMPT_VERSION,
                               "golden": GOLDEN.name, "summary": summary, "cases": rows},
                              indent=2, default=str))
    print("saved", out)


if __name__ == "__main__":
    main()
