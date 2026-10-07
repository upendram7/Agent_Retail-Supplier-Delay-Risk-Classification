from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

from app.rag.vector_store import policy_store
from app.services.data_service import get_policy_documents
from app.services.observability import current_trace_context, store


def run(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = "supplier delay risk classification procurement policy"
    started = time.perf_counter()
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
    context = current_trace_context()
    elapsed_ms = (time.perf_counter() - started) * 1000
    store.record_rag_call(
        query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
        documents=results,
        latency_ms=elapsed_ms,
        context_size=sum(len(item.get("content", "")) for item in results),
        context_tokens=sum(len(item.get("content", "").split()) for item in results),
        request_id=context.get("request_id"),
        trace_id=context.get("trace_id"),
        session_id=context.get("session_id"),
    )
    return results
