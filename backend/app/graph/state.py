from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict


class AgentState(TypedDict):
    session_id: str
    workflow_id: str
    user_query: str
    intent: Dict[str, Any]
    supplier_data: Dict[str, Any]
    purchase_order_data: Dict[str, Any]
    shipment_data: Dict[str, Any]
    inventory_data: Dict[str, Any]
    supplier_performance: Dict[str, Any]
    retrieved_documents: List[Dict[str, Any]]
    investigation_result: Dict[str, Any]
    risk_classification: Dict[str, Any]
    validation_result: str
    human_approval: Dict[str, Any]
    final_response: str
    errors: List[str]
    proposal: Dict[str, Any]
