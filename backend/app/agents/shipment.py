from __future__ import annotations

from typing import Any, Dict

from app.services.data_service import get_demo_case, get_purchase_order, get_shipment


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    intent = state.get("intent", {})
    po_id = intent.get("entities", {}).get("purchase_order_id", "PO10025")
    shipment = get_shipment(po_id)
    if not shipment:
        shipment = {
            "purchase_order_id": po_id,
            "supplier_id": "SUP001",
            "current_status": "IN_TRANSIT",
            "carrier_status": "DELAYED",
            "expected_delivery_date": "2026-10-15",
            "actual_shipment_date": "2026-10-09",
            "transit_time_days": 9,
            "delay_indicators": ["Shipment dispatched later than supplier commitment", "Transit time exceeds historical average"],
            "estimated_delay_days": 4,
            "risk_signal": "HIGH",
        }
    return shipment
