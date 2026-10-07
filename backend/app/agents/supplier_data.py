from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_supplier


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    supplier_id = intent.get("entities", {}).get("supplier_id", "SUP001")
    supplier = get_supplier(supplier_id)
    if not supplier:
        raise ValueError(f"Supplier not found: {supplier_id}")
    return {
        "supplier_id": supplier["supplier_id"],
        "supplier_name": supplier["supplier_name"],
        "country": supplier["country"],
        "supplier_category": supplier["supplier_category"],
        "lead_time_days": supplier["lead_time_days"],
        "on_time_delivery_rate": supplier["on_time_delivery_rate"],
        "active": supplier["active"],
        "risk_flags": supplier["risk_flags"],
    }
