from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

from langgraph.graph import END, START, StateGraph

from app.agents import triage, supplier_data, performance, shipment, inventory, rag, risk_classification, investigation, action, validator, response
from app.graph.state import AgentState


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
    result = state.get("validation_result", "PENDING")
    if result == "RETRY":
        return "rag"
    if result == "BLOCK":
        return "response"
    return "END"


def run_workflow(user_query: str, supplier_id: str | None = None, purchase_order_id: str | None = None, product_id: str | None = None) -> Dict[str, Any]:
    state = _empty_state(user_query)
    state["intent"] = triage.run(state, supplier_id=supplier_id, purchase_order_id=purchase_order_id, product_id=product_id)
    state["supplier_data"] = supplier_data.run(state)
    state["supplier_performance"] = performance.run(state)
    state["shipment_data"] = shipment.run(state)
    state["inventory_data"] = inventory.run(state)
    state["retrieved_documents"] = rag.run(state)
    state["risk_classification"] = risk_classification.run(state)
    state["investigation_result"] = investigation.run(state)
    state["proposal"] = action.run(state)
    state["validation_result"] = validator.run(state)

    if state["risk_classification"].get("risk_class") == "HIGH":
        state["human_approval"] = {"required": True, "decision": "PENDING"}
        state["final_response"] = response.run(state)
    else:
        state["final_response"] = response.run(state)

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
        "final_response": state["final_response"],
        "errors": state["errors"],
    }


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("triage", lambda state: {**state, "intent": triage.run(state, supplier_id=None, purchase_order_id=None, product_id=None)})
    workflow.add_node("supplier_data", lambda state: {**state, "supplier_data": supplier_data.run(state)})
    workflow.add_node("performance", lambda state: {**state, "supplier_performance": performance.run(state)})
    workflow.add_node("shipment", lambda state: {**state, "shipment_data": shipment.run(state)})
    workflow.add_node("inventory", lambda state: {**state, "inventory_data": inventory.run(state)})
    workflow.add_node("rag", lambda state: {**state, "retrieved_documents": rag.run(state)})
    workflow.add_node("risk_classification", lambda state: {**state, "risk_classification": risk_classification.run(state)})
    workflow.add_node("investigation", lambda state: {**state, "investigation_result": investigation.run(state)})
    workflow.add_node("human_review", lambda state: {**state, "human_approval": {"required": True, "decision": "PENDING"}})
    workflow.add_node("action", lambda state: {**state, "proposal": action.run(state)})
    workflow.add_node("validation", lambda state: {**state, "validation_result": validator.run(state)})
    workflow.add_node("response", lambda state: {**state, "final_response": response.run(state)})

    workflow.add_edge(START, "triage")
    workflow.add_edge("triage", "supplier_data")
    workflow.add_edge("supplier_data", "performance")
    workflow.add_edge("performance", "shipment")
    workflow.add_edge("shipment", "inventory")
    workflow.add_edge("inventory", "rag")
    workflow.add_edge("rag", "risk_classification")
    workflow.add_edge("risk_classification", "investigation")
    workflow.add_conditional_edges("investigation", route_after_risk, {"human_review": "human_review", "response": "response"})
    workflow.add_edge("human_review", "action")
    workflow.add_edge("action", "validation")
    workflow.add_conditional_edges("validation", route_after_validation, {"rag": "rag", "response": "response", "END": END})
    workflow.add_edge("response", END)
    return workflow
