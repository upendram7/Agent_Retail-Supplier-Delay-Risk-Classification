from __future__ import annotations

from typing import Any, Dict

from app.models.schemas import IntentResult
from app.services.data_service import get_demo_case, get_supplier, get_purchase_order


def run(state: Dict[str, Any], supplier_id: str | None = None, purchase_order_id: str | None = None, product_id: str | None = None) -> Dict[str, Any]:
    query = state.get("user_query", "")
    if not supplier_id:
        supplier_id = "SUP001" if "SUP001" in query.upper() else None
    if not purchase_order_id:
        purchase_order_id = "PO10025" if "PO10025" in query.upper() else None
    if not product_id:
        product_id = "PROD100"

    intent = IntentResult(
        intent="supplier_delay_risk_classification",
        category="supplier_risk",
        priority="HIGH",
        entities={
            "supplier_id": supplier_id,
            "purchase_order_id": purchase_order_id,
            "product_id": product_id,
        },
        missing_information=[],
        confidence=0.94,
        recommended_route="supplier_risk_workflow",
    )

    if not supplier_id:
        intent.missing_information.append("supplier_id")
    if not purchase_order_id:
        intent.missing_information.append("purchase_order_id")
    return intent.model_dump()
