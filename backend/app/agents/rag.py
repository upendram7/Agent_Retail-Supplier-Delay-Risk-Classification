from __future__ import annotations

from typing import Any, Dict, List

from app.rag.vector_store import policy_store
from app.services.data_service import get_policy_documents


def run(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = "supplier delay risk classification procurement policy"
    docs = get_policy_documents()
    if docs:
        store_docs = [{
            "id": str(item.get("document_id", idx)),
            "title": item.get("title", "Policy"),
            "content": item.get("content", ""),
            "source": item.get("source", "policy"),
            "category": item.get("category", "supplier_policy"),
            "page": item.get("page", 1),
            "section": item.get("section", "overview"),
            "version": item.get("version", "v1"),
            "effective_date": item.get("effective_date", "2026-01-01"),
        } for idx, item in enumerate(docs)]
        policy_store.add_documents(store_docs)
    results = policy_store.search(query, limit=3)
    return results
