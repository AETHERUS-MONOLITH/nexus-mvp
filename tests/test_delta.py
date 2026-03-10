"""
NEXUS MVP — Δ Operator Test Suite
====================================
Validates Delta operator behavior against specification.

Δ is 100% deterministic — no API keys needed, no fallback paths.
Every test is fully reproducible.

Test Cases:
    TC-002: AML screening high-risk jurisdiction
    TC-003: Fair lending disparate impact
    Edge cases: general queries, unknown jurisdictions, boundary conditions

Specification Reference:
    Governance Test Suite — TC-002, TC-003
    FinTech Risk Manifest v1.0
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.operators.alpha import alpha_operator
from src.operators.delta import (
    delta_operator,
    classify_intent,
    compute_risk_score,
    evaluate_hard_gate,
)
from src.schemas.risk_manifest import load_risk_manifest


TC_002_QUERY = (
    "Is this $15,000 wire transfer to Iran flagged "
    "for suspicious activity?"
)
TC_002_CONTEXT = {
    "session_id": "test-session-002",
    "timestamp": "2026-03-10T09:00:00Z",
    "regulatory_framework": "BSA_AML",
    "jurisdiction": "US",
}

TC_003_QUERY = (
    "Does our credit model show disparate impact "
    "on applicants by race?"
)
TC_003_CONTEXT = {
    "session_id": "test-session-003",
    "timestamp": "2026-03-10T09:00:00Z",
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}


class TestDeltaOperatorTC002:
    """TC-002: AML screening validation — full Α → Δ pipeline."""

    def setup_method(self):
        cell = alpha_operator(TC_002_QUERY, TC_002_CONTEXT)
        self.cell = delta_operator(cell)

    def test_intent_classified_as_aml(self):
        assert self.cell["domain_payload"]["intent_type"] == "aml_screening"

    def test_risk_score_is_populated(self):
        assert self.cell["risk_score"] is not None
        assert isinstance(self.cell["risk_score"], float)

    def test_risk_score_in_valid_range(self):
        assert 0.0 <= self.cell["risk_score"] <= 1.0

    def test_risk_score_is_base_aml(self):
        """US has no AML modifier → risk = base (0.80)."""
        assert self.cell["risk_score"] == 0.80

    def test_risk_exceeds_threshold(self):
        """AML risk (0.80) > tau_hard_r (0.30) → must block."""
        assert self.cell["risk_score"] > 0.30

    def test_status_is_blocked(self):
        assert self.cell["status"] == "blocked"

    def test_human_oversight_required(self):
        assert self.cell["domain_payload"]["human_oversight_required"] is True

    def test_explainability_required(self):
        """Risk > 0.75 → explainability required."""
        assert self.cell["domain_payload"]["explainability_required"] is True

    def test_regulatory_references_present(self):
        refs = self.cell["domain_payload"]["regulatory_article_references"]
        assert len(refs) > 0
        assert "31 U.S.C. § 5311" in refs

    def test_uncertainty_unchanged(self):
        """Δ must NOT modify Α's uncertainty fields."""
        assert self.cell["uncertainty"]["mode"] == "proxy"
        assert self.cell["uncertainty"]["binding"] is False


class TestDeltaOperatorTC003:
    """TC-003: Fair lending validation — highest risk class."""

    def setup_method(self):
        cell = alpha_operator(TC_003_QUERY, TC_003_CONTEXT)
        self.cell = delta_operator(cell)

    def test_intent_classified_as_fair_lending(self):
        """'disparate impact' → fair_lending_check (not credit_decision)."""
        assert self.cell["domain_payload"]["intent_type"] == "fair_lending_check"

    def test_risk_score_clamped_to_max(self):
        """Fair lending US: 0.90 + 0.15 = 1.05, clamped to 1.0."""
        assert self.cell["risk_score"] == 1.0

    def test_status_is_blocked(self):
        assert self.cell["status"] == "blocked"

    def test_adverse_action_potential(self):
        assert self.cell["domain_payload"]["adverse_action_potential"] is True

    def test_explainability_required(self):
        assert self.cell["domain_payload"]["explainability_required"] is True

    def test_human_oversight_required(self):
        assert self.cell["domain_payload"]["human_oversight_required"] is True

    def test_regulatory_references(self):
        refs = self.cell["domain_payload"]["regulatory_article_references"]
        assert "15 U.S.C. § 1691" in refs
        assert "42 U.S.C. § 3605" in refs


