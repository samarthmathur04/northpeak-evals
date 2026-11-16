"""Hand-label judge items so we can measure how often the LLM judge agrees with a human.

Shows you one (reply, label item) pair at a time. You type p (pass) or f (fail).
You do NOT see the judge's verdict. If you did, you'd anchor on it and the
agreement number would be inflated (same reason labels are written blind).

Usage:
  python -m evals.label_judge                      # uses the latest golden_v1 run
  python -m evals.label_judge --run evals/results/<file>.json --n 50

Saves after every answer to evals/human_labels/<run>.jsonl, so you can quit (q) and resume.
"""
import argparse
import json
import random
import textwrap
from pathlib import Path

LABELS_DIR = Path("evals/human_labels")

DEFINITIONS = {
    "must_say": "PASS if the reply clearly tells the customer this (any wording).",
    "must_not_say": "PASS if the reply does NOT tell the customer this. FAIL if it does.",
}


def latest_run() -> Path:
    runs = sorted(Path("evals/results").glob("agent_golden_v1_*.json"), key=lambda p: p.stat().st_mtime)
    runs = [r for r in runs if any("items" in c["grades"].get("judge", {})
                                   for c in json.loads(r.read_text())["cases"])]
    return runs[-1]


def sample_items(run: dict, n: int, seed: int = 0) -> list[dict]:
    """All judge FAILs + random judge PASSes up to n.

    Why oversample fails: the judge passes ~95% of items. A random 50 would have ~2 fails,
    so we'd learn almost nothing about whether its fails are right. We record the
    sampling so it's reported honestly (agreement on a fail-enriched sample != on all items).
    """
    pool = []
    for c in run["cases"]:
        for g in c["grades"].get("judge", {}).get("items", []):
            if g["type"] == "nice_to_have":   # doesn't affect pass/fail, skip
                continue
            pool.append({"key": f"{c['id']}|{g['type']}|{g['item']}", "case_id": c["id"],
                         "message": c["message"], "reply": c["reply"],
                         "type": g["type"], "item": g["item"], "judge": g["verdict"]})
    rng = random.Random(seed)
    fails = [x for x in pool if x["judge"] == "fail"]
    passes = [x for x in pool if x["judge"] == "pass"]
    picked = fails + rng.sample(passes, min(len(passes), max(0, n - len(fails))))
    rng.shuffle(picked)   # so fails aren't bunched together (you'd notice the pattern)
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path)
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    run_path = args.run or latest_run()
    run = json.loads(run_path.read_text())
    items = sample_items(run, args.n)

    LABELS_DIR.mkdir(exist_ok=True)
    out = LABELS_DIR / f"{run_path.stem}.jsonl"
    done = {json.loads(l)["key"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    todo = [x for x in items if x["key"] not in done]
    print(f"run: {run_path.name}\nsaving to: {out}\n{len(done)} done, {len(todo)} to go. "
          f"Keys: p = pass, f = fail, s = skip, q = quit\n")

    for i, x in enumerate(todo, 1):
        print("=" * 80)
        print(f"[{len(done) + i}/{len(items)}]  case {x['case_id']}")
        print("\nCUSTOMER:\n" + textwrap.fill(x["message"], 100))
        print("\nAGENT REPLY:\n" + "\n".join(textwrap.fill(l, 100) for l in x["reply"].splitlines()))
        print(f"\n>>> [{x['type']}]  \"{x['item']}\"")
        print(f"    {DEFINITIONS[x['type']]}")
        while True:
            a = input("p / f / s / q > ").strip().lower()
            if a in {"p", "f", "s", "q"}:
                break
        if a == "q":
            break
        if a == "s":
            continue
        note = input("note (optional, enter to skip) > ").strip()
        row = {k: x[k] for k in ("key", "case_id", "type", "item", "judge")}
        row.update(human="pass" if a == "p" else "fail", note=note)
        with out.open("a") as f:   # append per answer -> nothing lost if you quit
            f.write(json.dumps(row) + "\n")

    print(f"\nSaved. Run: python -m evals.judge_agreement {out}")


if __name__ == "__main__":
    main()
