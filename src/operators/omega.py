"""
NEXUS MVP — Ω (Omega) Operator
=================================
Final decision gate for the NEXUS governance kernel.

Ω is the third and final stage of the pipeline:
    Α (intake) → Δ (risk evaluation) → Ω (decision gate)

E.Decision Values:
    release   — Risk within thresholds. Action may proceed.
    escalate  — Risk gate or integrity violation. Route to human.
    abstain   — Indeterminate state. Fallback only.
    block     — Reserved for future use. Not active in MVP.

Invariants:
    - Zero LLM calls
    - uncertainty.binding is NEVER read for decision-making
    - Every execution path writes a LEDGER entry
    - Pending cells are rejected (ValueError)

Specification Reference:
    Governance Decision Specification — Ω Section
"""

import logging
from typing import Optional
from uuid import uuid4

from src.overlays.arb import ARBOverlay
from src.overlays.ledger import LEDGEROverlay
from src.schemas.risk_manifest import load_risk_manifest

logger = logging.getLogger(__name__)

INTENT_ESCALATION_TARGET = {
    "fair_lending_check": "Fair Lending Counsel",
    "credit_decision": "Compliance Officer",
    "aml_screening": "BSA/AML Officer",
    "kyc_verification": "Compliance Officer",
    "fraud_assessment": "Fraud Ops Team",
    "regulatory_report": "Regulatory Reporting Team",
    "general_compliance_query": "Compliance Officer",
}

ESCALATION_VARIANT_MAP = {
    "Compliance Officer": "defer_to_compliance_officer",
    "BSA/AML Officer": "defer_to_compliance_officer",
    "Fair Lending Counsel": "defer_to_legal",
    "Fraud Ops Team": "defer_to_compliance_officer",
    "Regulatory Reporting Team": "defer_to_compliance_officer",
}

DEFAULT_VARIANT = "defer_to_compliance_officer"


def _get_escalation_variant(intent_type: str) -> str:
    target = INTENT_ESCALATION_TARGET.get(intent_type, "Compliance Officer")
    return ESCALATION_VARIANT_MAP.get(target, DEFAULT_VARIANT)


def _get_escalation_target(intent_type: str) -> str:
    return INTENT_ESCALATION_TARGET.get(intent_type, "Compliance Officer")


