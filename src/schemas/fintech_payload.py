"""
NEXUS MVP — FinTech Domain Payload Schema
==========================================
Domain-specific regulatory context for financial technology compliance.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class IntentType(str, Enum):
    CREDIT_DECISION = "credit_decision"
    AML_SCREENING = "aml_screening"
    FAIR_LENDING_CHECK = "fair_lending_check"
    RISK_ASSESSMENT = "risk_assessment"
    REGULATORY_REPORTING = "regulatory_reporting"
    CUSTOMER_ONBOARDING = "customer_onboarding"
    UNKNOWN = "unknown"


class RegulatoryFramework(str, Enum):
    ECOA = "ECOA"
    FCRA = "FCRA"
    BSA_AML = "BSA_AML"
    HMDA = "HMDA"
    CRA = "CRA"
    EU_AI_ACT = "EU_AI_ACT"
    GDPR = "GDPR"
    UNKNOWN = "UNKNOWN"


class PEPStatus(str, Enum):
    NONE = "none"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class EntityType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    TRANSACTION = "transaction"


class RiskSubject(BaseModel):
    entity_type: str = EntityType.INDIVIDUAL.value
    protected_class_data_present: bool = False
    high_risk_jurisdiction: bool = False
    pep_status: str = PEPStatus.NONE.value


class FinTechPayload(BaseModel):
    intent_type: Optional[str] = None  # Populated by Δ
    regulatory_framework: str = RegulatoryFramework.UNKNOWN.value
    risk_subject: RiskSubject = Field(default_factory=RiskSubject)
    jurisdiction: str = "US"  # ISO 3166-1 alpha-2
    explainability_required: bool = False
    human_oversight_required: bool = False
    adverse_action_potential: bool = False
    regulatory_article_references: List[str] = []
    compliance_metadata: dict = {}
