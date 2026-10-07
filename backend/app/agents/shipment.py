from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_shipment


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    po_id = intent.get("entities", {}).get("purchase_order_id", "PO10025")
    shipment = get_shipment(po_id)
    if not shipment:
        raise ValueError(f"Shipment data not found for purchase order: {po_id}")
    return shipment
