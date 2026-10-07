from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> str:
    docs = state.get("retrieved_documents", [])
    classification = state.get("risk_classification", {})
    if classification.get("risk_class") not in {"LOW", "MEDIUM", "HIGH"}:
        return "BLOCK"
    if not docs:
        return "BLOCK"
    if classification["risk_class"] == "HIGH":
        return "HUMAN_REVIEW"
    return "PASS"
