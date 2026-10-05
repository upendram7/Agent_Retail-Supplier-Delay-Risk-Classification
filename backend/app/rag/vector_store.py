from __future__ import annotations

from typing import Any, Dict, List
import uuid

try:
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None

from app.config import settings


class ChromaPolicyStore:
    def __init__(self, collection_name: str = "supplier_policies") -> None:
        self.collection_name = collection_name
        self.client = chromadb.Client() if chromadb is not None else None
        self.collection = None
        if self.client is not None:
            try:
                self.collection = self.client.get_or_create_collection(name=collection_name)
            except Exception:
                self.collection = None

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        if self.collection is None:
            return
        ids = []
        texts = []
        metas = []
        for doc in documents:
            ids.append(doc.get("id") or str(uuid.uuid4()))
            texts.append(doc["content"])
            metas.append({
                "title": doc.get("title", "Untitled"),
                "source": doc.get("source", "unknown"),
                "category": doc.get("category", "general"),
                "page": doc.get("page", 1),
                "section": doc.get("section", "overview"),
                "version": doc.get("version", "v1"),
                "effective_date": doc.get("effective_date", "2026-01-01"),
            })
        self.collection.add(documents=texts, ids=ids, metadatas=metas)

    def search(self, query: str, limit: int = 5, filter_dict: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if self.collection is None:
            return []
        kwargs: Dict[str, Any] = {"query_texts": [query], "n_results": limit}
        if filter_dict:
            kwargs["where"] = filter_dict
        results = self.collection.query(**kwargs)
        docs: List[Dict[str, Any]] = []
        for i in range(len(results.get("ids", [[]])[0])):
            doc = {
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
            docs.append(doc)
        return docs


policy_store = ChromaPolicyStore()
