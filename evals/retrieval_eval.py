"""Retrieval eval: recall@k and full-hit rate over the golden set.

Run: python -m evals.retrieval_eval
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.embed import MODEL_NAME
from app.bm25 import retrieve_bm25
from app.hybrid import retrieve_rrf, retrieve_weighted
from app.retrieve import retrieve

GOLDEN = Path("evals/golden_v1.jsonl")
RESULTS_DIR = Path("evals/results")
KS = [1, 3, 5]


def recall_at_k(relevant: list[str], retrieved: list[str]) -> float:
    """Fraction of the needed chunks that showed up in the top k."""
    hits = sum(1 for chunk_id in relevant if chunk_id in retrieved)
    return hits / len(relevant)


RETRIEVERS = {"dense": retrieve, "bm25": retrieve_bm25,
              "rrf": retrieve_rrf, "weighted": retrieve_weighted}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=RETRIEVERS, default="dense")
    mode = ap.parse_args().mode
    retrieve_fn = RETRIEVERS[mode]

    cases = [json.loads(l) for l in GOLDEN.read_text().splitlines() if l.strip()]
    cases = [c for c in cases if c["relevant_chunks"]]  # skip "no doc needed" cases

    rows = []
    for c in cases:
        retrieved = [r["id"] for r in retrieve_fn(c["message"], k=max(KS))]
        row = {"id": c["id"], "relevant": c["relevant_chunks"], "retrieved": retrieved}
        for k in KS:
            row[f"recall@{k}"] = recall_at_k(c["relevant_chunks"], retrieved[:k])
        rows.append(row)

    print(f"[{mode}] {len(rows)} cases (skipped no-doc cases)\n")
    summary = {}
    for k in KS:
        recalls = [r[f"recall@{k}"] for r in rows]
        summary[k] = {"mean_recall": sum(recalls) / len(recalls),
                      "full_hit_rate": sum(x == 1.0 for x in recalls) / len(recalls)}
        print(f"k={k}:  mean recall {summary[k]['mean_recall']:.2f}   "
              f"full-hit rate {summary[k]['full_hit_rate']:.2f}")

    k = 3
    print(f"\nMisses at k={k}:")
    for r in rows:
        if r[f"recall@{k}"] < 1.0:
            missing = [c for c in r["relevant"] if c not in r["retrieved"][:k]]
            print(f"  {r['id']:<13} missing {missing}  got {r['retrieved'][:k]}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"retrieval_{mode}_{stamp}.json"
    out.write_text(json.dumps({"mode": mode, "model": MODEL_NAME if mode == "dense" else None, "summary": summary, "cases": rows}, indent=2))
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
