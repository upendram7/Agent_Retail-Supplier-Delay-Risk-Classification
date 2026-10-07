from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
import json

from app.services.observability import store

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str) -> List[Dict[str, Any]]:
    file_path = DATA_DIR / filename
    with open(file_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


SUPPLIERS = _load_json("suppliers.json")
PURCHASE_ORDERS = _load_json("purchase_orders.json")
SHIPMENTS = _load_json("shipments.json")
INVENTORY = _load_json("inventory.json")
POLICIES = _load_json("policies.json")


def get_supplier(supplier_id: str) -> Dict[str, Any]:
    return store.record_tool_call(
        "get_supplier",
        lambda: next((supplier for supplier in SUPPLIERS if supplier["supplier_id"] == supplier_id), {}),
        agent_name="supplier_data",
        input_summary={"supplier_id": supplier_id},
    )


def get_supplier_performance(supplier_id: str) -> Dict[str, Any]:
    return store.record_tool_call(
        "get_supplier_performance",
        lambda: next((item for item in _load_json("supplier_performance.json") if item["supplier_id"] == supplier_id), {}),
        agent_name="performance",
        input_summary={"supplier_id": supplier_id},
    )


def get_purchase_order(purchase_order_id: str) -> Dict[str, Any]:
    return store.record_tool_call(
        "get_purchase_order",
        lambda: next((po for po in PURCHASE_ORDERS if po["purchase_order_id"] == purchase_order_id), {}),
        agent_name="supplier_data",
        input_summary={"purchase_order_id": purchase_order_id},
    )


def get_shipment(purchase_order_id: str) -> Dict[str, Any]:
    return store.record_tool_call(
        "get_shipment",
        lambda: next((shipment for shipment in SHIPMENTS if shipment["purchase_order_id"] == purchase_order_id), {}),
        agent_name="shipment",
        input_summary={"purchase_order_id": purchase_order_id},
    )


def get_inventory(product_id: str) -> Dict[str, Any]:
    return store.record_tool_call(
        "get_inventory",
        lambda: next((entry for entry in INVENTORY if entry["product_id"] == product_id), {}),
        agent_name="inventory",
        input_summary={"product_id": product_id},
    )


def get_policy_documents() -> List[Dict[str, Any]]:
    return store.record_tool_call(
        "get_policy_documents", lambda: POLICIES, agent_name="rag",
        input_summary={"document_count": len(POLICIES)},
    )


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
