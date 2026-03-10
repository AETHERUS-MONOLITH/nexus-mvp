"""
NEXUS MVP — Layer 3: Governance Correctness Test Suite
========================================================
Validates the governance thesis through ground-truth scenarios.

Architecture:
    - Α is mocked with minimal valid pending cells (deterministic, no API cost)
    - Δ and Ω are exercised live (these are the governance layers under test)
    - LEDGER uses tmp_path fixtures for isolation

Test Classes:
    Class 1: TestCriticalPath         — TC-001 to TC-004 (100% pass required)
    Class 2: TestEdgeCases            — TC-005 to TC-009 (90% pass required)
    Class 3: TestAuditAndDeterminism  — TC-010 to TC-011 (100% pass required)
"""

import hashlib
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator
from src.schemas.risk_manifest import load_risk_manifest


def make_governance_cell(query: str, jurisdiction: str, framework: str) -> dict:
    """Build a minimal valid pending cell as Α would produce."""
    return {
        "cell_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "proposal": {
            "action": query,
            "reasoning": f"Governance test cell for query: {query[:80]}",
        },
        "claims": [
            {
                "claim_id": str(uuid4()),
                "text": f"Query requests action under {framework} framework",
                "confidence": 0.5,
            }
        ],
        "evidence": [],
        "uncertainty": {
            "total": 0.5,
            "mode": "proxy",
            "binding": False,
            "note": "Observational only - does not influence Ω decisions",
        },
        "risk_score": None,
        "domain_payload": {
            "intent_type": None,
            "regulatory_framework": framework,
            "risk_subject": {
                "entity_type": "individual",
                "protected_class_data_present": False,
                "high_risk_jurisdiction": False,
                "pep_status": "none",
            },
            "jurisdiction": jurisdiction,
            "explainability_required": False,
            "human_oversight_required": False,
            "adverse_action_potential": False,
            "regulatory_article_references": [],
            "compliance_metadata": {},
        },
    }


def run_governance_pipeline(
    query: str, jurisdiction: str, framework: str, ledger_path: str
) -> dict:
    """Run full Δ → Ω pipeline with mocked Α output."""
    cell = make_governance_cell(query, jurisdiction, framework)
    cell = delta_operator(cell)

    omega = OmegaOperator(ledger_path=ledger_path)
    intent_class = cell["domain_payload"].get("intent_type", "unknown")
    reg_context = {"framework": framework, "intent_class": intent_class}
    output = omega.process(cell, query, reg_context)

    return {"cell": cell, "output": output}


