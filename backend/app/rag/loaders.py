from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any


def load_policy_documents(directory: str | Path) -> List[Dict[str, Any]]:
    base_dir = Path(directory)
    docs: List[Dict[str, Any]] = []
    if not base_dir.exists():
        return docs
    for file in sorted(base_dir.glob("*.md")):
        docs.append({
            "id": file.stem,
            "title": file.stem.replace("-", " ").title(),
            "content": file.read_text(encoding="utf-8"),
            "source": str(file),
            "category": "procurement_policy",
            "page": 1,
            "section": "document",
            "version": "v1",
            "effective_date": "2026-01-01",
        })
    return docs
