from __future__ import annotations

from app.guardrails import deny_action_tool


def create_supplier_escalation(supplier_id: str, reason: str) -> None:
    deny_action_tool("create_supplier_escalation")


def create_procurement_ticket(po_id: str, summary: str) -> None:
    deny_action_tool("create_procurement_ticket")


def request_supplier_confirmation(supplier_id: str, message: str) -> None:
    deny_action_tool("request_supplier_confirmation")


def flag_purchase_order(po_id: str) -> None:
    deny_action_tool("flag_purchase_order")
