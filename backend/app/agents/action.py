from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    risk = state.get("risk_classification", {}).get("risk_class", "MEDIUM")
    if risk == "HIGH":
        return {
            "action": "create_supplier_escalation",
            "status": "PENDING_APPROVAL",
            "requires_human_review": True,
            "summary": "Supplier escalation and contingency planning request created for approval.",
        }
    return {
        "action": "monitor_supplier",
        "status": "AUTO_APPROVED",
        "requires_human_review": False,
        "summary": "Supplier monitored under standard operations workflow.",
    }
