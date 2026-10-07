from __future__ import annotations

import logging
import re
import hashlib
from typing import Any, Dict, NoReturn, Optional

from fastapi import HTTPException

from app.services.observability import current_trace_context, store
from app.services.data_service import get_purchase_order, get_supplier

logger = logging.getLogger(__name__)

DISABLED_ACTION_TOOLS = frozenset(
    {
        "create_supplier_escalation",
        "create_procurement_ticket",
        "request_supplier_confirmation",
        "flag_purchase_order",
    }
)

_ID_PATTERNS = {
    "supplier_id": re.compile(r"\bSUP\d+\b", re.IGNORECASE),
    "purchase_order_id": re.compile(r"\bPO\d+\b", re.IGNORECASE),
    "product_id": re.compile(r"\bPROD\d+\b", re.IGNORECASE),
}
_SCOPE_PATTERN = re.compile(
    r"\b(supplier|delay|risk|shipment|purchase order|procurement|delivery)\b",
    re.IGNORECASE,
)
_INJECTION_PATTERN = re.compile(
    r"\b(ignore|disregard|override|bypass)\b.{0,40}\b(instructions?|guardrails?|rules?|policy|system prompt)\b"
    r"|\b(reveal|show|print|expose)\b.{0,30}\b(system prompt|developer prompt|secret|credential|api key|password)\b"
    r"|\b(act as|pretend to be)\b.{0,30}\b(system|developer|administrator|unrestricted)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_ACTION_PATTERN = re.compile(
    r"\b(send|email|notify|delete|remove|modify|update|overwrite|upload|download|execute|"
    r"transfer|submit)\b"
    r"|\b(create|open)\s+(?:a\s+)?(?:supplier escalation|procurement ticket|purchase order|file|record)\b",
    re.IGNORECASE,
)


