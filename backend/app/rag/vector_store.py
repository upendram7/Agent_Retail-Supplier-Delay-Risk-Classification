from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from typing import Any, Dict, List

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from app.config import settings

logger = logging.getLogger(__name__)


class ChromaPolicyStore:
    def __init__(self, collection_name: str = "supplier_policies") -> None:
        self.collection_name = collection_name
        self._documents: Dict[str, Dict[str, Any]] = {}
        self.embedding_dimension = 1536
        self._openai_client = None

        if OpenAI is not None and os.getenv("OPENAI_API_KEY"):
            try:
                self._openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception:  # pragma: no cover
                self._openai_client = None

        # Chroma's default client and default ONNX embedding setup can trigger an
        # automatic model download on serverless hosts such as Vercel. We avoid that
        # by creating an in-memory ephemeral client and by always passing embeddings
        # explicitly instead of relying on Chroma's default embedding function.
        self.client = None
        self.collection = None
        if chromadb is not None:
            try:
                self.client = chromadb.EphemeralClient()
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=None,
                )
            except Exception:
                self.client = None
                self.collection = None

    def _build_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": doc.get("title", "Untitled"),
            "source": doc.get("source", "unknown"),
            "category": doc.get("category", "general"),
            "page": doc.get("page", 1),
            "section": doc.get("section", "overview"),
            "version": doc.get("version", "v1"),
            "effective_date": doc.get("effective_date", "2026-01-01"),
        }

    def _embed_text(self, text: str) -> List[float]:
        if self._openai_client is not None:
            try:
                response = self._openai_client.embeddings.create(
                    model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                    input=text,
                )
                values = response.data[0].embedding
                if values:
                    return [float(value) for value in values]
            except Exception:
                pass

        # Deterministic local fallback: hash-based vector, no model downloads and no
        # file writes. This keeps the demo working in local Codespaces and Vercel.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [0.0] * 32
        for index in range(32):
            byte = digest[index % len(digest)]
            vector[index] = ((byte / 255.0) * 2.0) - 1.0
        return vector

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        for doc in documents:
            item = {
                "id": doc.get("id") or str(uuid.uuid4()),
                "title": doc.get("title", "Untitled"),
                "content": doc.get("content", ""),
                "metadata": self._build_metadata(doc),
            }
            self._documents[str(item["id"])] = item

        if self.collection is None:
            return

        ids: List[str] = []
        texts: List[str] = []
        embeddings: List[List[float]] = []
        metas: List[Dict[str, Any]] = []
        for doc in documents:
            item_id = doc.get("id") or str(uuid.uuid4())
            text = doc.get("content", "")
            ids.append(item_id)
            texts.append(text)
            embeddings.append(self._embed_text(text))
            metas.append(self._build_metadata(doc))

        try:
            self.collection.upsert(documents=texts, ids=ids, embeddings=embeddings, metadatas=metas)
        except Exception:
            logger.exception("Chroma policy indexing failed; in-memory retrieval remains available")

    def _normalize_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        ids = results.get("ids", [[]])
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        if not ids or not documents:
            return []

        normalized: List[Dict[str, Any]] = []
        for index in range(len(ids[0])):
            metadata = metadatas[0][index] if len(metadatas[0]) > index else {}
            text = documents[0][index] if len(documents[0]) > index else ""
            distance = distances[0][index] if distances and len(distances[0]) > index else None
            normalized.append({
                "id": ids[0][index],
                "title": metadata.get("title", "Policy"),
                "content": text,
                "similarity_score": 1 / (1 + max(float(distance), 0)) if distance is not None else None,
                "metadata": metadata,
            })
        return normalized

    def _fallback_search(self, query: str, limit: int = 5, filter_dict: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if not self._documents:
            return []

        normalized_query = re.sub(r"[^a-z0-9 ]", " ", query.lower())
        tokens = {token for token in normalized_query.split() if token}
        scored: List[tuple[float, Dict[str, Any]]] = []

        for doc in self._documents.values():
            metadata = doc.get("metadata", {})
            if filter_dict:
                matched = True
                for key, value in filter_dict.items():
                    if metadata.get(key) != value:
                        matched = False
                        break
                if not matched:
                    continue

            content = f"{doc.get('title', '')} {doc.get('content', '')} {' '.join(f'{k}:{v}' for k, v in metadata.items())}"
            lower_content = content.lower()
            score = 0.0
            for token in tokens:
                if token in lower_content:
                    score += 2.0
            if tokens and score == 0.0:
                # Still return relevant documents even if the query is generic, using a
                # light lexical fallback rather than crashing the workflow.
                score = 0.1
            scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "id": item["id"],
                "title": item.get("title", "Policy"),
                "content": item["content"],
                "similarity_score": min(score / max(len(tokens) * 2, 1), 1.0),
                "metadata": item.get("metadata", {}),
            }
            for score, item in scored[:limit]
        ]

    def search(self, query: str, limit: int = 5, filter_dict: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if self.collection is not None:
            try:
                results = self.collection.query(
                    query_embeddings=[self._embed_text(query)],
                    n_results=limit,
                    where=filter_dict,
                )
                normalized = self._normalize_results(results)
                if normalized:
                    return normalized
            except Exception:
                # Fall back to the lightweight deterministic in-memory matcher rather than
                # crashing on a serverless filesystem restriction or Chroma init issue.
                pass

        return self._fallback_search(query, limit=limit, filter_dict=filter_dict)


policy_store = ChromaPolicyStore()
