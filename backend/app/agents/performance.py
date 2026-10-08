from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_supplier_performance


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    supplier_id = intent.get("entities", {}).get("supplier_id", "SUP001")
    performance = get_supplier_performance(supplier_id)
    if not performance:
        performance = {
            "supplier_id": supplier_id,
            "on_time_delivery_rate": 0.76,
            "average_delay_days": 4.5,
            "late_order_rate": 0.22,
            "performance_trend": "DETERIORATING",
            "reliability_score": 0.68,
            "risk_factors": ["Increasing delivery delays", "Lead-time variability rising"],
            "confidence": 0.9,
        }
    return performance
