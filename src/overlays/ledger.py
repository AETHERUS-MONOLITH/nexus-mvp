"""
NEXUS MVP — LEDGER Overlay
============================
Immutable append-only audit trail. JSONL format.

Every execution path through Ω produces a LEDGER entry.
No silent exits. No record modification after write.

Invariants:
    - Append-only: records are never modified or deleted
    - Every Ω execution writes exactly one entry
    - Write failures raise RuntimeError (never silent)
    - Zero LLM calls
"""

import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)


class LEDGEROverlay:
    """Immutable append-only audit trail. JSONL format."""

    def __init__(self, ledger_path: str):
        self.ledger_path = ledger_path

    def write(self, run_id: str, input_query: str, cell: dict, arb_result: dict, decision: dict) -> dict:
        entry = self._build_entry(run_id, input_query, cell, arb_result, decision)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            logger.info(f"LEDGER: Entry written for run_id={run_id}")
            return entry
        except Exception as e:
            raise RuntimeError(f"LEDGER write failed for run_id={run_id}: {e}") from e

    def read_all(self) -> List[dict]:
        if not os.path.exists(self.ledger_path):
            return []
        entries = []
        with open(self.ledger_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def get_by_run_id(self, run_id: str) -> Optional[dict]:
        for entry in self.read_all():
            if entry.get("run_id") == run_id:
                return entry
        return None

    def _build_entry(self, run_id: str, input_query: str, cell: dict, arb_result: dict, decision: dict) -> dict:
        domain_payload = cell.get("domain_payload", {})
        return {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_hash": hashlib.sha256(input_query.encode("utf-8")).hexdigest(),
            "input_query_preview": input_query[:100],
            "alpha_output": {
                "cell_id": cell.get("cell_id"),
                "proposal": cell.get("proposal", {}),
                "uncertainty": cell.get("uncertainty", {}),
            },
            "delta_evaluation": {
                "intent_class": domain_payload.get("intent_type"),
                "risk_score": cell.get("risk_score"),
                "status": cell.get("status"),
                "evaluation": {
                    "adverse_action_potential": domain_payload.get("adverse_action_potential", False),
                    "human_oversight_required": domain_payload.get("human_oversight_required", False),
                    "explainability_required": domain_payload.get("explainability_required", False),
                    "regulatory_article_references": domain_payload.get("regulatory_article_references", []),
                },
            },
            "omega_decision": {
                "decision": decision.get("decision"),
                "variant": decision.get("variant"),
                "reasoning": decision.get("reasoning"),
                "regulatory_reference": decision.get("regulatory_reference"),
                "next_action": decision.get("next_action"),
            },
            "overlay_decisions": [
                {
                    "overlay_name": "ARB",
                    "level_triggered": arb_result.get("level_triggered"),
                    "reason_code": arb_result.get("reason_code"),
                }
            ],
            "regulatory_context": {
                "framework": domain_payload.get("regulatory_framework", "UNKNOWN"),
                "intent_class": domain_payload.get("intent_type", "unknown"),
            },
        }
