from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    classification = state.get("risk_classification", {})
    docs = state.get("retrieved_documents", [])
    evidence = [
        "Supplier performance is degrading over recent orders",
        "Current shipment is delayed beyond expected date",
        "Inventory coverage is below the safety stock threshold",
    ]
    return {
        "issue_type": "SUPPLIER_DELAY_RISK",
        "risk_class": classification.get("risk_class", "MEDIUM"),
        "evidence": evidence,
        "policy_reference": [item.get("title", "Procurement policy") for item in docs[:2]],
        "business_impact": "HIGH" if classification.get("risk_class") == "HIGH" else "MEDIUM",
        "recommended_action": classification.get("recommended_action", "Review supplier risk"),
        "confidence": classification.get("confidence", 0.9),
        "requires_human_review": classification.get("requires_human_review", False),
    }