class OmegaOperator:
    """Ω operator: Final decision gate."""

    def __init__(self, ledger_path: str, manifest_path: Optional[str] = None):
        self.arb = ARBOverlay()
        self.ledger = LEDGEROverlay(ledger_path)
        self.manifest = load_risk_manifest(manifest_path)

    def process(self, cell: dict, input_query: str, regulatory_context: dict) -> dict:
        """
        Execute Ω operator: ARB → Decision → LEDGER.

        Raises:
            ValueError: If cell status is "pending" or cell is malformed.
            RuntimeError: If NEXUS invariant is violated or LEDGER write fails.
        """
        if cell.get("status") == "pending":
            raise ValueError(
                "Ω operator cannot process unevaluated cell (status='pending'). "
                "Cell must pass through Δ before reaching Ω."
            )

        required = {"cell_id", "status", "proposal", "uncertainty", "domain_payload"}
        missing = required - set(cell.keys())
        if missing:
            raise ValueError(f"Cell missing required fields for Ω: {missing}")

        run_id = str(uuid4())

        # Step 1: ARB Evaluation
        arb_result = self.arb.evaluate(cell)
        logger.info(f"Ω Step 1 — ARB: level={arb_result['level_triggered']}, code={arb_result['reason_code']}")

        # Step 2: Make Decision
        decision = self._make_decision(cell, arb_result)
        logger.info(f"Ω Step 2 — Decision: {decision['decision']}")

        # Step 3: Write LEDGER
        ledger_entry = self.ledger.write(
            run_id=run_id,
            input_query=input_query,
            cell=cell,
            arb_result=arb_result,
            decision=decision,
        )
        logger.info(f"Ω Step 3 — LEDGER entry written: run_id={run_id}")

        # Step 4: Build output
        domain_payload = cell.get("domain_payload", {})
        intent_type = domain_payload.get("intent_type", "unknown")
        risk_score = cell.get("risk_score")

        threshold_value = None
        if intent_type in self.manifest.risk_classes:
            threshold_value = self.manifest.risk_classes[intent_type].tau_hard_r

        output = {
            "run_id": run_id,
            "cell_id": cell.get("cell_id"),
            "decision": decision["decision"],
            "variant": decision["variant"],
            "reasoning": decision["reasoning"],
            "regulatory_reference": decision.get("regulatory_reference"),
            "next_action": decision.get("next_action"),
            "audit_record": {
                "run_id": run_id,
                "cell_id": cell.get("cell_id"),
                "intent_class": intent_type,
                "risk_score": risk_score,
                "threshold_value": threshold_value,
                "arb_level_triggered": arb_result["level_triggered"],
                "arb_reason_code": arb_result["reason_code"],
                "timestamp": ledger_entry["timestamp"],
            },
        }

        self._assert_invariants(cell, output)
        return output

    def _make_decision(self, cell: dict, arb_result: dict) -> dict:
        """Produce E.Decision. INVARIANT: uncertainty is NEVER read here."""
        domain_payload = cell.get("domain_payload", {})
        intent_type = domain_payload.get("intent_type", "unknown")

        if arb_result["level_triggered"] == 1:
            return {
                "decision": "escalate",
                "variant": "defer_to_compliance_officer",
                "reasoning": f"Cell integrity violation: {arb_result['trigger_reason']}",
                "regulatory_reference": None,
                "next_action": "Manual review required — data integrity issue",
            }

        if cell["status"] == "blocked":
            variant = _get_escalation_variant(intent_type)
            target = _get_escalation_target(intent_type)
            risk_score = cell.get("risk_score", 0.0)

            reg_frameworks = []
            if intent_type in self.manifest.risk_classes:
                reg_frameworks = self.manifest.risk_classes[intent_type].regulatory_framework

            threshold = None
            if intent_type in self.manifest.risk_classes:
                threshold = self.manifest.risk_classes[intent_type].tau_hard_r

            reasoning = f"{intent_type} risk score {risk_score} exceeds hard gate τ={threshold}"
            if reg_frameworks:
                reasoning += f" — {', '.join(reg_frameworks)} exposure"

            return {
                "decision": "escalate",
                "variant": variant,
                "reasoning": reasoning,
                "regulatory_reference": ", ".join(reg_frameworks) if reg_frameworks else None,
                "next_action": f"Manual review required — route to {target}",
            }

        if cell["status"] == "safe":
            return {
                "decision": "release",
                "variant": None,
                "reasoning": "Risk within acceptable thresholds",
                "regulatory_reference": None,
                "next_action": None,
            }

        logger.error(f"Ω: Indeterminate cell status: {cell.get('status')}")
        return {
            "decision": "abstain",
            "variant": None,
            "reasoning": f"Indeterminate cell status: {cell.get('status')}",
            "regulatory_reference": None,
            "next_action": "System error — contact administrator",
        }

    def _assert_invariants(self, cell: dict, output: dict) -> None:
        uncertainty = cell.get("uncertainty", {})
        if uncertainty.get("mode") != "proxy":
            raise RuntimeError(
                f"NEXUS INVARIANT VIOLATION: uncertainty.mode must be 'proxy', "
                f"got '{uncertainty.get('mode')}'"
            )
        if uncertainty.get("binding") is not False:
            raise RuntimeError(
                f"NEXUS INVARIANT VIOLATION: uncertainty.binding must be False, "
                f"got {uncertainty.get('binding')}"
            )
        valid_decisions = {"release", "escalate", "abstain", "block"}
        if output.get("decision") not in valid_decisions:
            raise RuntimeError(
                f"NEXUS INVARIANT VIOLATION: decision must be one of {valid_decisions}, "
                f"got '{output.get('decision')}'"
            )
        if "run_id" not in output:
            raise RuntimeError("NEXUS INVARIANT VIOLATION: output missing run_id")
        if "audit_record" not in output:
            raise RuntimeError("NEXUS INVARIANT VIOLATION: output missing audit_record")
