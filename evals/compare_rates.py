"""Is the difference between two red-team runs real, or noise?

Usage:
  python -m evals.compare_rates <run_A.json> <run_B.json> --id rt_ind_003 --metric attempted
"""
import argparse
import json
from pathlib import Path


def count(run_path: Path, attack_id: str, metric: str) -> tuple[int, int]:
    """(k, n): how many runs of attack_id had metric True, out of how many."""
    runs = [r for r in json.loads(run_path.read_text())["runs"] if r["id"] == attack_id]
    return sum(bool(r[metric]) for r in runs), len(runs)


def compare(k_a: int, n_a: int, k_b: int, n_b: int) -> dict:
    """TODO(Samarth): your stats.

    Questions to answer in code:
      1. What are the two rates, and the difference (B - A)?
      2. Which test fits two proportions with small counts (some cells may be 0-5)?
         Hint: think about when a z-test's normal approximation breaks.
      3. One-sided or two-sided? We *hoped* rule 12 lowers attempts. Is that a reason to go one-sided?
      4. A CI on the difference, so you can say "rule 12 cut attempts by X points (95% CI ...)".
    scipy is installed (scipy.stats).
    Return a dict, e.g. {"rate_a":..., "rate_b":..., "diff":..., "p_value":..., "test":..., "ci95_diff":...}
    """
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a", type=Path)
    ap.add_argument("run_b", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--metric", default="attempted", choices=["attempted", "success"])
    args = ap.parse_args()
    k_a, n_a = count(args.run_a, args.id, args.metric)
    k_b, n_b = count(args.run_b, args.id, args.metric)
    print(f"A: {k_a}/{n_a}   B: {k_b}/{n_b}")
    print(json.dumps(compare(k_a, n_a, k_b, n_b), indent=2))


if __name__ == "__main__":
    main()
