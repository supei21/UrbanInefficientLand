from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from tianshu_core.rag.config import PolicyRagSettings
from tianshu_core.rag.documents import PolicyDocument, load_documents
from tianshu_core.rag.embeddings import cosine_similarity, embed_text

_INDEX_CACHE: dict[tuple[str, int, int, int], dict[str, Any]] = {}
_SEARCH_CACHE: dict[tuple[str, int, int, int], PolicySearchBackend] = {}


def search_policy_documents(
    query: str, settings: PolicyRagSettings, k: int | None = None
) -> list[dict[str, Any]]:
    if settings.backend.lower() == "chroma":
        from tianshu_core.rag.chroma_store import get_chroma_store

        return get_chroma_store(settings).dual_search(query, max(1, k or settings.retrieval_k))[
            : max(1, k or settings.retrieval_k)
        ]
    backend = load_search_backend(settings)
    return backend.search(query, max(1, k or settings.retrieval_k))


def load_search_backend(settings: PolicyRagSettings) -> PolicySearchBackend:
    cache_key = _settings_cache_key(settings)
    cached = _SEARCH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    index = load_or_build_index(settings)
    backend = PolicySearchBackend(index.get("documents", []))
    _SEARCH_CACHE[cache_key] = backend
    return backend


@dataclass
class PolicySearchBackend:
    documents: list[dict[str, Any]]

    def __post_init__(self) -> None:
        self._nearest = None
        self._matrix = None
        self._use_nearest_neighbors = False
        # Small local policy libraries are faster and more stable with the
        # deterministic linear scorer; only build sklearn structures for
        # genuinely large indexes.
        if len(self.documents) >= 1000:
            self._build_nearest_neighbors()

    def search(self, query: str, k: int) -> list[dict[str, Any]]:
        if not self.documents:
            return []
        query_vector = embed_text(query)
        candidate_count = min(len(self.documents), max(k * 4, k + 12))
        if self._use_nearest_neighbors:
            scored = self._search_nearest_neighbors(query_vector, candidate_count)
        else:
            scored = self._search_linear(query_vector, candidate_count)
        selected = _select_balanced_results(scored, k)
        return [_format_result(score, item) for score, item in selected]

    def _build_nearest_neighbors(self) -> None:
        try:
            import numpy as np
            from sklearn.neighbors import NearestNeighbors
        except Exception:
            return
        matrix = np.array([item["embedding"] for item in self.documents], dtype="float32")
        if matrix.size == 0:
            return
        nearest = NearestNeighbors(metric="cosine", algorithm="brute")
        nearest.fit(matrix)
        self._matrix = matrix
        self._nearest = nearest
        self._use_nearest_neighbors = True

    def _search_nearest_neighbors(
        self, query_vector: list[float], k: int
    ) -> list[tuple[float, dict[str, Any]]]:
        import numpy as np

        limit = min(k, len(self.documents))
        distances, indices = self._nearest.kneighbors(
            np.array([query_vector], dtype="float32"),
            n_neighbors=limit,
        )
        return [
            (1.0 - float(distance), self.documents[int(index)])
            for distance, index in zip(distances[0], indices[0], strict=True)
        ]

    def _search_linear(
        self, query_vector: list[float], k: int
    ) -> list[tuple[float, dict[str, Any]]]:
        scored = []
        for item in self.documents:
            score = cosine_similarity(query_vector, item["embedding"])
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:k]


def _format_result(score: float, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": item["metadata"].get("source", ""),
        "type": item["metadata"].get("type", ""),
        "score": round(score, 6),
        "rule_id": item["metadata"].get("rule_id"),
        "policy_name": item["metadata"].get("policy_name"),
        "category": item["metadata"].get("category"),
        "article_ref": item["metadata"].get("article_ref"),
        "content": item["content"],
    }


def _select_balanced_results(
    scored: list[tuple[float, dict[str, Any]]], k: int
) -> list[tuple[float, dict[str, Any]]]:
    """Keep distinct policy files visible when rule chunks dominate similarity scores."""

    if k <= 0:
        return []
    ranked = sorted(scored, key=lambda pair: pair[0], reverse=True)
    policy_target = (k + 1) // 2
    selected: list[tuple[float, dict[str, Any]]] = []
    selected_ids: set[int] = set()
    policy_sources: set[str] = set()

    for score, item in ranked:
        metadata = item.get("metadata", {})
        if metadata.get("type") != "policy":
            continue
        source = str(metadata.get("source") or "")
        if source in policy_sources:
            continue
        selected.append((score, item))
        selected_ids.add(id(item))
        policy_sources.add(source)
        if len(policy_sources) >= policy_target:
            break

    for score, item in ranked:
        if len(selected) >= k:
            break
        if id(item) in selected_ids:
            continue
        metadata = item.get("metadata", {})
        if metadata.get("type") == "policy":
            source = str(metadata.get("source") or "")
            if source in policy_sources:
                continue
            policy_sources.add(source)
        selected.append((score, item))
        selected_ids.add(id(item))

    return sorted(selected, key=lambda pair: pair[0], reverse=True)


def search_policy_documents_linear(
    query: str, settings: PolicyRagSettings, k: int | None = None
) -> list[dict[str, Any]]:
    index = load_or_build_index(settings)
    query_vector = embed_text(query)
    scored = []
    for item in index.get("documents", []):
        score = cosine_similarity(query_vector, item["embedding"])
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    limit = max(1, k or settings.retrieval_k)
    return [_format_result(score, item) for score, item in _select_balanced_results(scored, limit)]


def load_or_build_index(settings: PolicyRagSettings) -> dict[str, Any]:
    cache_key = _settings_cache_key(settings)
    cached = _INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached

    docs = load_documents(settings)
    source_hash = documents_hash(docs)
    if settings.index_path.exists():
        try:
            payload = json.loads(settings.index_path.read_text(encoding="utf-8"))
            if payload.get("source_hash") == source_hash:
                _INDEX_CACHE[cache_key] = payload
                return payload
        except json.JSONDecodeError:
            pass
    payload = build_index_payload(docs, source_hash)
    settings.index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _INDEX_CACHE[cache_key] = payload
    return payload


def build_index_payload(docs: list[PolicyDocument], source_hash: str) -> dict[str, Any]:
    return {
        "source_hash": source_hash,
        "count": len(docs),
        "documents": [
            {
                "content": doc.content,
                "metadata": doc.metadata,
                "embedding": embed_text(doc.content),
            }
            for doc in docs
        ],
    }


def documents_hash(docs: list[PolicyDocument]) -> str:
    digest = hashlib.md5()
    for doc in docs:
        digest.update(doc.content.encode("utf-8"))
        digest.update(json.dumps(doc.metadata, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def _settings_cache_key(settings: PolicyRagSettings) -> tuple[str, int, int, int]:
    return (
        str(settings.policy_dir.resolve()),
        settings.retrieval_k,
        settings.chunk_size,
        settings.chunk_overlap,
    )
