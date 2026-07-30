"""Embeddings: one multilingual model, two vectors per claim (ADR-0006).

Model choice is `paraphrase-multilingual-MiniLM-L12-v2`. The smoke test in
tools/smoke_deps.py measured what actually matters for us: a code-mixed
Hinglish sentence against its English equivalent scored 0.827, while an
unrelated sentence scored -0.035. That gap is the entire reason strain
recognition survives a language switch, and it is measured, not assumed.

Loading is lazy because importing sentence-transformers costs ~4 s and the API
must answer /healthz before the model is warm.
"""
from __future__ import annotations

import threading
from typing import Sequence

from app.interfaces import EmbeddingModel

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformerEmbeddings(EmbeddingModel):
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(
                        self.model_name, cache_folder=self.cache_dir
                    )
        return self._model

    def warm(self) -> None:
        """Pay the load cost before the first request, not during it."""
        self.encode(["warm"])

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vecs = model.encode(list(texts), normalize_embeddings=True,
                            show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vecs]

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())


class HashingEmbeddings(EmbeddingModel):
    """Deterministic offline fallback — character n-gram hashing.

    This exists so that CI, the fixture generator, and the network-severed
    demo path never depend on a 470 MB download. It is genuinely worse at
    paraphrase than the real model, which is why it is a *fallback* and why
    tools/check_wiring.py fails the build if it is what production resolves to.
    """

    def __init__(self, dim: int = 384, ngram: int = 3) -> None:
        self._dim = dim
        self.ngram = ngram

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        import hashlib
        import math

        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            norm = " ".join((text or "").lower().split())
            grams = [norm[i:i + self.ngram] for i in range(max(0, len(norm) - self.ngram + 1))]
            grams += norm.split()
            for g in grams:
                h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
                vec[h % self._dim] += 1.0 if h & 1 else -1.0
            mag = math.sqrt(sum(v * v for v in vec))
            out.append([v / mag for v in vec] if mag else vec)
        return out

    @property
    def dim(self) -> int:
        return self._dim
