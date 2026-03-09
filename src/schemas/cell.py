"""
NEXUS MVP — Cell Schema
========================
Core data structure for governance pipeline transit.

The Cell is the atomic unit that flows through the NEXUS operator chain:
    Α (intake) → Δ (risk evaluation) → Ω (decision gate)

Each operator reads from and writes to the Cell. The Cell accumulates
state as it transits — Α initializes, Δ classifies, Ω decides.

Design Principles:
    - Immutable IDs (cell_id, claim_id, evidence_id assigned once)
    - Append-only semantics (operators add data, never remove)
    - Uncertainty is ALWAYS non-binding in MVP (mode="proxy", binding=False)
    - risk_score is None until Δ populates it
    - status is "pending" until Ω resolves it

Specification Reference:
    Governance Decision Specification — Α Section
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import uuid4
from datetime import datetime, timezone


class Proposal(BaseModel):
    action: str
    reasoning: str


class Claim(BaseModel):
    claim_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    content: str


class Uncertainty(BaseModel):
    total: float = Field(ge=0.0, le=1.0)
    mode: str = "proxy"
    binding: bool = False
    note: str = "Observational only - does not influence Ω decisions"


class Cell(BaseModel):
    cell_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"
    proposal: Proposal
    claims: List[Claim]
    evidence: List[Evidence]
    uncertainty: Uncertainty
    risk_score: Optional[float] = None  # Populated by Δ, not Α
    domain_payload: dict  # FinTechPayload.model_dump()
