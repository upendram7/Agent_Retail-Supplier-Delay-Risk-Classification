from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    performance = state.get("supplier_performance", {})
    shipment = state.get("shipment_data", {})
    inventory = state.get("inventory_data", {})
    on_time_delivery_rate = performance["on_time_delivery_rate"]
    shipment_risk = shipment["risk_signal"]
    stockout_risk = inventory["stockout_risk"]
    relationship = 0
    if on_time_delivery_rate < 0.85:
        relationship += 0.4
    if performance.get("performance_trend") == "DETERIORATING":
        relationship += 0.2
    if shipment_risk == "HIGH":
        relationship += 0.2
    if stockout_risk in {"HIGH", "MEDIUM"}:
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

    risk_factors = []
    evidence = []
    if on_time_delivery_rate < 0.85:
        risk_factors.append("Supplier delivery reliability is below the preferred threshold")
        evidence.append(f"Supplier on-time delivery rate is {on_time_delivery_rate:.0%}.")
    else:
        evidence.append(f"Supplier on-time delivery rate is {on_time_delivery_rate:.0%}.")
    if performance.get("performance_trend") == "DETERIORATING":
        risk_factors.append("Historical supplier performance is deteriorating")
        evidence.extend(performance.get("risk_factors", []))
    if shipment_risk in {"HIGH", "MEDIUM"}:
        risk_factors.append("Current shipment has an elevated delay risk")
        evidence.extend(shipment.get("delay_indicators", []))
    else:
        evidence.append(f"Current shipment risk signal is {shipment_risk}.")
    if stockout_risk in {"HIGH", "MEDIUM"}:
        risk_factors.append("Inventory coverage is below the safety threshold")
        evidence.append(
            f"Inventory stockout risk is {stockout_risk}; days of supply: {inventory['days_of_supply']}."
        )
    else:
        evidence.append(f"Inventory stockout risk is {stockout_risk}.")

    return {
        "risk_class": risk,
        "risk_score": round(score, 2),
        "confidence": 0.91,
        "key_risk_factors": risk_factors,
        "supporting_evidence": evidence,
        "recommended_action": action,
        "requires_human_review": risk == "HIGH",
    }