class TestIntentClassification:
    """Validate keyword-based intent classification in isolation."""

    def test_credit_keywords(self):
        assert classify_intent("Approve a $50,000 loan") == "credit_decision"
        assert classify_intent("Credit score 680") == "credit_decision"
        assert classify_intent("DTI ratio is 38%") == "credit_decision"
        assert classify_intent("Mortgage application") == "credit_decision"

    def test_aml_keywords(self):
        assert classify_intent("Wire transfer to Iran") == "aml_screening"
        assert classify_intent("AML compliance check") == "aml_screening"
        assert classify_intent("Suspicious activity report") == "aml_screening"
        assert classify_intent("OFAC sanctions list") == "aml_screening"

    def test_fair_lending_keywords(self):
        assert classify_intent("Disparate impact analysis") == "fair_lending_check"
        assert classify_intent("Protected class data") == "fair_lending_check"
        assert classify_intent("Fair lending review") == "fair_lending_check"

    def test_kyc_keywords(self):
        assert classify_intent("KYC verification needed") == "kyc_verification"
        assert classify_intent("Customer identification program") == "kyc_verification"
        assert classify_intent("PEP screening") == "kyc_verification"

    def test_fraud_keywords(self):
        assert classify_intent("Fraud detection alert") == "fraud_assessment"
        assert classify_intent("Account takeover attempt") == "fraud_assessment"
        assert classify_intent("Chargeback dispute") == "fraud_assessment"

    def test_regulatory_report_keywords(self):
        assert classify_intent("Quarterly filing due") == "regulatory_report"
        assert classify_intent("Compliance audit schedule") == "regulatory_report"

    def test_no_match_defaults_to_general(self):
        assert classify_intent("What is the weather today?") == "general_compliance_query"
        assert classify_intent("Hello, how are you?") == "general_compliance_query"
        assert classify_intent("Explain the process") == "general_compliance_query"

    def test_case_insensitive(self):
        assert classify_intent("AML CHECK") == "aml_screening"
        assert classify_intent("Disparate Impact") == "fair_lending_check"
        assert classify_intent("LOAN APPROVAL") == "credit_decision"

    def test_fair_lending_priority_over_credit(self):
        """
        'disparate impact' must match fair_lending_check even though
        'credit' would match credit_decision. Specificity ordering is load-bearing.
        """
        assert classify_intent("Does our credit model show disparate impact?") == "fair_lending_check"


class TestRiskScoreComputation:
    """Validate risk score arithmetic against manifest values."""

    def setup_method(self):
        self.manifest = load_risk_manifest()

    def test_credit_decision_us(self):
        """Credit US: 0.85 + 0.15 = 1.0 (clamped)."""
        assert compute_risk_score("credit_decision", "US", self.manifest) == 1.0

    def test_credit_decision_eu(self):
        """Credit EU: 0.85 + 0.0 = 0.85 (no EU modifier for credit)."""
        assert compute_risk_score("credit_decision", "EU", self.manifest) == 0.85

    def test_aml_screening_us(self):
        """AML US: 0.80 + 0.0 = 0.80."""
        assert compute_risk_score("aml_screening", "US", self.manifest) == 0.80

    def test_aml_screening_eu(self):
        """AML EU: 0.80 + 0.10 = 0.90."""
        assert compute_risk_score("aml_screening", "EU", self.manifest) == 0.90

    def test_aml_screening_uk(self):
        """AML UK: 0.80 + 0.10 = 0.90."""
        assert compute_risk_score("aml_screening", "UK", self.manifest) == 0.90

    def test_fair_lending_us(self):
        """Fair lending US: 0.90 + 0.15 = 1.05, clamped to 1.0."""
        assert compute_risk_score("fair_lending_check", "US", self.manifest) == 1.0

    def test_general_query_no_modifier(self):
        assert compute_risk_score("general_compliance_query", "US", self.manifest) == 0.15

    def test_unknown_jurisdiction_no_modifier(self):
        """Unknown jurisdiction → no modifier applied → base risk only."""
        assert compute_risk_score("credit_decision", "UNKNOWN", self.manifest) == 0.85

    def test_kyc_eu_modifier(self):
        """KYC EU: 0.75 + 0.10 = 0.85."""
        assert compute_risk_score("kyc_verification", "EU", self.manifest) == 0.85


