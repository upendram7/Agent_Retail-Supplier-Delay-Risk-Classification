from __future__ import annotations

import uuid
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from app.agents import triage, supplier_data, performance, shipment, inventory, rag, risk_classification, investigation, action, validator, response
from app.guardrails import validate_supplier_risk_request, validate_workflow_output
from app.graph.state import AgentState
from app.services.data_service import get_purchase_order


def _empty_state(user_query: str, session_id: str | None = None) -> AgentState:
    return {
        "session_id": session_id or f"session-{uuid.uuid4().hex[:8]}",
        "workflow_id": f"wf-{uuid.uuid4().hex[:8]}",
        "user_query": user_query,
        "intent": {},
        "supplier_data": {},
        "purchase_order_data": {},
        "shipment_data": {},
        "inventory_data": {},
        "supplier_performance": {},
        "retrieved_documents": [],
        "investigation_result": {},
        "risk_classification": {},
        "validation_result": "PENDING",
        "human_approval": {},
        "final_response": "",
        "errors": [],
        "proposal": {},
    }


def route_after_risk(state: AgentState) -> str:
    classification = state.get("risk_classification", {})
    risk = classification.get("risk_class", "MEDIUM")
    if risk == "HIGH":
        return "human_review"
    return "response"


def route_after_validation(state: AgentState) -> str:
    return "response"


def _guarded_triage(state: AgentState) -> AgentState:
    entities = validate_supplier_risk_request(state["user_query"])
    return {
        **state,
        "intent": triage.run(state, **entities),
        "purchase_order_data": get_purchase_order(entities["purchase_order_id"]),
    }


def _propose_action(state: AgentState) -> AgentState:
    approval = (
        {"required": True, "decision": "PENDING"}
        if state.get("risk_classification", {}).get("risk_class") == "HIGH"
        else {"required": False, "decision": "NOT_REQUIRED"}
    )
    return {**state, "proposal": action.run(state), "human_approval": approval}


def _guarded_response(state: AgentState) -> AgentState:
    validate_workflow_output(state["risk_classification"], state["proposal"])
    return {**state, "final_response": response.run(state)}


def _validate_result(state: AgentState) -> AgentState:
    result = validator.run(state)
    errors = state.get("errors", [])
    if result == "BLOCK":
        errors = [
            *errors,
            "Validation blocked the result because required policy evidence or classification data is unavailable.",
        ]
    return {**state, "validation_result": result, "errors": errors}


def run_workflow(user_query: str, supplier_id: str | None = None, purchase_order_id: str | None = None, product_id: str | None = None) -> Dict[str, Any]:
    entities = validate_supplier_risk_request(
        user_query, supplier_id=supplier_id, purchase_order_id=purchase_order_id, product_id=product_id
    )
    state = _empty_state(user_query)
    state["intent"] = triage.run(state, **entities)
    state["purchase_order_data"] = get_purchase_order(entities["purchase_order_id"])
    state["supplier_data"] = supplier_data.run(state)
    state["supplier_performance"] = performance.run(state)
    state["shipment_data"] = shipment.run(state)
    state["inventory_data"] = inventory.run(state)
    state["retrieved_documents"] = rag.run(state)
    state["risk_classification"] = risk_classification.run(state)
    state["investigation_result"] = investigation.run(state)
    state["proposal"] = action.run(state)
    if state["risk_classification"].get("risk_class") == "HIGH":
        state["human_approval"] = {"required": True, "decision": "PENDING"}
    else:
        state["human_approval"] = {"required": False, "decision": "NOT_REQUIRED"}
    state["validation_result"] = validator.run(state)
    if state["validation_result"] == "BLOCK":
        state["errors"].append("Validation blocked the result because required policy evidence or classification data is unavailable.")
    state["final_response"] = response.run(state)
    validate_workflow_output(state["risk_classification"], state["proposal"])

    return {
        "session_id": state["session_id"],
        "workflow_id": state["workflow_id"],
        "query": state["user_query"],
        "intent": state["intent"],
        "supplier_data": state["supplier_data"],
        "purchase_order_data": state.get("purchase_order_data", {}),
        "shipment_data": state["shipment_data"],
        "inventory_data": state["inventory_data"],
        "supplier_performance": state["supplier_performance"],
        "retrieved_documents": state["retrieved_documents"],
        "risk_classification": state["risk_classification"],
        "investigation_result": state["investigation_result"],
        "validation_result": state["validation_result"],
        "human_approval": state["human_approval"],
        "proposal": state["proposal"],
        "guardrails": {
            "scope": "supplier_delay_risk_classification",
            "data_access": "READ_ONLY",
            "file_access": "READ_ONLY",
            "allowed_tools": [],
            "action_execution": "DISABLED",
            "approval_state_persisted": False,
            "untrusted_content_is_data": True,
        },
        "final_response": state["final_response"],
        "errors": state["errors"],
    }


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("triage", _guarded_triage)
    workflow.add_node("supplier_lookup", lambda state: {**state, "supplier_data": supplier_data.run(state)})
    workflow.add_node("performance_analysis", lambda state: {**state, "supplier_performance": performance.run(state)})
    workflow.add_node("shipment_review", lambda state: {**state, "shipment_data": shipment.run(state)})
    workflow.add_node("inventory_review", lambda state: {**state, "inventory_data": inventory.run(state)})
    workflow.add_node("policy_retrieval", lambda state: {**state, "retrieved_documents": rag.run(state)})
    workflow.add_node("risk_scoring", lambda state: {**state, "risk_classification": risk_classification.run(state)})
    workflow.add_node("investigation", lambda state: {**state, "investigation_result": investigation.run(state)})
    workflow.add_node("human_review", lambda state: {**state, "human_approval": {"required": True, "decision": "PENDING"}})
    workflow.add_node("action", _propose_action)
    workflow.add_node("validation", _validate_result)
    workflow.add_node("response", _guarded_response)

    workflow.add_edge(START, "triage")
    workflow.add_edge("triage", "supplier_lookup")
    workflow.add_edge("supplier_lookup", "performance_analysis")
    workflow.add_edge("performance_analysis", "shipment_review")
    workflow.add_edge("shipment_review", "inventory_review")
    workflow.add_edge("inventory_review", "policy_retrieval")
    workflow.add_edge("policy_retrieval", "risk_scoring")
    workflow.add_edge("risk_scoring", "investigation")
    workflow.add_conditional_edges("investigation", route_after_risk, {"human_review": "human_review", "response": "action"})
    workflow.add_edge("human_review", "action")
    workflow.add_edge("action", "validation")
    workflow.add_conditional_edges("validation", route_after_validation, {"response": "response"})
    workflow.add_edge("response", END)
    return workflow
