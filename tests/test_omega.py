"""
NEXUS MVP — Ω Operator Test Suite
====================================
17 tests across 5 classes:
    Class 1: Decision routing (TO-001 through TO-004)
    Class 2: ARB overlay (TO-005 through TO-008)
    Class 3: LEDGER (TO-009 through TO-013)
    Class 4: Invariants (TO-014 through TO-016)
    Class 5: Determinism (TO-017)
"""

import hashlib
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator
from src.overlays.arb import ARBOverlay
from src.overlays.ledger import LEDGEROverlay


def _make_cell(query: str, context: dict) -> dict:
    return delta_operator(alpha_operator(query, context))


CREDIT_QUERY = (
    "Should we approve a $50,000 loan for an applicant "
    "with credit score 680, income $45K, DTI 38%?"
)
CREDIT_CONTEXT = {
    "session_id": "test-omega-credit",
    "timestamp": "2026-03-10T10:00:00Z",
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}

FAIR_LENDING_QUERY = "Does our credit model show disparate impact on applicants by race?"
FAIR_LENDING_CONTEXT = {
    "session_id": "test-omega-fair-lending",
    "timestamp": "2026-03-10T10:00:00Z",
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}

GENERAL_QUERY = "What are the standard procedures for quarterly reviews?"
GENERAL_CONTEXT = {
    "session_id": "test-omega-general",
    "timestamp": "2026-03-10T10:00:00Z",
    "regulatory_framework": "UNKNOWN",
    "jurisdiction": "US",
}

REG_CONTEXT = {"framework": "ECOA", "intent_class": "credit_decision"}


class TestDecisionRouting:
    """TO-001 through TO-004."""

    def test_to_001_blocked_cell_escalates(self, tmp_path):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        assert cell["status"] == "blocked"
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        assert omega.process(cell, CREDIT_QUERY, REG_CONTEXT)["decision"] == "escalate"

    def test_to_002_safe_cell_releases(self, tmp_path):
        cell = _make_cell(GENERAL_QUERY, GENERAL_CONTEXT)
        assert cell["status"] == "safe"
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        assert omega.process(cell, GENERAL_QUERY, REG_CONTEXT)["decision"] == "release"

    def test_to_003_fair_lending_routes_to_legal(self, tmp_path):
        cell = _make_cell(FAIR_LENDING_QUERY, FAIR_LENDING_CONTEXT)
        assert cell["domain_payload"]["intent_type"] == "fair_lending_check"
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        output = omega.process(cell, FAIR_LENDING_QUERY, REG_CONTEXT)
        assert output["decision"] == "escalate"
        assert output["variant"] == "defer_to_legal"

    def test_to_004_credit_decision_routes_to_compliance(self, tmp_path):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        assert cell["domain_payload"]["intent_type"] == "credit_decision"
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        output = omega.process(cell, CREDIT_QUERY, REG_CONTEXT)
        assert output["decision"] == "escalate"
        assert output["variant"] == "defer_to_compliance_officer"


class TestARBOverlay:
    """TO-005 through TO-008."""

    def test_to_005_arb_level_2_on_blocked(self):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        result = ARBOverlay().evaluate(cell)
        assert result["level_triggered"] == 2
        assert result["reason_code"] == "R2"
        assert result["recommended_decision"] == "escalate"

    def test_to_006_arb_level_1_on_integrity_violation(self):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        cell["risk_score"] = "not_a_number"
        result = ARBOverlay().evaluate(cell)
        assert result["level_triggered"] == 1
        assert result["reason_code"] == "R1"
        assert result["recommended_decision"] == "escalate"

    def test_to_007_arb_r0_on_safe_cell(self):
        cell = _make_cell(GENERAL_QUERY, GENERAL_CONTEXT)
        assert cell["status"] == "safe"
        result = ARBOverlay().evaluate(cell)
        assert result["level_triggered"] is None
        assert result["reason_code"] == "R0"
        assert result["recommended_decision"] == "release"

    def test_to_008_arb_level_1_priority_over_level_2(self):
        """Level 1 (integrity) takes priority over level 2 (risk gate)."""
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        assert cell["status"] == "blocked"   # would trigger level 2
        cell["risk_score"] = "corrupt"        # also triggers level 1
        result = ARBOverlay().evaluate(cell)
        assert result["level_triggered"] == 1
        assert result["reason_code"] == "R1"


