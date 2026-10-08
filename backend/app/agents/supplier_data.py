from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_demo_case, get_supplier


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    supplier_id = intent.get("entities", {}).get("supplier_id", "SUP001")
    supplier = get_supplier(supplier_id)
    if not supplier:
        supplier = get_demo_case()["supplier"]
    return {
        "supplier_id": supplier.get("supplier_id", supplier_id),
        "supplier_name": supplier.get("supplier_name", "Alpha Manufacturing"),
        "country": supplier.get("country", "India"),
        "supplier_category": supplier.get("supplier_category", "Electronics"),
        "lead_time_days": supplier.get("lead_time_days", 14),
        "on_time_delivery_rate": supplier.get("on_time_delivery_rate", 0.82),
        "active": supplier.get("active", True),
        "risk_flags": supplier.get("risk_flags", ["Recent delay trend"]),
    }
