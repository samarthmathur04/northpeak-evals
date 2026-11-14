"""Hybrid search: merge dense (embeddings) and BM25 (keywords) rankings."""

from app.bm25 import retrieve_bm25
from app.retrieve import retrieve

N_CHUNKS = 28   # pull full rankings from both, then merge
RRF_K = 60      # standard RRF constant: dampens the gap between rank 1 and rank 2


def retrieve_rrf(query: str, k: int = 3) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (RRF_K + rank)."""
    fused, by_id = {}, {}
    for results in (retrieve(query, N_CHUNKS), retrieve_bm25(query, N_CHUNKS)):
        for rank, r in enumerate(results, start=1):
            fused[r["id"]] = fused.get(r["id"], 0.0) + 1 / (RRF_K + rank)
            by_id[r["id"]] = r
    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**by_id[i], "score": fused[i]} for i in top]


def _minmax(results: list[dict]) -> dict[str, float]:
    lo, hi = min(r["score"] for r in results), max(r["score"] for r in results)
    return {r["id"]: (r["score"] - lo) / (hi - lo or 1) for r in results}


def retrieve_weighted(query: str, k: int = 3, w_dense: float = 0.5) -> list[dict]:
    """Min-max normalize each score list to 0-1, then weighted sum."""
    dense, sparse = retrieve(query, N_CHUNKS), retrieve_bm25(query, N_CHUNKS)
    d, s = _minmax(dense), _minmax(sparse)
    by_id = {r["id"]: r for r in dense}
    fused = {i: w_dense * d[i] + (1 - w_dense) * s.get(i, 0.0) for i in d}
    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**by_id[i], "score": fused[i]} for i in top]
