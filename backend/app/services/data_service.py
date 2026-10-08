from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str) -> List[Dict[str, Any]]:
    file_path = DATA_DIR / filename
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


SUPPLIERS = _load_json("suppliers.json")
PURCHASE_ORDERS = _load_json("purchase_orders.json")
SHIPMENTS = _load_json("shipments.json")
INVENTORY = _load_json("inventory.json")
POLICIES = _load_json("policies.json")


def get_supplier(supplier_id: str) -> Dict[str, Any]:
    for supplier in SUPPLIERS:
        if supplier["supplier_id"] == supplier_id:
            return supplier
    return {}


def get_supplier_performance(supplier_id: str) -> Dict[str, Any]:
    for item in _load_json("supplier_performance.json"):
        if item["supplier_id"] == supplier_id:
            return item
    return {}


def get_purchase_order(purchase_order_id: str) -> Dict[str, Any]:
    for po in PURCHASE_ORDERS:
        if po["purchase_order_id"] == purchase_order_id:
            return po
    return {}


def get_shipment(purchase_order_id: str) -> Dict[str, Any]:
    for shipment in SHIPMENTS:
        if shipment["purchase_order_id"] == purchase_order_id:
            return shipment
    return {}


def get_inventory(product_id: str) -> Dict[str, Any]:
    for entry in INVENTORY:
        if entry["product_id"] == product_id:
            return entry
    return {}


def get_policy_documents() -> List[Dict[str, Any]]:
    return POLICIES


def get_demo_case(supplier_id: str = "SUP001", po_id: str = "PO10025") -> Dict[str, Any]:
    supplier = get_supplier(supplier_id)
    po = get_purchase_order(po_id)
    shipment = get_shipment(po_id)
    inventory = get_inventory(po.get("product_id", "PROD100"))
    performance = get_supplier_performance(supplier_id)
    return {
        "supplier": supplier,
        "purchase_order": po,
        "shipment": shipment,
        "inventory": inventory,
        "performance": performance,
    }


def get_supplier_list() -> List[Dict[str, Any]]:
    return SUPPLIERS


def get_all_purchase_orders() -> List[Dict[str, Any]]:
    return PURCHASE_ORDERS
