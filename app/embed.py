"""Embed the policy chunks once and cache them to disk (offline step of RAG)."""

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.chunk import chunk_docs

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, local, free
CACHE_DIR = Path("data/embeddings")

_model = None


def get_model() -> SentenceTransformer:
    """Load the model once per process (loading takes a few seconds)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Return a (len(texts), 384) array of unit-length vectors."""
    return get_model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)


def build_index(docs_dir: str = "docs") -> tuple[list[dict], np.ndarray]:
    """Chunk + embed every doc, save to CACHE_DIR, and return (chunks, matrix)."""
    chunks = chunk_docs(docs_dir)
    matrix = embed_texts([c["text"] for c in chunks])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CACHE_DIR / "chunks.npy", matrix)
    (CACHE_DIR / "chunks.json").write_text(json.dumps(
        {"model": MODEL_NAME, "chunks": chunks}, indent=2))
    return chunks, matrix


def load_index() -> tuple[list[dict], np.ndarray]:
    """Load the cached index, rebuilding it if missing or built with another model."""
    meta_path = CACHE_DIR / "chunks.json"
    if not meta_path.exists():
        return build_index()
    meta = json.loads(meta_path.read_text())
    if meta["model"] != MODEL_NAME:
        return build_index()
    return meta["chunks"], np.load(CACHE_DIR / "chunks.npy")


if __name__ == "__main__":
    chunks, matrix = build_index()
    print(matrix.shape)                      # expect (28, 384)
    print(np.linalg.norm(matrix, axis=1)[:3])  # expect ~1.0 each
