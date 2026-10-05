from __future__ import annotations

from typing import Any


def embed_text(text: str) -> list[float]:
    # This demo intentionally uses a lightweight deterministic placeholder embedding.
    # In production, this should be replaced by a real embedding model integration.
    return [float((ord(ch) % 10) + 1) for ch in text[:32]]
