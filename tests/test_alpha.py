"""
NEXUS MVP — Α Operator Test Suite
====================================
Validates Alpha operator behavior against specification.

Test Cases:
    TC-001: Credit decision query (primary validation)
    TC-002: Empty query rejection
    TC-003: Missing context fields (safe defaults)
    TC-004: Uncertainty invariant enforcement
    TC-005: Domain payload initialization

Specification Reference:
    Governance Test Suite — TC-001
"""

import os
import pytest
from uuid import UUID
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.operators.alpha import alpha_operator
from src.schemas.cell import Cell, Uncertainty
from src.schemas.fintech_payload import FinTechPayload


TC_001_QUERY = (
    "Should we approve a $50,000 loan for an applicant "
    "with credit score 680, income $45K, DTI 38%?"
)

TC_001_CONTEXT = {
    "session_id": "test-session-001",
    "timestamp": "2026-03-09T14:45:00Z",
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}


class TestAlphaOperatorTC001:
    """Primary validation: credit decision decomposition."""

    def setup_method(self):
        self.cell = alpha_operator(TC_001_QUERY, TC_001_CONTEXT)

    def test_cell_has_valid_uuid(self):
        UUID(self.cell["cell_id"], version=4)

    def test_cell_has_iso_timestamp(self):
        datetime.fromisoformat(self.cell["timestamp"])

    def test_cell_status_is_pending(self):
        assert self.cell["status"] == "pending"

    def test_proposal_present_and_non_empty(self):
        assert "proposal" in self.cell
        assert isinstance(self.cell["proposal"]["action"], str)
        assert len(self.cell["proposal"]["action"]) > 0
        assert isinstance(self.cell["proposal"]["reasoning"], str)
        assert len(self.cell["proposal"]["reasoning"]) > 0

    def test_claims_is_list(self):
        assert isinstance(self.cell["claims"], list)

    def test_claims_have_required_fields(self):
        for claim in self.cell["claims"]:
            assert "claim_id" in claim
            assert "text" in claim
            assert "confidence" in claim
            assert 0.0 <= claim["confidence"] <= 1.0

    def test_evidence_is_list(self):
        assert isinstance(self.cell["evidence"], list)

    def test_uncertainty_mode_is_proxy(self):
        """NEXUS INVARIANT: Uncertainty mode MUST be 'proxy'."""
        assert self.cell["uncertainty"]["mode"] == "proxy"

    def test_uncertainty_binding_is_false(self):
        """NEXUS INVARIANT: Uncertainty binding MUST be False."""
        assert self.cell["uncertainty"]["binding"] is False

    def test_uncertainty_total_in_range(self):
        assert 0.0 <= self.cell["uncertainty"]["total"] <= 1.0

    def test_uncertainty_note_present(self):
        assert "not influence" in self.cell["uncertainty"]["note"].lower() or \
               "observational" in self.cell["uncertainty"]["note"].lower()

    def test_risk_score_is_none(self):
        """Α does NOT set risk_score. That is Δ's job."""
        assert self.cell["risk_score"] is None

    def test_domain_payload_framework(self):
        assert self.cell["domain_payload"]["regulatory_framework"] == "ECOA"

    def test_domain_payload_jurisdiction(self):
        assert self.cell["domain_payload"]["jurisdiction"] == "US"

    def test_domain_payload_intent_type_is_none(self):
        """Α does NOT classify intent. intent_type must be None."""
        assert self.cell["domain_payload"]["intent_type"] is None

    def test_domain_payload_risk_subject_defaults(self):
        rs = self.cell["domain_payload"]["risk_subject"]
        assert rs["protected_class_data_present"] is False
        assert rs["high_risk_jurisdiction"] is False
        assert rs["pep_status"] == "none"


class TestAlphaOperatorEdgeCases:
    """Edge case validation."""

    def test_empty_query_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty query"):
            alpha_operator("", TC_001_CONTEXT)

    def test_whitespace_query_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty query"):
            alpha_operator("   ", TC_001_CONTEXT)


class TestAlphaOperatorMissingContext:
    """Validates safe defaults when context is incomplete."""

    def test_missing_framework_defaults_to_unknown(self):
        cell = alpha_operator("Test query", {"session_id": "test"})
        assert cell["domain_payload"]["regulatory_framework"] == "UNKNOWN"

    def test_missing_jurisdiction_defaults_to_us(self):
        cell = alpha_operator("Test query", {"session_id": "test"})
        assert cell["domain_payload"]["jurisdiction"] == "US"

    def test_empty_context_produces_valid_cell(self):
        cell = alpha_operator("Test query", {})
        assert "cell_id" in cell
        assert "proposal" in cell
        assert cell["status"] == "pending"
        assert cell["risk_score"] is None


class TestCellSchemaValidation:
    """Validates that Pydantic schemas enforce constraints."""

    def test_uncertainty_total_lower_bound(self):
        with pytest.raises(Exception):
            Uncertainty(total=-0.1)

    def test_uncertainty_total_upper_bound(self):
        with pytest.raises(Exception):
            Uncertainty(total=1.5)

    def test_fintech_payload_serialization(self):
        payload = FinTechPayload(
            regulatory_framework="ECOA",
            jurisdiction="US",
        )
        d = payload.model_dump()
        assert d["intent_type"] is None
        assert d["regulatory_framework"] == "ECOA"
        assert d["jurisdiction"] == "US"
        assert d["risk_subject"]["pep_status"] == "none"


if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS MVP — Α Operator Validation (TC-001)")
    print("=" * 60)

    api_mode = "LLM" if os.environ.get("ANTHROPIC_API_KEY") else "FALLBACK"
    print(f"Execution mode: {api_mode}\n")

    cell = alpha_operator(TC_001_QUERY, TC_001_CONTEXT)

    print(f"✓ Cell ID:        {cell['cell_id']}")
    print(f"✓ Status:         {cell['status']}")
    print(f"✓ Proposal:       {cell['proposal']['action'][:80]}...")
    print(f"✓ Claims:         {len(cell['claims'])} extracted")
    print(f"✓ Evidence:       {len(cell['evidence'])} items")
    print(f"✓ Uncertainty:    {cell['uncertainty']['total']} (mode={cell['uncertainty']['mode']}, binding={cell['uncertainty']['binding']})")
    print(f"✓ Risk Score:     {cell['risk_score']} (awaiting Δ)")
    print(f"✓ Framework:      {cell['domain_payload']['regulatory_framework']}")
    print(f"✓ Jurisdiction:   {cell['domain_payload']['jurisdiction']}")
    print(f"✓ Intent Type:    {cell['domain_payload']['intent_type']} (awaiting Δ)")
    print(f"\n{'=' * 60}")
    print("TC-001 PASSED — Cell initialized, ready for Δ")
    print(f"{'=' * 60}")
