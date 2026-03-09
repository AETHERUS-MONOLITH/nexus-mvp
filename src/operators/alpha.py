"""
NEXUS MVP — Α (Alpha) Operator
================================
Intake and decomposition operator for the NEXUS governance kernel.

Α is the ONLY point in the pipeline where LLM inference occurs.
Everything downstream (Δ, Ω) is deterministic. This is by design:
governance decisions must not depend on model confidence.

Behavioral Contract:
    1. Single decomposition: one query → one proposal → one cell
    2. Claims extraction: identify verifiable assertions
    3. Evidence linking: reference supporting data (may be empty for MVP)
    4. Uncertainty recording: populate u field as NON-BINDING (mode="proxy")
    5. NO decision-making: Α does not decide release/block/escalate
    6. Domain payload initialization: known fields from context, rest for Δ

Specification Reference:
    Governance Decision Specification — Α Section
"""

import os
import json
import logging
from typing import Optional

from src.schemas.cell import Cell, Proposal, Claim, Evidence, Uncertainty
from src.schemas.fintech_payload import FinTechPayload, RiskSubject

logger = logging.getLogger(__name__)

DECOMPOSITION_PROMPT = """You are a governance decomposition agent operating within the NEXUS kernel.

Your role is STRICTLY intake decomposition. You do NOT make governance decisions.
You do NOT classify risk. You do NOT recommend approval or denial.

USER QUERY:
{query}

REGULATORY CONTEXT:
Framework: {framework}
Jurisdiction: {jurisdiction}

TASK:
1. Extract the PROPOSED ACTION — what is the query asking the system to do?
2. Provide brief REASONING — why is this action being proposed?
3. Identify CLAIMS — verifiable factual assertions embedded in or implied by the query.
   Each claim needs a confidence score (0.0 = no basis, 1.0 = definitively verifiable).
4. Note EVIDENCE — any data sources or references mentioned. If none, return empty list.
5. Estimate UNCERTAINTY — a single float (0.0 = fully certain, 1.0 = completely uncertain)
   representing how ambiguous or under-specified the query is.

Respond ONLY with valid JSON. No markdown, no commentary, no preamble:
{{
    "action": "<proposed action>",
    "reasoning": "<brief explanation of what is being asked>",
    "claims": [
        {{"text": "<verifiable assertion>", "confidence": <float 0-1>}}
    ],
    "evidence": [
        {{"source": "<data source>", "content": "<evidence text>"}}
    ],
    "uncertainty": <float 0-1>
}}"""


def _call_llm(query: str, context: dict) -> Optional[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — falling back to deterministic decomposition")
        return None

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        prompt = DECOMPOSITION_PROMPT.format(
            query=query,
            framework=context.get("regulatory_framework", "UNKNOWN"),
            jurisdiction=context.get("jurisdiction", "UNKNOWN"),
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[: raw_text.rfind("```")]
            raw_text = raw_text.strip()

        decomposition = json.loads(raw_text)
        _validate_decomposition(decomposition)
        return decomposition

    except ImportError:
        logger.warning("anthropic package not installed — falling back to deterministic decomposition")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON: {e} — falling back to deterministic decomposition")
        return None
    except Exception as e:
        logger.warning(f"LLM call failed: {e} — falling back to deterministic decomposition")
        return None


def _validate_decomposition(d: dict) -> None:
    required_keys = {"action", "reasoning", "claims", "uncertainty"}
    missing = required_keys - set(d.keys())
    if missing:
        raise ValueError(f"Decomposition missing required keys: {missing}")

    if not isinstance(d["claims"], list):
        raise ValueError("claims must be a list")

    if not isinstance(d["uncertainty"], (int, float)):
        raise ValueError("uncertainty must be a number")

    d["uncertainty"] = max(0.0, min(1.0, float(d["uncertainty"])))

    if "evidence" not in d or not isinstance(d["evidence"], list):
        d["evidence"] = []

    for i, claim in enumerate(d["claims"]):
        if "text" not in claim:
            raise ValueError(f"Claim {i} missing 'text' field")
        if "confidence" not in claim:
            claim["confidence"] = 0.5
        claim["confidence"] = max(0.0, min(1.0, float(claim["confidence"])))


def _deterministic_fallback(query: str, context: dict) -> dict:
    return {
        "action": f"Process query: {query[:200]}",
        "reasoning": "Deterministic fallback — LLM unavailable. Query passed through as-is.",
        "claims": [
            {
                "text": f"Query requests action under {context.get('regulatory_framework', 'UNKNOWN')} framework",
                "confidence": 0.5,
            }
        ],
        "evidence": [],
        "uncertainty": 0.7,
    }


def alpha_operator(query: str, context: dict) -> dict:
    """
    Α operator: Intake and decomposition.

    Args:
        query: User query string.
        context: Regulatory context dict with keys:
            - session_id (str)
            - timestamp (str, ISO 8601)
            - regulatory_framework (str)
            - jurisdiction (str, ISO 3166-1 alpha-2)

    Returns:
        Cell as dict (serialized via Pydantic model_dump).

    Raises:
        ValueError: If query is empty.
    """
    if not query or not query.strip():
        raise ValueError("Α operator requires a non-empty query")

    decomposition = _call_llm(query, context)
    if decomposition is None:
        decomposition = _deterministic_fallback(query, context)

    payload = FinTechPayload(
        regulatory_framework=context.get("regulatory_framework", "UNKNOWN"),
        jurisdiction=context.get("jurisdiction", "US"),
    )

    cell = Cell(
        proposal=Proposal(
            action=decomposition["action"],
            reasoning=decomposition["reasoning"],
        ),
        claims=[
            Claim(text=c["text"], confidence=c["confidence"])
            for c in decomposition.get("claims", [])
        ],
        evidence=[
            Evidence(source=e["source"], content=e["content"])
            for e in decomposition.get("evidence", [])
        ],
        uncertainty=Uncertainty(
            total=decomposition.get("uncertainty", 0.5),
        ),
        domain_payload=payload.model_dump(),
    )

    return cell.model_dump()
