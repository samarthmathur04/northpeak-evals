"""How much does the LLM judge agree with human labels?

  python -m evals.judge_agreement evals/human_labels/<run>.jsonl

Reports:
- % agreement: simple, but misleading when one answer dominates
  (a judge that ALWAYS says "pass" gets 95% if 95% of items are passes).
- Cohen's kappa: agreement corrected for chance.
    kappa = (p_o - p_e) / (1 - p_e)
    p_o = observed agreement
    p_e = agreement you'd expect by luck, given how often each rater says pass/fail
  ~0 = no better than chance, >0.6 substantial, >0.8 near-perfect (Landis & Koch rule of thumb).
- Confusion matrix + every disagreement, because the number tells you HOW MUCH,
  the disagreements tell you WHY (bad label? bad rubric rule? judge mistake? your mistake?).
"""
import json
import sys
from pathlib import Path


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    p_o = sum(h == j for h, j in pairs) / n
    h_pass = sum(h == "pass" for h, _ in pairs) / n
    j_pass = sum(j == "pass" for _, j in pairs) / n
    p_e = h_pass * j_pass + (1 - h_pass) * (1 - j_pass)
    return 1.0 if p_e == 1 else (p_o - p_e) / (1 - p_e)


def main():
    rows = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
    pairs = [(r["human"], r["judge"]) for r in rows]
    n = len(pairs)
    agree = sum(h == j for h, j in pairs)
    cm = {(h, j): sum(1 for p in pairs if p == (h, j)) for h in ("pass", "fail") for j in ("pass", "fail")}

    print(f"n = {n}   (sample is fail-enriched: all judge fails + random passes)")
    print(f"agreement = {agree}/{n} = {agree / n:.0%}")
    print(f"Cohen's kappa = {cohens_kappa(pairs):.2f}\n")
    print("                judge=pass  judge=fail")
    print(f"human=pass      {cm['pass', 'pass']:>9}  {cm['pass', 'fail']:>10}   <- judge too strict")
    print(f"human=fail      {cm['fail', 'pass']:>9}  {cm['fail', 'fail']:>10}   <- judge too lenient (worse: bugs slip through)")

    print("\nDISAGREEMENTS:")
    for r in rows:
        if r["human"] != r["judge"]:
            print(f"- {r['case_id']} [{r['type']}] \"{r['item']}\"  human={r['human']} judge={r['judge']}"
                  + (f"  note: {r['note']}" if r.get("note") else ""))


if __name__ == "__main__":
    main()
