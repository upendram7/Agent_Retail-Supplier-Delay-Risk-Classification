from __future__ import annotations

from typing import Any, Dict


def create_supplier_escalation(supplier_id: str, reason: str) -> Dict[str, Any]:
    return {"tool": "create_supplier_escalation", "supplier_id": supplier_id, "status": "success", "reason": reason}


def create_procurement_ticket(po_id: str, summary: str) -> Dict[str, Any]:
    return {"tool": "create_procurement_ticket", "purchase_order_id": po_id, "status": "success", "summary": summary}


def request_supplier_confirmation(supplier_id: str, message: str) -> Dict[str, Any]:
    return {"tool": "request_supplier_confirmation", "supplier_id": supplier_id, "status": "success", "message": message}


def flag_purchase_order(po_id: str) -> Dict[str, Any]:
    return {"tool": "flag_purchase_order", "purchase_order_id": po_id, "status": "success"}
