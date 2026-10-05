from __future__ import annotations

from typing import Any, Dict, List


def retrieve_documents(store: Any, query: str, limit: int = 3) -> List[Dict[str, Any]]:
    return store.search(query, limit=limit)
