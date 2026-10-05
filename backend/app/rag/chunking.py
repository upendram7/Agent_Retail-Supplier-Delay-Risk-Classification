from __future__ import annotations

from typing import List, Dict, Any


def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    for idx in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[idx:idx + chunk_size]))
    return chunks
