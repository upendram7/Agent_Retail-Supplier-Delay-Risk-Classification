from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> str:
    classification = state.get("risk_classification", {})
    risk = classification.get("risk_class", "MEDIUM")
    score = classification.get("risk_score", 0.5)
    confidence = classification.get("confidence", 0.8)
    action = classification.get("recommended_action", "Review supplier performance")
    docs = state.get("retrieved_documents", [])
    refs = ", ".join(item.get("title", "policy") for item in docs[:2]) if docs else "internal procurement policy"
    return (
        f"Risk classification: {risk}. Risk score: {score}. Confidence: {confidence}. "
        f"Key action: {action}. Evidence includes supplier delivery trend and current shipment delay. "
        f"Relevant policy references: {refs}."
    )
