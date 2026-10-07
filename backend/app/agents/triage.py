from __future__ import annotations

from typing import Any, Dict

from app.models.schemas import IntentResult


def run(state: Dict[str, Any], supplier_id: str | None = None, purchase_order_id: str | None = None, product_id: str | None = None) -> Dict[str, Any]:
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
