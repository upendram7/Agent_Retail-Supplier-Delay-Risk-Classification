from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    risk = state.get("risk_classification", {}).get("risk_class", "MEDIUM")
    if risk == "HIGH":
        return {
            "action": "create_supplier_escalation",
            "status": "PENDING_APPROVAL",
            "requires_human_review": True,
            "summary": "Supplier escalation is proposed for human review; no action has been executed.",
        }
    return {
        "action": "monitor_supplier",
        "status": "NOT_EXECUTED",
        "requires_human_review": False,
        "summary": "Monitoring is recommended; no action has been executed.",
    }
