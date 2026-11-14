"""BM25 keyword search over the policy chunks (the 'sparse' half of hybrid search)."""

import math
import re
from collections import Counter

from app.chunk import chunk_docs

K1 = 1.5   # how fast repeated words stop adding score (saturation)
B = 0.75   # how much to penalize long chunks


def tokenize(text: str) -> list[str]:
    """Lowercase words/numbers only: 'Plus member!' -> ['plus', 'member']."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.docs = [tokenize(c["text"]) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]          # word counts per chunk
        self.avg_len = sum(len(d) for d in self.docs) / len(self.docs)
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in set(d))  # chunks containing each word
        # IDF: rare words (few chunks) get a big weight, common words ~0.
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, doc in zip(self.tf, self.docs):
            s = 0.0
            for w in q:
                if w not in tf:
                    continue
                f = tf[w]
                norm = K1 * (1 - B + B * len(doc) / self.avg_len)
                s += self.idf[w] * f * (K1 + 1) / (f + norm)
            out.append(s)
        return out


_index = None


def retrieve_bm25(query: str, k: int = 3) -> list[dict]:
    global _index
    if _index is None:
        _index = BM25(chunk_docs())
    scores = _index.scores(query)
    top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [{**_index.chunks[i], "score": scores[i]} for i in top]
