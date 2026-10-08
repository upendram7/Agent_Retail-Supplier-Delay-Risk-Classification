from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_inventory


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    product_id = intent.get("entities", {}).get("product_id", "PROD100")
    inventory = get_inventory(product_id)
    if not inventory:
        inventory = {
            "product_id": product_id,
            "current_inventory": 120,
            "daily_demand": 35,
            "days_of_supply": 3.4,
            "safety_stock": 150,
            "stockout_risk": "HIGH",
            "business_impact": "HIGH",
        }
    return inventory
