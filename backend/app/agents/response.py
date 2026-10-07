from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> str:
    docs = state.get("retrieved_documents", [])
    classification = state["risk_classification"]
    risk = classification["risk_class"]
    score = classification["risk_score"]
    confidence = classification["confidence"]
    action = classification["recommended_action"]
    refs = ", ".join(item.get("title", "policy") for item in docs[:2]) if docs else "no policy references were retrieved"
    proposal = state.get("proposal", {})
    execution_status = proposal.get("summary", "No operational action has been executed.")
    evidence = "; ".join(classification["supporting_evidence"])
    return (
        f"Risk classification: {risk}. Risk score: {score}. Confidence: {confidence}. "
        f"Key action: {action}. Supporting evidence: {evidence}. "
        f"Relevant policy references: {refs}. {execution_status}"
    )
