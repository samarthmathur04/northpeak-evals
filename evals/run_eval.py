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
from app.cost import dollars
from evals.graders.llm_judge import JUDGE_MODEL, JUDGE_VERSION, judge

RESULTS = Path("evals/results")
USE_JUDGE = True   # --no-judge turns it off (faster/cheaper while iterating on tools)


def run_case(case: dict) -> dict:
    t0 = time.time()
    try:
        result = run_agent(case["message"], case.get("followups"))
        error = None
    except Exception as e:  # one crash shouldn't kill the whole run; it's a graded failure
        result, error = {"reply": "", "tool_calls": [], "stop": "error"}, repr(e)
    tools = grade_tool_calls(case, result)
    esc = grade_escalation(case, result)
    try:
        text = judge(case, result["reply"]) if USE_JUDGE else {"pass": True, "skipped": True, "failed": []}
    except Exception as e:  # judge crash != agent failure; record it, don't count it as a pass
        text = {"pass": False, "failed": [], "error": repr(e)}
    return {
        "id": case["id"], "category": case["category"], "message": case["message"],
        "reply": result["reply"], "stop": result["stop"], "error": error,
        "tool_calls": [{"name": c["name"], "input": c["input"], "output": c["output"]}
                       for c in result["tool_calls"]],
        "grades": {"tools": tools, "escalation": esc, "judge": text},
        "pass": tools["pass"] and esc["pass"] and text["pass"] and error is None,
        "latency_s": round(time.time() - t0, 2), "usage": result.get("usage", {}),
    }


def summarize(rows: list[dict]) -> dict:
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    rate = lambda rs, f: round(sum(f(r) for r in rs) / len(rs), 3)
    summary = {cat: {"n": len(rs),
                     "pass": rate(rs, lambda r: r["pass"]),
                     "tools": rate(rs, lambda r: r["grades"]["tools"]["pass"]),
                     "escalation": rate(rs, lambda r: r["grades"]["escalation"]["pass"]),
                     "judge": rate(rs, lambda r: r["grades"]["judge"]["pass"])}
               for cat, rs in sorted(by_cat.items())}
    summary["ALL"] = {"n": len(rows), "pass": rate(rows, lambda r: r["pass"]),
                      "tools": rate(rows, lambda r: r["grades"]["tools"]["pass"]),
                      "escalation": rate(rows, lambda r: r["grades"]["escalation"]["pass"]),
                      "judge": rate(rows, lambda r: r["grades"]["judge"]["pass"])}
    kinds = defaultdict(int)
    for r in rows:
        kinds[r["grades"]["escalation"]["kind"]] += 1
    summary["escalation_confusion"] = dict(kinds)
    return summary


def cost_summary(rows: list[dict], judge_key) -> dict:
    """$ and tokens for agent + judge, plus latency. judge_key(row) -> the judge result dict."""
    agent_u, judge_u = {}, {}
    for r in rows:
        for k, v in (r.get("usage") or {}).items():
            agent_u[k] = agent_u.get(k, 0) + v
        for k, v in ((judge_key(r) or {}).get("usage") or {}).items():
            judge_u[k] = judge_u.get(k, 0) + v
    a, j = dollars(MODEL, agent_u), dollars(JUDGE_MODEL, judge_u)
    lat = sorted(r["latency_s"] for r in rows if r.get("latency_s") is not None)
    out = {"agent_tokens": agent_u, "judge_tokens": judge_u,
           "agent_usd": round(a, 4), "judge_usd": round(j, 4), "total_usd": round(a + j, 4),
           "usd_per_case": round((a + j) / len(rows), 5) if rows else 0}
    if lat:
        out |= {"latency_p50_s": lat[len(lat) // 2], "latency_p90_s": lat[round(0.9 * (len(lat) - 1))]}
    print(f"cost: agent ${a:.3f} + judge ${j:.3f} = ${a + j:.3f}  (${(a + j) / max(len(rows), 1):.4f}/case)"
          + (f"   latency p50 {out['latency_p50_s']}s p90 {out['latency_p90_s']}s" if lat else ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--category")
    ap.add_argument("--golden", default="evals/golden_v1.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()
    global USE_JUDGE
    USE_JUDGE = not args.no_judge

    GOLDEN = Path(args.golden)
    cases = [json.loads(l) for l in GOLDEN.read_text().splitlines() if l.strip()]
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(run_case, cases))

    summary = summarize(rows)
    summary["cost"] = cost_summary(rows, lambda r: r["grades"]["judge"])
    print(f"\n{'category':<15}{'n':>4}{'pass':>8}{'tools':>8}{'esc':>8}{'judge':>8}")
    for cat, s in summary.items():
        if cat not in ("escalation_confusion", "cost"):
            print(f"{cat:<15}{s['n']:>4}{s['pass']:>8.0%}{s['tools']:>8.0%}{s['escalation']:>8.0%}{s['judge']:>8.0%}")
    print("escalation:", summary["escalation_confusion"])
    print("\nFAILED:", ", ".join(r["id"] for r in rows if not r["pass"]) or "none")
    for r in rows:
        for f in r["grades"]["judge"].get("failed", []):
            print(f"  judge {r['id']}: {f}")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"agent_{GOLDEN.stem}_{MODEL}_{PROMPT_VERSION}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"model": MODEL, "prompt_version": PROMPT_VERSION,
                               "judge": f"{JUDGE_MODEL}/{JUDGE_VERSION}" if USE_JUDGE else None,
                               "golden": GOLDEN.name, "summary": summary, "cases": rows},
                              indent=2, default=str))
    print("saved", out)


if __name__ == "__main__":
    main()
