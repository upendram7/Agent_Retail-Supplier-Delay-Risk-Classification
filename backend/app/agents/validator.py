from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> str:
    docs = state.get("retrieved_documents", [])
    classification = state.get("risk_classification", {})
    if not docs:
        return "RETRY"
    if not classification.get("risk_class"):
        return "BLOCK"
    if classification.get("risk_class") == "HIGH" and not state.get("human_approval"):
        return "HUMAN_REVIEW"
    return "PASS"
