"""
NEXUS MVP — Δ (Delta) Operator
================================
Deterministic risk classification and evaluation operator.

Δ is the second stage of the NEXUS governance pipeline.
It receives an initialized cell from Α and applies rule-based
risk classification. NO LLM inference. NO probabilistic logic.
Same input → same output, always.

Processing Steps:
    1. Intent classification — keyword matching against risk classes
    2. Risk score computation — base_risk + jurisdiction modifier, clamped [0,1]
    3. Hard gate evaluation — r > τ^hard_r → BLOCKED (strict inequality)
    4. Domain payload updates — risk flags, oversight requirements, references

Behavioral Contract:
    - Deterministic: zero LLM calls, zero randomness
    - Manifest-driven: all risk values from data/risk_manifest.json
    - Append-only: Δ adds to the cell, never removes Α's work
    - Two terminal states: "safe" or "blocked" (nothing else)

Hard Gate Semantics:
    - Uses strict inequality: r > τ^hard_r (NOT >=)
    - r == τ^hard_r → NOT blocked (benefit of the doubt)

Specification Reference:
    Governance Decision Specification — Δ Section
    FinTech Risk Manifest v1.0
"""

import logging
from typing import Dict

from src.schemas.risk_manifest import load_risk_manifest, RiskManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------
# Ordered by specificity: more specific classes checked first to prevent
# broad classes from shadowing narrow ones.
# "disparate impact" must match fair_lending_check before "credit" matches
# credit_decision. This ordering is load-bearing.
# ---------------------------------------------------------------------------

INTENT_KEYWORDS: Dict[str, list] = {
    "fair_lending_check": [
        "disparate impact", "protected class", "fair lending",
        "discrimination", "redlining", "hmda",
    ],
    "credit_decision": [
        "loan", "credit", "approve", "deny", "underwriting",
        "adverse action", "credit score", "dti", "mortgage",
    ],
    "aml_screening": [
        "aml", "anti-money laundering", "wire transfer",
        "suspicious activity", "sar", "high-risk jurisdiction",
        "sanctions", "ofac",
    ],
    "kyc_verification": [
        "kyc", "know your customer", "identity", "onboarding",
        "cip", "customer identification", "pep",
    ],
    "fraud_assessment": [
        "fraud", "anomaly", "suspicious transaction",
        "chargeback", "account takeover",
    ],
    "regulatory_report": [
        "report", "filing", "disclosure", "audit",
    ],
}

EXPLAINABILITY_RISK_THRESHOLD = 0.75
ADVERSE_ACTION_INTENTS = {"credit_decision", "fair_lending_check"}


def classify_intent(proposal_text: str) -> str:
    """
    Classify query intent via keyword matching against risk classes.

    Returns the FIRST match (ordered by specificity).
    Defaults to "general_compliance_query" if no keywords match.
    """
    text_lower = proposal_text.lower()

    for intent_type, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                logger.debug(f"Intent match: '{keyword}' → {intent_type}")
                return intent_type

    logger.debug("No keyword match — defaulting to general_compliance_query")
    return "general_compliance_query"


def compute_risk_score(
    intent_type: str,
    jurisdiction: str,
    manifest: RiskManifest,
) -> float:
    """
    Compute risk score: base_risk + jurisdiction modifier, clamped to [0,1].

        r = clamp(base_risk + modifier, 0.0, 1.0)

    Raises:
        KeyError: If intent_type is not in the manifest.
    """
    risk_class = manifest.risk_classes[intent_type]
    base_risk = risk_class.base_risk
    modifier = risk_class.jurisdiction_modifiers.get(jurisdiction, 0.0)
    risk_score = max(0.0, min(1.0, base_risk + modifier))

    logger.debug(f"Risk: {base_risk} (base) + {modifier} ({jurisdiction}) = {risk_score}")
    return risk_score


def evaluate_hard_gate(risk_score: float, tau_hard_r: float) -> bool:
    """
    Evaluate hard gate: does risk_score exceed the threshold?

    Uses STRICT inequality: r > τ^hard_r.
    r == τ^hard_r → gate does NOT trigger (not blocked).
    """
    return risk_score > tau_hard_r


def delta_operator(cell: dict) -> dict:
    """
    Δ operator: Deterministic risk classification and evaluation.

    Processing steps:
        1. Intent classification (keyword → risk class)
        2. Risk score computation (base + jurisdiction modifier)
        3. Hard gate evaluation (r > τ^hard_r → blocked)
        4. Domain payload updates (risk flags, references)

    Args:
        cell: Cell dict from Α operator.

    Returns:
        Updated cell dict with risk_score, intent_type, and status set.
    """
    manifest = load_risk_manifest()

    # Step 1: Intent Classification
    proposal_text = cell["proposal"]["action"]
    intent_type = classify_intent(proposal_text)
    cell["domain_payload"]["intent_type"] = intent_type
    logger.info(f"Δ Step 1 — Intent classified: {intent_type}")

    # Step 2: Risk Score Computation
    jurisdiction = cell["domain_payload"].get("jurisdiction", "US")
    risk_score = compute_risk_score(intent_type, jurisdiction, manifest)
    cell["risk_score"] = risk_score
    logger.info(f"Δ Step 2 — Risk score: {risk_score}")

    # Step 3: Hard Gate Evaluation
    risk_class = manifest.risk_classes[intent_type]
    tau_hard_r = risk_class.tau_hard_r
    gate_violated = evaluate_hard_gate(risk_score, tau_hard_r)

    if gate_violated:
        cell["status"] = "blocked"
        logger.warning(f"Δ Step 3 — HARD GATE TRIGGERED: {risk_score} > {tau_hard_r} → BLOCKED")
    else:
        cell["status"] = "safe"
        logger.info(f"Δ Step 3 — Gate clear: {risk_score} <= {tau_hard_r} → SAFE")

    # Step 4: Domain Payload Updates
    if intent_type in ADVERSE_ACTION_INTENTS:
        cell["domain_payload"]["adverse_action_potential"] = True

    if cell["status"] == "blocked":
        cell["domain_payload"]["human_oversight_required"] = True

    if risk_score > EXPLAINABILITY_RISK_THRESHOLD:
        cell["domain_payload"]["explainability_required"] = True

    cell["domain_payload"]["regulatory_article_references"] = (
        risk_class.article_references
    )

    logger.info(
        f"Δ Step 4 — Payload updated: "
        f"adverse={cell['domain_payload'].get('adverse_action_potential', False)}, "
        f"oversight={cell['domain_payload'].get('human_oversight_required', False)}, "
        f"explainability={cell['domain_payload'].get('explainability_required', False)}"
    )

    return cell
