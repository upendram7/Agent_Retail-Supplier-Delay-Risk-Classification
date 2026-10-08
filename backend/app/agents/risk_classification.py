from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    performance = state.get("supplier_performance", {})
    shipment = state.get("shipment_data", {})
    inventory = state.get("inventory_data", {})
    relationship = 0
    if performance.get("on_time_delivery_rate", 0.8) < 0.85:
        relationship += 0.4
    if performance.get("performance_trend") == "DETERIORATING":
        relationship += 0.2
    if shipment.get("risk_signal") == "HIGH":
        relationship += 0.2
    if inventory.get("stockout_risk") in {"HIGH", "MEDIUM"}:
        relationship += 0.2
    score = min(max(relationship, 0.15), 0.96)
    if score >= 0.7:
        risk = "HIGH"
        action = "Escalate supplier, create contingency plan, and notify procurement leadership."
    elif score >= 0.4:
        risk = "MEDIUM"
        action = "Monitor supplier performance and trigger a corrective action review."
    else:
        risk = "LOW"
        action = "Continue normal supplier management and monitor delivery signals."

    return {
        "risk_class": risk,
        "risk_score": round(score, 2),
        "confidence": 0.91,
        "key_risk_factors": [
            "Supplier delivery reliability is below the preferred threshold",
            "Current shipment is running behind expected schedule",
            "Inventory coverage is below the safety threshold",
            "Historical trend indicates worsening supplier performance",
        ],
        "supporting_evidence": [
            "Supplier on-time delivery rate below benchmark",
            "Current shipment delay indicators present",
            "Inventory supply risk is elevated",
        ],
        "recommended_action": action,
        "requires_human_review": risk == "HIGH",
    }