class TestLEDGER:
    """TO-009 through TO-013."""

    def test_to_009_ledger_entry_on_escalate(self, tmp_path):
        ledger_path = str(tmp_path / "ledger.jsonl")
        omega = OmegaOperator(ledger_path=ledger_path)
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        output = omega.process(cell, CREDIT_QUERY, REG_CONTEXT)
        assert output["decision"] == "escalate"
        entries = omega.ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["omega_decision"]["decision"] == "escalate"

    def test_to_010_ledger_entry_on_release(self, tmp_path):
        ledger_path = str(tmp_path / "ledger.jsonl")
        omega = OmegaOperator(ledger_path=ledger_path)
        cell = _make_cell(GENERAL_QUERY, GENERAL_CONTEXT)
        output = omega.process(cell, GENERAL_QUERY, REG_CONTEXT)
        assert output["decision"] == "release"
        entries = omega.ledger.read_all()
        assert len(entries) == 1
        assert entries[0]["omega_decision"]["decision"] == "release"

    def test_to_011_ledger_contains_input_hash(self, tmp_path):
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        omega.process(_make_cell(CREDIT_QUERY, CREDIT_CONTEXT), CREDIT_QUERY, REG_CONTEXT)
        entries = omega.ledger.read_all()
        expected = hashlib.sha256(CREDIT_QUERY.encode("utf-8")).hexdigest()
        assert entries[0]["input_hash"] == expected

    def test_to_012_ledger_read_all_returns_entries(self, tmp_path):
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        omega.process(_make_cell(CREDIT_QUERY, CREDIT_CONTEXT), CREDIT_QUERY, REG_CONTEXT)
        omega.process(_make_cell(GENERAL_QUERY, GENERAL_CONTEXT), GENERAL_QUERY, REG_CONTEXT)
        assert len(omega.ledger.read_all()) == 2

    def test_to_013_ledger_get_by_run_id(self, tmp_path):
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        output = omega.process(_make_cell(CREDIT_QUERY, CREDIT_CONTEXT), CREDIT_QUERY, REG_CONTEXT)
        entry = omega.ledger.get_by_run_id(output["run_id"])
        assert entry is not None
        assert entry["run_id"] == output["run_id"]
        assert entry["omega_decision"]["decision"] == "escalate"


class TestInvariants:
    """TO-014 through TO-016."""

    def test_to_014_pending_cell_raises_value_error(self, tmp_path):
        cell = alpha_operator(CREDIT_QUERY, CREDIT_CONTEXT)
        assert cell["status"] == "pending"
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        with pytest.raises(ValueError, match="pending"):
            omega.process(cell, CREDIT_QUERY, REG_CONTEXT)

    def test_to_015_uncertainty_mode_proxy_preserved(self, tmp_path):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        output = omega.process(cell, CREDIT_QUERY, REG_CONTEXT)
        assert cell["uncertainty"]["mode"] == "proxy"
        assert output["decision"] in ("release", "escalate", "abstain", "block")

    def test_to_016_uncertainty_binding_false_preserved(self, tmp_path):
        cell = _make_cell(CREDIT_QUERY, CREDIT_CONTEXT)
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        output = omega.process(cell, CREDIT_QUERY, REG_CONTEXT)
        assert cell["uncertainty"]["binding"] is False
        assert output is not None


class TestDeterminism:
    """TO-017."""

    def test_to_017_identical_input_identical_decision(self, tmp_path):
        """Same input → same decision fields. run_id differs (UUID per call)."""
        omega = OmegaOperator(ledger_path=str(tmp_path / "ledger.jsonl"))
        out1 = omega.process(_make_cell(CREDIT_QUERY, CREDIT_CONTEXT), CREDIT_QUERY, REG_CONTEXT)
        out2 = omega.process(_make_cell(CREDIT_QUERY, CREDIT_CONTEXT), CREDIT_QUERY, REG_CONTEXT)
        assert out1["decision"] == out2["decision"]
        assert out1["variant"] == out2["variant"]
        assert out1["reasoning"] == out2["reasoning"]
        assert out1["regulatory_reference"] == out2["regulatory_reference"]
        assert out1["run_id"] != out2["run_id"]
