#!/usr/bin/env python3
"""Prove stable NEXUS governance decision fields across repeated runs."""

import os
import sys
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator


logging.disable(logging.CRITICAL)


QUERY = (
    "Should we approve a $50,000 loan for an applicant "
    "with credit score 680, income $45K, DTI 38%?"
)
JURISDICTION = "US"
FRAMEWORK = "ECOA"
RUNS = 3


def run_once(ledger_path: str) -> dict:
    context = {
        "session_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regulatory_framework": FRAMEWORK,
        "jurisdiction": JURISDICTION,
    }

    cell = alpha_operator(QUERY, context)
    cell = delta_operator(cell)

    intent = cell["domain_payload"]["intent_type"]
    omega = OmegaOperator(
        ledger_path=ledger_path,
        manifest_path=str(PROJECT_ROOT / "data" / "risk_manifest.json"),
    )
    output = omega.process(
        cell,
        QUERY,
        {"framework": FRAMEWORK, "intent_class": intent},
    )

    return {
        "intent": intent,
        "risk_score": cell["risk_score"],
        "status": cell["status"],
        "decision": output["decision"],
        "variant": output["variant"],
        "reasoning": output["reasoning"],
        "regulatory_reference": output["regulatory_reference"],
    }


def main() -> int:
    # This proof targets deterministic governance behavior. It intentionally
    # excludes timestamp, run_id, UUIDs, and LEDGER append order.
    os.environ.pop("ANTHROPIC_API_KEY", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = str(Path(tmpdir) / "ledger.jsonl")
        results = [run_once(ledger_path) for _ in range(RUNS)]

    baseline = results[0]
    mismatches = [
        {"run": index + 1, "expected": baseline, "actual": result}
        for index, result in enumerate(results[1:], start=1)
        if result != baseline
    ]

    if mismatches:
        print("FAIL: stable decision fields diverged")
        for mismatch in mismatches:
            print(mismatch)
        return 1

    print("PASS: stable decision fields matched across 3 runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
