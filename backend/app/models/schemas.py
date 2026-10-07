from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class TriageInput(BaseModel):
    user_query: str
    supplier_id: Optional[str] = None
    purchase_order_id: Optional[str] = None
    product_id: Optional[str] = None


class IntentResult(BaseModel):
    intent: str = "supplier_delay_risk_classification"
    category: str = "supplier_risk"
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
    entities: Dict[str, Optional[str]] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    recommended_route: str = "supplier_risk_workflow"


class SupplierData(BaseModel):
    supplier_id: str
    supplier_name: str
    country: str
    supplier_category: str
    lead_time_days: int
    on_time_delivery_rate: float
    active: bool = True
    risk_flags: List[str] = Field(default_factory=list)


class PurchaseOrderData(BaseModel):
    purchase_order_id: str
    supplier_id: str
    order_date: str
    expected_delivery_date: str
    quantity_ordered: int
    quantity_received: int
    status: str
    open_quantity: int


class ShipmentData(BaseModel):
    purchase_order_id: str
    supplier_id: str
    current_status: str
    carrier_status: str
    expected_delivery_date: str
    actual_shipment_date: Optional[str] = None
    transit_time_days: Optional[int] = None
    delay_indicators: List[str] = Field(default_factory=list)
    estimated_delay_days: int = 0
    risk_signal: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"


class InventoryData(BaseModel):
    product_id: str
    current_inventory: int
    daily_demand: int
    days_of_supply: float
    safety_stock: int
    stockout_risk: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    business_impact: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"


class SupplierPerformance(BaseModel):
    supplier_id: str
    on_time_delivery_rate: float
    average_delay_days: float
    late_order_rate: float
    performance_trend: Literal["STABLE", "IMPROVING", "DETERIORATING"] = "STABLE"
    reliability_score: float
    risk_factors: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class RiskClassification(BaseModel):
    risk_class: Literal["LOW", "MEDIUM", "HIGH"]
    risk_score: float
    confidence: float
    key_risk_factors: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    recommended_action: str
    requires_human_review: bool = False


class InvestigationResult(BaseModel):
    issue_type: str = "SUPPLIER_DELAY_RISK"
    risk_class: str
    evidence: List[str] = Field(default_factory=list)
    policy_reference: List[str] = Field(default_factory=list)
    business_impact: str
    recommended_action: str
    confidence: float
    requires_human_review: bool = False


class ApprovalPayload(BaseModel):
    decision: Literal["APPROVE", "REJECT", "MODIFY"]
    notes: Optional[str] = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChatRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=2000)
    supplier_id: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    purchase_order_id: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    product_id: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WorkflowState(BaseModel):
    session_id: str
    workflow_id: str
    user_query: str
    intent: Dict[str, Any] = Field(default_factory=dict)
    supplier_data: Dict[str, Any] = Field(default_factory=dict)
    purchase_order_data: Dict[str, Any] = Field(default_factory=dict)
    shipment_data: Dict[str, Any] = Field(default_factory=dict)
    inventory_data: Dict[str, Any] = Field(default_factory=dict)
    supplier_performance: Dict[str, Any] = Field(default_factory=dict)
    retrieved_documents: List[Dict[str, Any]] = Field(default_factory=list)
    investigation_result: Dict[str, Any] = Field(default_factory=dict)
    risk_classification: Dict[str, Any] = Field(default_factory=dict)
    validation_result: str = "PENDING"
    human_approval: Dict[str, Any] = Field(default_factory=dict)
    final_response: str = ""
    errors: List[str] = Field(default_factory=list)
