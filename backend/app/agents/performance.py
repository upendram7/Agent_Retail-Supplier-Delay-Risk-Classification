from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_supplier_performance


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    supplier_id = intent.get("entities", {}).get("supplier_id", "SUP001")
    performance = get_supplier_performance(supplier_id)
    if not performance:
        raise ValueError(f"Supplier performance data not found: {supplier_id}")
    return performance
