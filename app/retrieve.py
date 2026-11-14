"""Online step of RAG: find the top-k chunks for a customer message."""

import numpy as np

from app.embed import embed_texts, load_index
from app.query_clean import clean_query


def retrieve(query: str, k: int = 5, clean: bool = True) -> list[dict]:
    """Return the k most similar chunks to `query`, best first.

    Defaults = winner of retrieval eval: dense + query cleaning, k=5 (full-hit 0.83).

    Each result: {"id": ..., "heading": ..., "text": ..., "score": float}
    """
    chunks, matrix = load_index()  # matrix: (28, 384), rows are unit length

    if clean:
        query = clean_query(query)            # strip emails / order #s (noise)
    query_vec = embed_texts([query])[0]       # (1, 384) -> (384,)
    scores = matrix @ query_vec               # (28, 384) @ (384,) -> (28,) cosine scores
    top = np.argsort(scores)[::-1][:k]        # indices sorted high -> low, keep k

    return [{**chunks[i], "score": float(scores[i])} for i in top]


if __name__ == "__main__":
    for q in ["can i return a final sale jacket?",
              "how long does shipping take",
              "my tent is leaking after a year"]:
        print(f"\n{q}")
        for r in retrieve(q):
            print(f"  {r['score']:.3f}  {r['id']:<12} {r['heading']}")
