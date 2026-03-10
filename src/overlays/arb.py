"""
NEXUS MVP — ARB (Arbitration) Overlay
=======================================
Priority ladder for conflict resolution. Deterministic. No LLM.

Priority Levels (MVP):
    Level 1 (highest): Integrity violations — schema errors, missing fields
    Level 2:           Risk hard gate violations — status == "blocked"
    Level 3 (deferred): Uncertainty abstention — NOT active in MVP
    Level 4 (lowest):  User intent — implicit, not evaluated

Reason Codes:
    R0 — No violation. Release.
    R1 — Integrity violation (cell schema error).
    R2 — Risk hard gate triggered (status = blocked).

Invariants:
    - Zero LLM calls
    - Level 1 always takes priority over Level 2
    - Level 3 is NEVER evaluated in MVP
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

REQUIRED_CELL_KEYS = {
    "cell_id", "timestamp", "status", "proposal",
    "claims", "uncertainty", "domain_payload",
}

VALID_STATUSES = {"safe", "blocked"}


class ARBOverlay:
    """Arbitration overlay — evaluates cell against priority ladder."""

    def evaluate(self, cell: dict) -> dict:
        integrity_result = self._check_integrity(cell)
        if integrity_result is not None:
            logger.warning(f"ARB Level 1 triggered: {integrity_result}")
            return {
                "level_triggered": 1,
                "trigger_reason": integrity_result,
                "recommended_decision": "escalate",
                "reason_code": "R1",
            }

        if cell.get("status") == "blocked":
            reason = (
                f"Risk hard gate violated: risk_score={cell.get('risk_score')} "
                f"for intent={cell.get('domain_payload', {}).get('intent_type', 'unknown')}"
            )
            logger.info(f"ARB Level 2 triggered: {reason}")
            return {
                "level_triggered": 2,
                "trigger_reason": reason,
                "recommended_decision": "escalate",
                "reason_code": "R2",
            }

        # Level 3 (uncertainty abstention) DEFERRED — not active in MVP
        logger.info("ARB: No violations. Recommending release.")
        return {
            "level_triggered": None,
            "trigger_reason": None,
            "recommended_decision": "release",
            "reason_code": "R0",
        }

    def _check_integrity(self, cell: dict) -> Optional[str]:
        missing = REQUIRED_CELL_KEYS - set(cell.keys())
        if missing:
            return f"Missing required cell keys: {missing}"

        if cell.get("status") not in VALID_STATUSES:
            return f"Invalid cell status: '{cell.get('status')}' (expected: {VALID_STATUSES})"

        if cell.get("risk_score") is not None:
            if not isinstance(cell["risk_score"], (int, float)):
                return f"risk_score must be numeric, got: {type(cell['risk_score']).__name__}"

        proposal = cell.get("proposal")
        if not isinstance(proposal, dict):
            return "proposal must be a dict"
        if "action" not in proposal or "reasoning" not in proposal:
            return "proposal missing 'action' or 'reasoning'"

        uncertainty = cell.get("uncertainty")
        if not isinstance(uncertainty, dict):
            return "uncertainty must be a dict"
        if "mode" not in uncertainty or "binding" not in uncertainty:
            return "uncertainty missing 'mode' or 'binding'"

        return None
