"""Strain centroid search (ADR-0010).

Two implementations, and the default is the boring one.

`InMemoryVectorIndex` is brute-force cosine over a numpy matrix. At our scale —
hundreds to low thousands of strains — an exact scan is both faster than an ANN
index and has no build step, no background compaction, and no recall cliff.
The p95 cache-hit budget is 300 ms end to end; a 2000x384 matmul is ~0.2 ms, so
the index is not where the budget goes. Choosing an approximate index here would
have bought nothing and cost us exact recall, which strain memory depends on.

`ChromaVectorIndex` persists across restarts and is what a real multi-tenant
deployment would use. It is wired when a persist directory is configured.
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from app.interfaces import VectorIndex


class InMemoryVectorIndex(VectorIndex):
    def __init__(self) -> None:
        self._ids: dict[str, list[str]] = {}
        self._mat: dict[str, np.ndarray] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def upsert(self, strain_id: str, vector: Sequence[float], namespace: str,
               metadata: dict[str, Any] | None = None) -> None:
        if not vector:
            return
        v = np.asarray(vector, dtype=np.float32)
        n = np.linalg.norm(v)
        if n:
            v = v / n
        ids = self._ids.setdefault(namespace, [])
        if strain_id in ids:
            self._mat[namespace][ids.index(strain_id)] = v
        else:
            ids.append(strain_id)
            existing = self._mat.get(namespace)
            self._mat[namespace] = v[None, :] if existing is None else np.vstack([existing, v[None, :]])
        self._meta[f"{namespace}/{strain_id}"] = metadata or {}

    def query(self, vector: Sequence[float], namespace: str, k: int = 5
              ) -> list[tuple[str, float]]:
        mat = self._mat.get(namespace)
        ids = self._ids.get(namespace, [])
        if mat is None or not ids or not vector:
            return []
        q = np.asarray(vector, dtype=np.float32)
        n = np.linalg.norm(q)
        if n:
            q = q / n
        sims = mat @ q
        top = np.argsort(-sims)[:k]
        return [(ids[i], float(sims[i])) for i in top]

    def count(self, namespace: str) -> int:
        return len(self._ids.get(namespace, []))

    def clear(self) -> None:
        self._ids.clear()
        self._mat.clear()
        self._meta.clear()


class ChromaVectorIndex(VectorIndex):
    """Persistent variant. Same contract, survives a restart."""

    def __init__(self, persist_dir: str) -> None:
        import chromadb
        try:
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=persist_dir, settings=Settings(anonymized_telemetry=False))
        except Exception:
            # Chroma's Settings surface has moved twice across majors; the
            # index is not worth failing startup over.
            self._client = chromadb.PersistentClient(path=persist_dir)
        self._cols: dict[str, Any] = {}

    def _col(self, namespace: str):
        if namespace not in self._cols:
            self._cols[namespace] = self._client.get_or_create_collection(
                namespace, metadata={"hnsw:space": "cosine"})
        return self._cols[namespace]

    def upsert(self, strain_id: str, vector: Sequence[float], namespace: str,
               metadata: dict[str, Any] | None = None) -> None:
        if not vector:
            return
        self._col(namespace).upsert(
            ids=[strain_id], embeddings=[list(vector)],
            metadatas=[metadata or {"_": ""}])

    def query(self, vector: Sequence[float], namespace: str, k: int = 5
              ) -> list[tuple[str, float]]:
        if not vector:
            return []
        col = self._col(namespace)
        if col.count() == 0:
            return []
        res = col.query(query_embeddings=[list(vector)], n_results=min(k, col.count()))
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        # Chroma returns cosine *distance*; the contract is similarity.
        return [(i, 1.0 - float(d)) for i, d in zip(ids, dists)]

    def count(self, namespace: str) -> int:
        return int(self._col(namespace).count())
