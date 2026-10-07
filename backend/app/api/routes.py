from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.graph.workflow import run_workflow
from app.models.schemas import ApprovalPayload, ChatRequest, WorkflowState
from app.services.data_service import get_demo_case, get_purchase_order, get_supplier, get_supplier_list

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "retail-supplier-delay-risk-classification"}


@router.get("/metrics")
def metrics() -> Dict[str, Any]:
    return {"detail": "Use /api/observability/overview or the /api/metrics/* endpoints."}


@router.post("/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    workflow = run_workflow(
        user_query=payload.user_query,
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        product_id=payload.product_id,
    )
    return workflow


@router.post("/agent/run")
def agent_run(payload: ChatRequest) -> Dict[str, Any]:
    return run_workflow(
        user_query=payload.user_query,
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        product_id=payload.product_id,
    )


@router.post("/risk/classify")
def classify_risk(payload: ChatRequest) -> Dict[str, Any]:
    return run_workflow(
        user_query=payload.user_query,
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        product_id=payload.product_id,
    )


@router.get("/suppliers/{supplier_id}")
def supplier_detail(supplier_id: str) -> Dict[str, Any]:
    supplier = get_supplier(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("/purchase-orders/{purchase_order_id}")
def purchase_order_detail(purchase_order_id: str) -> Dict[str, Any]:
    po = get_purchase_order(purchase_order_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    raise HTTPException(status_code=404, detail="Session state is not persisted.")


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> Dict[str, Any]:
    raise HTTPException(status_code=404, detail="Workflow state is not persisted.")


@router.post("/approval/{workflow_id}")
def approval(workflow_id: str, payload: ApprovalPayload) -> Dict[str, Any]:
    raise HTTPException(
        status_code=409,
        detail="Approval cannot be applied because workflow state is not persisted. No action has been executed.",
    )


@router.get("/demo")
def demo_case() -> Dict[str, Any]:
    return get_demo_case()


@router.get("/suppliers")
def suppliers() -> Dict[str, Any]:
    return {
        "request_id": context.get("request_id"),
        "trace_id": context.get("trace_id"),
        "conversation_id": context.get("session_id"),
        "user_id": None,"suppliers": get_supplier_list()}
