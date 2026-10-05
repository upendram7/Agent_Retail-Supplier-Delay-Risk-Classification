from __future__ import annotations

from typing import Any, Dict


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "routing", "next": "supplier_risk_workflow"}
