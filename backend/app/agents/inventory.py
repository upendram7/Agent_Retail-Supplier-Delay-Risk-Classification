from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_inventory


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    product_id = intent.get("entities", {}).get("product_id", "PROD100")
    inventory = get_inventory(product_id)
    if not inventory:
        raise ValueError(f"Inventory data not found for product: {product_id}")
    return inventory