def _reject(code: str, detail: str, status_code: int = 422) -> None:
    logger.warning("Guardrail rejected request: %s", code)
    context = current_trace_context()
    store.record_guardrail(
        guardrail_name="supplier_risk_input",
        guardrail_type="input",
        decision="BLOCK",
        reason=code,
        request_id=context.get("request_id"),
        trace_id=context.get("trace_id"),
        session_id=context.get("session_id"),
        severity="WARNING",
        action_taken="rejected",
        input_hash=context.get("input_hash"),
    )
    store.record_security(
        "prompt_injection_attempt" if code == "instruction_override" else "request_validation",
        "BLOCKED",
        context.get("endpoint"),
        context.get("request_id"),
        context.get("trace_id"),
        "WARNING",
        {"reason_code": code},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def authorize_tool(tool_name: str) -> None:
    if tool_name in DISABLED_ACTION_TOOLS:
        raise PermissionError(f"Tool '{tool_name}' is disabled; no operational actions are permitted.")
    raise PermissionError(f"Tool '{tool_name}' is not on the approved tool allowlist.")


def deny_action_tool(tool_name: str) -> NoReturn:
    if tool_name not in DISABLED_ACTION_TOOLS:
        raise PermissionError(f"Tool '{tool_name}' is not an approved action tool.")
    context = current_trace_context()
    store.record_guardrail(
        guardrail_name="tool_authorization",
        guardrail_type="tool",
        decision="BLOCK",
        reason="operational_tools_disabled",
        request_id=context.get("request_id"),
        trace_id=context.get("trace_id"),
        session_id=context.get("session_id"),
        severity="WARNING",
        action_taken="tool_blocked",
    )
    store.record_security(
        "blocked_tool_call", "BLOCKED", context.get("endpoint"),
        context.get("request_id"), context.get("trace_id"), "WARNING",
        {"tool_name": tool_name},
    )
    raise PermissionError(f"Tool '{tool_name}' is disabled; no operational actions are permitted.")


def _resolve_identifier(
    field: str, supplied: Optional[str], query: str
) -> Optional[str]:
    found = {value.upper() for value in _ID_PATTERNS[field].findall(query)}
    if len(found) > 1:
        _reject("ambiguous_identifier", f"Provide only one {field}.")
    from_query = next(iter(found), None)
    normalized = supplied.upper() if supplied else None
    if normalized and from_query and normalized != from_query:
        _reject("conflicting_identifier", f"{field} conflicts with the identifier in user_query.")
    return normalized or from_query


def validate_supplier_risk_request(
    user_query: str,
    supplier_id: Optional[str] = None,
    purchase_order_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Constrain a request to read-only supplier delay risk analysis."""
    input_hash = hashlib.sha256(user_query.encode("utf-8")).hexdigest()
    context = current_trace_context()
    if context:
        context["input_hash"] = input_hash
    if not user_query.strip() or len(user_query) > 2000:
        _reject("invalid_query", "user_query must contain 1 to 2000 characters.")
    if any(ord(character) < 32 and character not in "\r\n\t" for character in user_query):
        _reject("invalid_query", "user_query contains unsupported control characters.")
    if _INJECTION_PATTERN.search(user_query):
        _reject(
            "instruction_override",
            "Requests to override instructions or disclose protected information are not supported.",
            status_code=400,
        )
    if _UNSUPPORTED_ACTION_PATTERN.search(user_query):
        _reject(
            "unsupported_action",
            "This service only classifies supplier delay risk; it cannot perform operational actions.",
        )
    if not _SCOPE_PATTERN.search(user_query):
        _reject(
            "out_of_scope",
            "This service only supports supplier delay risk classification.",
        )

    resolved_supplier_id = _resolve_identifier("supplier_id", supplier_id, user_query)
    resolved_po_id = _resolve_identifier("purchase_order_id", purchase_order_id, user_query)
    resolved_product_id = _resolve_identifier("product_id", product_id, user_query)

    if not resolved_po_id:
        _reject("missing_purchase_order", "A purchase_order_id is required for risk classification.")
    if not resolved_supplier_id:
        order = get_purchase_order(resolved_po_id)
        if not order:
            _reject("unknown_purchase_order", "Purchase order not found.")
        resolved_supplier_id = order["supplier_id"]

    supplier = get_supplier(resolved_supplier_id)
    if not supplier:
        _reject("unknown_supplier", "Supplier not found.")
    order = get_purchase_order(resolved_po_id)
    if not order:
        _reject("unknown_purchase_order", "Purchase order not found.")
    if order["supplier_id"] != resolved_supplier_id:
        _reject("supplier_order_mismatch", "The purchase order does not belong to the specified supplier.")

    expected_product_id = order.get("product_id")
    if resolved_product_id and resolved_product_id != expected_product_id:
        _reject("product_order_mismatch", "The product does not match the specified purchase order.")

    store.record_guardrail(
        guardrail_name="supplier_risk_input",
        guardrail_type="input",
        decision="ALLOW",
        reason="scope_and_identifiers_valid",
        severity="INFO",
        action_taken="continued",
        input_hash=input_hash,
    )
    return {
        "supplier_id": resolved_supplier_id,
        "purchase_order_id": resolved_po_id,
        "product_id": expected_product_id,
    }


def validate_workflow_output(risk_classification: Dict[str, Any], proposal: Dict[str, Any]) -> None:
    """Reject malformed or success-shaped output for actions that were not executed."""
    risk_class = risk_classification.get("risk_class")
    if risk_class not in {"LOW", "MEDIUM", "HIGH"}:
        raise RuntimeError("Guardrail blocked invalid risk classification output.")
    score = risk_classification.get("risk_score")
    confidence = risk_classification.get("confidence")
    if not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise RuntimeError("Guardrail blocked invalid risk score output.")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise RuntimeError("Guardrail blocked invalid confidence output.")
    expected_status = "PENDING_APPROVAL" if risk_class == "HIGH" else "NOT_EXECUTED"
    if proposal.get("status") != expected_status:
        raise RuntimeError("Guardrail blocked an action status that could imply execution.")