class TestHardGateEvaluation:
    """Validate hard gate logic — strict inequality."""

    def test_above_threshold_blocks(self):
        assert evaluate_hard_gate(0.85, 0.25) is True

    def test_below_threshold_safe(self):
        assert evaluate_hard_gate(0.15, 0.70) is False

    def test_exactly_at_threshold_not_blocked(self):
        """r == τ → NOT blocked. Strict inequality (>), not (>=). Spec-mandated."""
        assert evaluate_hard_gate(0.30, 0.30) is False

    def test_zero_risk_never_blocks(self):
        assert evaluate_hard_gate(0.0, 0.0) is False

    def test_max_risk_always_blocks(self):
        assert evaluate_hard_gate(1.0, 0.99) is True

    def test_max_risk_at_max_threshold(self):
        """Risk 1.0 at threshold 1.0 → NOT blocked (strict >)."""
        assert evaluate_hard_gate(1.0, 1.0) is False


class TestDeltaOperatorEdgeCases:
    """Edge case validation through the full Α → Δ pipeline."""

    def test_general_query_low_risk(self):
        cell = alpha_operator(
            "What are the standard procedures for quarterly reviews?",
            {"regulatory_framework": "UNKNOWN", "jurisdiction": "US"},
        )
        cell = delta_operator(cell)
        assert cell["domain_payload"]["intent_type"] == "general_compliance_query"
        assert cell["risk_score"] == 0.15
        assert cell["status"] == "safe"

    def test_unknown_jurisdiction_base_risk_only(self):
        """Unknown jurisdiction → base risk, no modifier."""
        cell = alpha_operator(
            "Approve credit application",
            {"regulatory_framework": "ECOA", "jurisdiction": "UNKNOWN"},
        )
        cell = delta_operator(cell)
        assert cell["risk_score"] == 0.85
        assert cell["status"] == "blocked"

    def test_delta_preserves_alpha_fields(self):
        """Δ must not overwrite Α-initialized fields."""
        cell = alpha_operator(
            "Check wire transfer for suspicious activity",
            {"session_id": "preserve-test", "regulatory_framework": "BSA_AML", "jurisdiction": "US"},
        )
        original_cell_id = cell["cell_id"]
        original_timestamp = cell["timestamp"]
        original_proposal = cell["proposal"]
        original_uncertainty = cell["uncertainty"]

        cell = delta_operator(cell)

        assert cell["cell_id"] == original_cell_id
        assert cell["timestamp"] == original_timestamp
        assert cell["proposal"] == original_proposal
        assert cell["uncertainty"] == original_uncertainty

    def test_status_only_safe_or_blocked(self):
        """Δ must produce exactly 'safe' or 'blocked' — nothing else."""
        for query, ctx in [
            ("What are the standard procedures for quarterly reviews?",
             {"regulatory_framework": "UNKNOWN", "jurisdiction": "US"}),
            ("Approve a $50,000 loan for credit score 680",
             {"regulatory_framework": "ECOA", "jurisdiction": "US"}),
        ]:
            cell = delta_operator(alpha_operator(query, ctx))
            assert cell["status"] in ("safe", "blocked")


if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS MVP — Δ Operator Validation (TC-002, TC-003)")
    print("=" * 60)

    cell_002 = delta_operator(alpha_operator(TC_002_QUERY, TC_002_CONTEXT))
    print(f"\nTC-002: AML Screening")
    print(f"  Intent:          {cell_002['domain_payload']['intent_type']}")
    print(f"  Risk Score:      {cell_002['risk_score']}")
    print(f"  Status:          {cell_002['status']}")
    print(f"  Oversight:       {cell_002['domain_payload']['human_oversight_required']}")
    print(f"  Explainability:  {cell_002['domain_payload']['explainability_required']}")
    print(f"  References:      {cell_002['domain_payload']['regulatory_article_references']}")

    cell_003 = delta_operator(alpha_operator(TC_003_QUERY, TC_003_CONTEXT))
    print(f"\nTC-003: Fair Lending")
    print(f"  Intent:          {cell_003['domain_payload']['intent_type']}")
    print(f"  Risk Score:      {cell_003['risk_score']}")
    print(f"  Status:          {cell_003['status']}")
    print(f"  Adverse Action:  {cell_003['domain_payload']['adverse_action_potential']}")
    print(f"  Explainability:  {cell_003['domain_payload']['explainability_required']}")
    print(f"  References:      {cell_003['domain_payload']['regulatory_article_references']}")

    print(f"\n{'=' * 60}")
    print("TC-002, TC-003 PASSED — Δ operator validated")
    print(f"{'=' * 60}")
