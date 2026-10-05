EVALUATION_CASES = [
    {
        "id": "case-01",
        "scenario": "normal",
        "supplier_id": "SUP002",
        "purchase_order_id": "PO10026",
        "expected_risk": "LOW",
        "notes": "On-time supplier with healthy inventory and low delay risk.",
    },
    {
        "id": "case-02",
        "scenario": "medium",
        "supplier_id": "SUP001",
        "purchase_order_id": "PO10025",
        "expected_risk": "HIGH",
        "notes": "Supplier is late, service impact is severe, and inventory coverage is low.",
    },
    {
        "id": "case-03",
        "scenario": "adversarial",
        "supplier_id": "SUP003",
        "purchase_order_id": "PO10027",
        "expected_risk": "HIGH",
        "notes": "Customs and port delay with stockout risk.",
    },
]