class TestCriticalPath:
    """TC-001 to TC-004: Core governance scenarios. 100% pass required."""

    def test_tc_001_credit_decision_no_protected_class(self, tmp_path):
        """TC-001: credit_decision US → risk=1.0 → blocked → escalate → defer_to_compliance_officer."""
        query = "Should we approve a $50,000 loan for an applicant with credit score 680, income $45K, DTI 38%?"
        r = run_governance_pipeline(query, "US", "ECOA", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "credit_decision"
        assert r["cell"]["risk_score"] == pytest.approx(1.0, abs=0.01)
        assert r["cell"]["status"] == "blocked"
        assert r["output"]["decision"] == "escalate"
        assert r["output"]["variant"] == "defer_to_compliance_officer"
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False
        assert "run_id" in r["output"]["audit_record"]

    def test_tc_002_aml_screening_high_risk_jurisdiction(self, tmp_path):
        """TC-002: aml_screening US → risk=0.80 → blocked → escalate → defer_to_compliance_officer."""
        query = "Is this $15,000 wire transfer to Iran flagged for suspicious activity?"
        r = run_governance_pipeline(query, "US", "BSA_AML", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "aml_screening"
        assert r["cell"]["risk_score"] == pytest.approx(0.80, abs=0.01)
        assert r["cell"]["status"] == "blocked"
        assert r["output"]["decision"] == "escalate"
        assert r["output"]["variant"] == "defer_to_compliance_officer"
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_003_fair_lending_disparate_impact(self, tmp_path):
        """TC-003: fair_lending_check US → risk=1.0 (clamped) → blocked → escalate → defer_to_legal."""
        query = "Does our credit model show disparate impact on applicants by race?"
        r = run_governance_pipeline(query, "US", "ECOA", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "fair_lending_check"
        assert r["cell"]["risk_score"] == pytest.approx(1.0, abs=0.01)
        assert r["cell"]["status"] == "blocked"
        assert r["output"]["decision"] == "escalate"
        assert r["output"]["variant"] == "defer_to_legal"
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_004_general_compliance_low_risk(self, tmp_path):
        """TC-004: general_compliance_query US → risk=0.15 → safe → release."""
        query = "What are the standard procedures for quarterly reviews?"
        r = run_governance_pipeline(query, "US", "UNKNOWN", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "general_compliance_query"
        assert r["cell"]["risk_score"] == pytest.approx(0.15, abs=0.01)
        assert r["cell"]["status"] == "safe"
        assert r["output"]["decision"] == "release"
        assert r["output"]["variant"] is None
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False


class TestEdgeCases:
    """TC-005 to TC-009: Boundary conditions. 90% pass required (>=4/5)."""

    def test_tc_005_risk_exactly_at_threshold_not_blocked(self, tmp_path):
        """TC-005: risk == tau_hard_r → NOT blocked (strict > semantics)."""
        cell = make_governance_cell("Synthetic boundary test", "US", "BSA_AML")
        cell["status"] = "safe"
        cell["risk_score"] = 0.30  # == tau_hard_r for aml_screening
        cell["domain_payload"]["intent_type"] = "aml_screening"

        omega = OmegaOperator(ledger_path=str(tmp_path / "l.jsonl"))
        output = omega.process(
            cell, "Synthetic boundary test",
            {"framework": "BSA_AML", "intent_class": "aml_screening"},
        )

        assert cell["status"] == "safe"
        assert output["decision"] == "release"
        assert cell["uncertainty"]["mode"] == "proxy"
        assert cell["uncertainty"]["binding"] is False

    def test_tc_006_overlapping_intent_aml_over_fraud(self, tmp_path):
        """TC-006: AML keywords checked before fraud → aml_screening wins on overlap."""
        query = "Should we flag this transaction for both fraud and AML?"
        r = run_governance_pipeline(query, "US", "MULTI", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "aml_screening"
        assert r["cell"]["risk_score"] == pytest.approx(0.80, abs=0.01)
        assert r["cell"]["status"] == "blocked"
        assert r["output"]["decision"] == "escalate"
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_007_unknown_jurisdiction_base_risk_only(self, tmp_path):
        """TC-007: UNKNOWN jurisdiction → no modifier → base risk 0.85 → blocked."""
        query = "Can we approve this credit application?"
        r = run_governance_pipeline(query, "UNKNOWN", "UNKNOWN", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "credit_decision"
        assert r["cell"]["risk_score"] == pytest.approx(0.85, abs=0.01)
        assert r["cell"]["status"] == "blocked"
        assert r["output"]["decision"] == "escalate"
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_008_ecoa_regulatory_references_in_escalation(self, tmp_path):
        """TC-008: credit_decision escalation includes ECOA, FCRA, Regulation B."""
        query = "Deny loan application - insufficient income"
        r = run_governance_pipeline(query, "US", "ECOA", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "credit_decision"
        assert r["output"]["decision"] == "escalate"

        reg_ref = r["output"].get("regulatory_reference", "")
        assert "ECOA" in reg_ref
        assert "FCRA" in reg_ref
        assert "Regulation B" in reg_ref
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_009_bsa_regulatory_references_in_escalation(self, tmp_path):
        """TC-009: aml_screening escalation includes BSA_AML and USA PATRIOT Act."""
        query = "File SAR for structuring pattern detected"
        r = run_governance_pipeline(query, "US", "BSA_AML", str(tmp_path / "l.jsonl"))

        assert r["cell"]["domain_payload"]["intent_type"] == "aml_screening"
        assert r["output"]["decision"] == "escalate"

        reg_ref = r["output"].get("regulatory_reference", "")
        assert "BSA_AML" in reg_ref
        assert "USA PATRIOT Act" in reg_ref
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False


class TestAuditAndDeterminism:
    """TC-010 to TC-011: Audit completeness and determinism. 100% pass required."""

    def test_tc_010_audit_trail_completeness(self, tmp_path):
        """TC-010: All required LEDGER fields populated with correct types."""
        query = "Approve mortgage application"
        ledger_path = str(tmp_path / "l.jsonl")
        r = run_governance_pipeline(query, "US", "ECOA", ledger_path)

        audit = r["output"]["audit_record"]
        for field in ["run_id", "timestamp", "cell_id", "intent_class",
                      "risk_score", "threshold_value", "arb_level_triggered", "arb_reason_code"]:
            assert field in audit

        datetime.fromisoformat(audit["timestamp"])

        omega = OmegaOperator(ledger_path=ledger_path)
        entries = omega.ledger.read_all()
        assert len(entries) == 1

        entry = entries[0]
        for field in ["run_id", "timestamp", "input_hash", "alpha_output",
                      "delta_evaluation", "omega_decision", "overlay_decisions", "regulatory_context"]:
            assert field in entry

        expected_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        assert entry["input_hash"] == expected_hash
        assert len(entry["input_hash"]) == 64

        datetime.fromisoformat(entry["timestamp"])
        assert r["cell"]["uncertainty"]["mode"] == "proxy"
        assert r["cell"]["uncertainty"]["binding"] is False

    def test_tc_011_determinism_three_runs(self, tmp_path):
        """TC-011: Same input, 3 runs → identical decision fields. run_id differs."""
        query = "Approve $25K personal loan"
        ledger_path = str(tmp_path / "l.jsonl")

        results = [run_governance_pipeline(query, "US", "ECOA", ledger_path) for _ in range(3)]

        for i in range(1, 3):
            assert results[i]["output"]["decision"] == results[0]["output"]["decision"]
            assert results[i]["output"]["reasoning"] == results[0]["output"]["reasoning"]
            assert results[i]["output"]["variant"] == results[0]["output"]["variant"]
            assert results[i]["output"]["regulatory_reference"] == results[0]["output"]["regulatory_reference"]
            assert results[i]["cell"]["domain_payload"]["intent_type"] == results[0]["cell"]["domain_payload"]["intent_type"]
            assert results[i]["cell"]["risk_score"] == results[0]["cell"]["risk_score"]
            assert results[i]["cell"]["status"] == results[0]["cell"]["status"]

        run_ids = [r["output"]["run_id"] for r in results]
        assert len(set(run_ids)) == 3

        for r in results:
            assert r["cell"]["uncertainty"]["mode"] == "proxy"
            assert r["cell"]["uncertainty"]["binding"] is False


if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("NEXUS MVP — Layer 3: Governance Correctness Validation")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = os.path.join(tmp, "ledger.jsonl")
        scenarios = [
            ("TC-001", "Should we approve a $50,000 loan for an applicant with credit score 680, income $45K, DTI 38%?", "US", "ECOA"),
            ("TC-002", "Is this $15,000 wire transfer to Iran flagged for suspicious activity?", "US", "BSA_AML"),
            ("TC-003", "Does our credit model show disparate impact on applicants by race?", "US", "ECOA"),
            ("TC-004", "What are the standard procedures for quarterly reviews?", "US", "UNKNOWN"),
        ]
        for label, query, jurisdiction, framework in scenarios:
            r = run_governance_pipeline(query, jurisdiction, framework, ledger_path)
            print(f"\n{label}:")
            print(f"  Intent:    {r['cell']['domain_payload']['intent_type']}")
            print(f"  Risk:      {r['cell']['risk_score']}")
            print(f"  Status:    {r['cell']['status']}")
            print(f"  Decision:  {r['output']['decision']}")
            print(f"  Variant:   {r['output']['variant']}")

    print(f"\n{'=' * 60}")
    print("Layer 3 Governance Correctness — Manual Run Complete")
    print(f"{'=' * 60}")
