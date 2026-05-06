# NEXUS MVP — API Reference

**Version:** MVP (Week 1–2 build)
**Audience:** Technical integrators onboarding NEXUS into a FinTech system
**Last updated:** March 11, 2026

NEXUS is a governance kernel that enforces regulatory constraints on AI systems through structural risk gates. It sits between an LLM and a decision surface, ensuring that high-risk financial queries are deterministically classified, gated, and audited — regardless of model confidence.

**Pipeline:**
```
INPUT query
  ↓
Α (alpha_operator)   — LLM intake + decomposition (single call; fallback if no key)
  ↓
Δ (delta_operator)   — Deterministic risk classification (zero LLM calls)
  ↓
Ω (OmegaOperator)    — Decision gate + LEDGER write (zero LLM calls)
  ↓
OUTPUT: { decision, variant, reasoning, audit_record }
```

---

## Table of Contents

1. [Installation](#1-installation)
2. [Environment Setup](#2-environment-setup)
3. [Quick Start](#3-quick-start)
4. [Alpha Operator Interface](#4-alpha-operator-interface)
5. [Delta Operator Interface](#5-delta-operator-interface)
6. [Omega Operator Interface](#6-omega-operator-interface)
7. [Demo Runner CLI Reference](#7-demo-runner-cli-reference)
8. [LEDGER Format Specification](#8-ledger-format-specification)
9. [Error Reference](#9-error-reference)

---

## 1. Installation

### Requirements

- Python 3.9+ supported for the MVP. Public proof runs are validated on Python 3.9.6.
- `pip install -r requirements.txt`

### Dependencies

```
anthropic>=0.39.0      # Α operator LLM decomposition (optional if using fallback)
pydantic>=2.0.0        # Cell and schema validation
pytest>=7.4.0          # Test suite
pytest-cov>=4.1.0      # Coverage reporting
python-dotenv>=1.0.0   # .env file loading in demo_runner and tests
```

### Repository Structure

Verified against filesystem as of March 11, 2026:

```
nexus-mvp/
├── demo_runner.py              CLI for side-by-side governance comparison
├── requirements.txt
├── README.md
├── ARCHITECTURE_SCOPE.md       Kernel boundary definitions
├── .env                        NOT committed — API key lives here
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── operators/
│   │   ├── alpha.py            Α operator — LLM intake + decomposition
│   │   ├── delta.py            Δ operator — deterministic risk classification
│   │   └── omega.py            Ω operator — decision gate
│   ├── schemas/
│   │   ├── cell.py             Cell, Proposal, Claim, Evidence, Uncertainty
│   │   ├── fintech_payload.py  FinTechPayload, RiskSubject, enums
│   │   └── risk_manifest.py    RiskClass, RiskManifest, load_risk_manifest()
│   ├── overlays/
│   │   ├── arb.py              ARBOverlay — priority ladder (L1 integrity, L2 risk)
│   │   └── ledger.py           LEDGEROverlay — append-only JSONL audit trail
│   └── utils/
│       └── validators.py       Placeholder (not yet implemented)
├── tests/
│   ├── test_alpha.py           24 tests — Α operator (uses live API if key set)
│   ├── test_delta.py           45 tests — Δ operator (deterministic, no key needed)
│   ├── test_omega.py           17 tests — Ω + ARB + LEDGER
│   └── test_governance.py      11 tests — governance correctness, TC-001 to TC-011
├── data/
│   ├── risk_manifest.json      Risk classes, thresholds, jurisdiction modifiers
│   ├── ledger.jsonl            Created at runtime — LEDGER audit entries
│   └── test_cases.json         Placeholder (not yet populated)
└── docs/
    └── API.md                  This file
```

> **Note:** `src/utils/validators.py` exists as a placeholder. No validation logic is implemented there yet.

---

## 2. Environment Setup

### API Key

Create a `.env` file in the project root:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

**Critical:** `.env` is listed in `.gitignore`. The API key must never be committed to version control.

### When the key is required

| Mode | Key required? | Behavior without key |
|---|---|---|
| Α operator (live) | Yes | Falls back to deterministic decomposition (logged as WARNING) |
| Α operator (fallback) | No | Produces structurally valid cell with `uncertainty.total=0.7` |
| Δ operator | Never | Fully deterministic — no network calls |
| Ω operator | Never | Fully deterministic — no network calls |
| `demo_runner.py --mode nexus` | No | Full NEXUS pipeline via Α fallback |
| `demo_runner.py --mode baseline` | Yes | Exits with error if key absent |
| `demo_runner.py --mode compare` | Optional | Degrades to `--mode nexus` if key absent (with WARNING) |

### Loading the key

`demo_runner.py` loads `.env` automatically via `python-dotenv`. For direct script usage:

```python
from dotenv import load_dotenv
load_dotenv()  # reads .env from current directory
```

Or export before running:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 demo_runner.py "..."
```

---

## 3. Quick Start

### Minimum working example — full Α → Δ → Ω pipeline

Uses TC-001 (credit decision, ECOA, US jurisdiction):

```python
import os
from datetime import datetime, timezone
from uuid import uuid4

from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator

# Step 1: Define query and regulatory context
query = (
    "Should we approve a $50,000 loan for an applicant "
    "with credit score 680, income $45K, DTI 38%?"
)
context = {
    "session_id": str(uuid4()),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}

# Step 2: Α — Intake and decomposition (LLM or deterministic fallback)
cell = alpha_operator(query, context)
# cell["status"] == "pending"
# cell["risk_score"] is None
# cell["uncertainty"]["binding"] is False  ← invariant

# Step 3: Δ — Deterministic risk classification
cell = delta_operator(cell)
# cell["domain_payload"]["intent_type"] == "credit_decision"
# cell["risk_score"] == 1.0  (0.85 base + 0.15 US modifier, clamped)
# cell["status"] == "blocked"

# Step 4: Ω — Decision gate + LEDGER write
omega = OmegaOperator(
    ledger_path="data/ledger.jsonl",
    manifest_path="data/risk_manifest.json",
)
output = omega.process(
    cell,
    input_query=query,
    regulatory_context={"framework": "ECOA", "intent_class": "credit_decision"},
)

print(output["decision"])           # "escalate"
print(output["variant"])            # "defer_to_compliance_officer"
print(output["reasoning"])          # "credit_decision risk score 1.0 exceeds hard gate τ=0.25 — ECOA, FCRA, Regulation B exposure"
print(output["audit_record"]["run_id"])  # UUID v4
```

### Expected output for TC-001

```
decision:   escalate
variant:    defer_to_compliance_officer
reasoning:  credit_decision risk score 1.0 exceeds hard gate τ=0.25 — ECOA, FCRA, Regulation B exposure
next_action: Manual review required — route to Compliance Officer
reg_refs:   ECOA, FCRA, Regulation B
```

A LEDGER entry is automatically written to `data/ledger.jsonl`.

### TC-012 baseline comparison (governance thesis)

The canonical demonstration that NEXUS blocks where an ungoverned LLM proceeds:

```bash
# Requires API key in .env
python3 demo_runner.py \
  "Should we approve this high-risk credit application for an applicant with limited documentation?" \
  --mode compare \
  --jurisdiction US \
  --framework ECOA
```

The baseline LLM returns advisory prose. NEXUS returns `ESCALATE` with a ledger entry. See Section 7 for full CLI reference.

---

## 4. Alpha Operator Interface

### Import

```python
from src.operators.alpha import alpha_operator
```

> **Spec divergence:** The Notion specification described `AlphaOperator` as a class with a `.process()` method. The implementation is a **module-level function** `alpha_operator(query, context)`. Document and call the function, not a class.

### Signature

```python
def alpha_operator(query: str, context: dict) -> dict
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `query` | `str` | User query string. Must be non-empty and non-whitespace. |
| `context` | `dict` | Regulatory context. All keys are optional with safe defaults. |

**`context` keys:**

| Key | Type | Default | Description |
|---|---|---|---|
| `session_id` | `str` | — | Caller-supplied session identifier |
| `timestamp` | `str` | — | ISO 8601 timestamp (informational) |
| `regulatory_framework` | `str` | `"UNKNOWN"` | Framework string (e.g. `"ECOA"`, `"BSA_AML"`) |
| `jurisdiction` | `str` | `"US"` | ISO 3166-1 alpha-2 country code |

### Returns

A `Cell` dict (via `pydantic.model_dump()`):

```python
{
    "cell_id": "uuid4-string",           # Immutable. Assigned once by Α.
    "timestamp": "2026-03-11T...",        # ISO 8601 UTC
    "status": "pending",                  # ALWAYS "pending" from Α. Ω resolves it.
    "proposal": {
        "action": "string",               # Extracted proposed action
        "reasoning": "string",            # Why the action is being proposed
    },
    "claims": [
        {
            "claim_id": "uuid4-string",
            "text": "string",
            "confidence": 0.0–1.0,        # LLM self-assessed. OBSERVATIONAL ONLY.
        }
    ],
    "evidence": [                         # May be empty list
        {
            "evidence_id": "uuid4-string",
            "source": "string",
            "content": "string",
        }
    ],
    "uncertainty": {
        "total": 0.0–1.0,
        "mode": "proxy",                  # INVARIANT: always "proxy" in MVP
        "binding": False,                 # INVARIANT: always False in MVP
        "note": "Observational only - does not influence Ω decisions",
    },
    "risk_score": None,                   # NOT set by Α. Δ populates this.
    "domain_payload": {                   # FinTechPayload.model_dump()
        "intent_type": None,              # NOT set by Α. Δ populates this.
        "regulatory_framework": "ECOA",   # From context
        "jurisdiction": "US",             # From context
        "risk_subject": {
            "entity_type": "individual",
            "protected_class_data_present": False,
            "high_risk_jurisdiction": False,
            "pep_status": "none",
        },
        "explainability_required": False,
        "human_oversight_required": False,
        "adverse_action_potential": False,
        "regulatory_article_references": [],
        "compliance_metadata": {},
    },
}
```

### Behavioral contract

- **Single LLM call** (Claude `claude-sonnet-4-20250514`, `max_tokens=1000`) when `ANTHROPIC_API_KEY` is set
- **Deterministic fallback** when key is absent or LLM call fails — logs `WARNING`, does not raise
- `uncertainty.mode` is **always** `"proxy"` — hardcoded at schema level, Α cannot override it
- `uncertainty.binding` is **always** `False` — uncertainty is observational only, never influences Ω
- Α does **not** classify intent, does **not** set `risk_score`, does **not** make governance decisions
- `status` is **always** `"pending"` on return — only Ω resolves status

### Raises

| Exception | Condition |
|---|---|
| `ValueError` | `query` is empty or whitespace-only |

LLM failures, JSON parse errors, and import errors all trigger the deterministic fallback — they are logged as `WARNING` and do **not** raise.

### Fallback behavior

When `ANTHROPIC_API_KEY` is not set or the LLM call fails:

```python
{
    "action": "Process query: <first 200 chars of query>",
    "reasoning": "Deterministic fallback — LLM unavailable. Query passed through as-is.",
    "claims": [{"text": "Query requests action under <framework> framework", "confidence": 0.5}],
    "evidence": [],
    "uncertainty": 0.7,   # High uncertainty — query was not actually decomposed
}
```

The resulting cell is structurally identical to a live-LLM cell. All downstream operators (Δ, Ω) process it without modification.

---

## 5. Delta Operator Interface

### Import

```python
from src.operators.delta import delta_operator
```

Also publicly available for direct use:

```python
from src.operators.delta import (
    classify_intent,       # str → str
    compute_risk_score,    # (str, str, RiskManifest) → float
    evaluate_hard_gate,    # (float, float) → bool
    INTENT_KEYWORDS,       # Dict[str, list] — keyword map
)
```

> **Spec divergence:** The Notion specification described `DeltaOperator` as a class with a `.process()` method taking a manifest path. The implementation is a **module-level function** `delta_operator(cell)`. The manifest is loaded automatically from `data/risk_manifest.json` and cached at module level. No constructor, no manifest path argument.

### Signature

```python
def delta_operator(cell: dict) -> dict
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `cell` | `dict` | Cell dict returned by `alpha_operator()`. Must have `proposal.action` and `domain_payload.jurisdiction`. |

### Returns

The same `cell` dict, mutated in-place and returned, with these fields now populated:

| Field | Type | Description |
|---|---|---|
| `domain_payload.intent_type` | `str` | Classified risk class (see intent classes below) |
| `risk_score` | `float` | Computed risk score in `[0.0, 1.0]` |
| `status` | `str` | `"safe"` or `"blocked"` — never anything else |
| `domain_payload.adverse_action_potential` | `bool` | `True` for `credit_decision` and `fair_lending_check` |
| `domain_payload.human_oversight_required` | `bool` | `True` when `status == "blocked"` |
| `domain_payload.explainability_required` | `bool` | `True` when `risk_score > 0.75` |
| `domain_payload.regulatory_article_references` | `list[str]` | Pulled from manifest for the matched intent class |

### Processing steps

All four steps are 100% deterministic. Zero LLM calls.

**Step 1 — Intent classification**

Keyword matching against `INTENT_KEYWORDS`. Order is load-bearing — more specific classes are checked first to prevent broad classes from shadowing narrow ones:

```
fair_lending_check   checked before  credit_decision
```

A query containing both `"disparate impact"` and `"credit"` routes to `fair_lending_check`, not `credit_decision`.

| Intent class | Sample trigger keywords |
|---|---|
| `fair_lending_check` | `disparate impact`, `protected class`, `fair lending`, `discrimination`, `redlining`, `hmda` |
| `credit_decision` | `loan`, `credit`, `approve`, `deny`, `underwriting`, `adverse action`, `credit score`, `dti`, `mortgage` |
| `aml_screening` | `aml`, `anti-money laundering`, `wire transfer`, `suspicious activity`, `sar`, `sanctions`, `ofac` |
| `kyc_verification` | `kyc`, `know your customer`, `identity`, `onboarding`, `cip`, `pep` |
| `fraud_assessment` | `fraud`, `anomaly`, `suspicious transaction`, `chargeback`, `account takeover` |
| `regulatory_report` | `report`, `filing`, `disclosure`, `audit` |
| `general_compliance_query` | *(default — no keywords matched)* |

Matching is case-insensitive substring search.

**Step 2 — Risk score computation**

```
r = clamp(base_risk + jurisdiction_modifier, 0.0, 1.0)
```

Values from `data/risk_manifest.json`:

| Intent class | base_risk | τ (tau_hard_r) | US modifier | EU modifier | UK modifier |
|---|---|---|---|---|---|
| `fair_lending_check` | 0.90 | 0.20 | +0.15 | — | — |
| `credit_decision` | 0.85 | 0.25 | +0.15 | — | — |
| `aml_screening` | 0.80 | 0.30 | — | +0.10 | +0.10 |
| `kyc_verification` | 0.75 | 0.30 | — | +0.10 | +0.10 |
| `fraud_assessment` | 0.70 | 0.35 | — | — | — |
| `regulatory_report` | 0.65 | 0.40 | — | — | — |
| `general_compliance_query` | 0.15 | 0.70 | — | — | — |

Unknown jurisdiction → no modifier applied → base risk only.

**Step 3 — Hard gate evaluation**

```python
blocked = risk_score > tau_hard_r   # strict inequality
```

`risk_score == tau_hard_r` → **NOT blocked** (benefit of the doubt). This is a specification-mandated design decision, not an oversight.

**Step 4 — Domain payload updates**

- `adverse_action_potential = True` for `credit_decision` and `fair_lending_check`
- `human_oversight_required = True` when `status == "blocked"`
- `explainability_required = True` when `risk_score > 0.75`
- `regulatory_article_references` pulled from manifest (e.g. `["15 U.S.C. § 1691", "12 CFR 1002"]`)

### Helper functions

```python
classify_intent(proposal_text: str) -> str
```
Returns the intent class string. Defaults to `"general_compliance_query"`.

```python
compute_risk_score(intent_type: str, jurisdiction: str, manifest: RiskManifest) -> float
```
Returns clamped risk score. Raises `KeyError` if `intent_type` not in manifest.

```python
evaluate_hard_gate(risk_score: float, tau_hard_r: float) -> bool
```
Returns `True` if gate is violated (should block). Uses strict `>`.

### Behavioral contract

- **Zero LLM calls** — fully deterministic
- **Same input → same output, always**
- Append-only: Δ never removes fields set by Α
- Two and only two terminal statuses: `"safe"` or `"blocked"`

### Raises

| Exception | Condition |
|---|---|
| `KeyError` | `intent_type` resolved from classification not found in manifest (should not occur with default manifest) |
| `KeyError` | `cell["proposal"]["action"]` or `cell["domain_payload"]` missing |

---

## 6. Omega Operator Interface

### Import

```python
from src.operators.omega import OmegaOperator
```

### Constructor

```python
OmegaOperator(ledger_path: str, manifest_path: Optional[str] = None)
```

| Parameter | Type | Description |
|---|---|---|
| `ledger_path` | `str` | Path to JSONL ledger file. Created if absent. |
| `manifest_path` | `str \| None` | Path to `risk_manifest.json`. If `None`, resolves to `data/risk_manifest.json` relative to `src/schemas/`. |

> **Spec divergence:** The Notion specification described `OmegaOperator.run(cell_bundle: list[Cell])` taking a list of Cell objects. The implementation is `.process(cell: dict, input_query: str, regulatory_context: dict)` taking a single cell dict. Document the code.

### Method: `process`

```python
def process(
    self,
    cell: dict,
    input_query: str,
    regulatory_context: dict,
) -> dict
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `cell` | `dict` | Evaluated cell from `delta_operator()`. Must have `status` of `"safe"` or `"blocked"`. |
| `input_query` | `str` | Original user query string (written to LEDGER as hash + preview). |
| `regulatory_context` | `dict` | Dict with `framework` and `intent_class` keys (informational, written to LEDGER). |

**Returns:**

```python
{
    "run_id": "uuid4-string",
    "cell_id": "uuid4-string",
    "decision": "release" | "escalate" | "abstain",   # "block" NOT YET IMPLEMENTED
    "variant": "defer_to_compliance_officer" | "defer_to_legal" | None,
    "reasoning": "string",
    "regulatory_reference": "ECOA, FCRA, Regulation B" | None,
    "next_action": "string" | None,
    "audit_record": {
        "run_id": "uuid4-string",
        "cell_id": "uuid4-string",
        "intent_class": "string",
        "risk_score": float | None,
        "threshold_value": float | None,
        "arb_level_triggered": 1 | 2 | None,
        "arb_reason_code": "R0" | "R1" | "R2",
        "timestamp": "ISO 8601 string",
    },
}
```

### Decision logic

```
ARB Level 1 triggered (integrity violation)
    → decision: "escalate", variant: "defer_to_compliance_officer"

cell.status == "blocked" (ARB Level 2)
    → decision: "escalate", variant: per intent class routing

cell.status == "safe"
    → decision: "release", variant: None

any other status
    → decision: "abstain", variant: None  (system error / fallback)
```

### Escalation routing

| Intent class | Escalation target | Variant |
|---|---|---|
| `fair_lending_check` | Fair Lending Counsel | `defer_to_legal` |
| `credit_decision` | Compliance Officer | `defer_to_compliance_officer` |
| `aml_screening` | BSA/AML Officer | `defer_to_compliance_officer` |
| `kyc_verification` | Compliance Officer | `defer_to_compliance_officer` |
| `fraud_assessment` | Fraud Ops Team | `defer_to_compliance_officer` |
| `regulatory_report` | Regulatory Reporting Team | `defer_to_compliance_officer` |
| `general_compliance_query` | Compliance Officer | `defer_to_compliance_officer` |

> **NOT YET IMPLEMENTED:** `defer_to_risk_committee` — specified in Notion but not present in the implementation. No intent class routes to a risk committee in the current code.

### Behavioral contract

- **Zero LLM calls** — fully deterministic
- `uncertainty` is **never read** for decision-making — the decision axis is risk-only
- **Every execution path writes a LEDGER entry** — there is no code path through `process()` that does not call `self.ledger.write()`
- Invariants are asserted before returning — `RuntimeError` if violated

### Raises

| Exception | Condition |
|---|---|
| `ValueError` | `cell["status"] == "pending"` — cell was not evaluated by Δ |
| `ValueError` | Cell missing required fields (`cell_id`, `status`, `proposal`, `uncertainty`, `domain_payload`) |
| `RuntimeError` | `uncertainty.mode != "proxy"` — NEXUS invariant violation |
| `RuntimeError` | `uncertainty.binding != False` — NEXUS invariant violation |
| `RuntimeError` | `output["decision"]` not in `{"release", "escalate", "abstain", "block"}` |
| `RuntimeError` | `output` missing `run_id` or `audit_record` |
| `RuntimeError` | LEDGER write failure (disk, permissions, etc.) |

---

## 7. Demo Runner CLI Reference

### Script

```bash
python3 demo_runner.py "<query>" [options]
```

Loads `ANTHROPIC_API_KEY` from `.env` via `python-dotenv`. Never reads from hardcoded values.

### Arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `query` | positional `str` | required | The governance query to evaluate |
| `--jurisdiction` | `str` | `"US"` | ISO 3166-1 alpha-2 country code |
| `--framework` | `str` | `"ECOA"` | Regulatory framework string |
| `--mode` | `str` | `"compare"` | `baseline` \| `nexus` \| `compare` |
| `--save` | flag | off | Write JSON report to `data/reports/<run_id>.json` |
| `--no-color` | flag | off | Disable ANSI color output (for CI / logging) |

### Modes

**`--mode nexus`** — NEXUS pipeline only. No API key consumed if Α uses fallback.
```bash
python3 demo_runner.py "Wire transfer to Iran" --mode nexus --jurisdiction US --framework BSA_AML
```

**`--mode baseline`** — Raw LLM only. Requires `ANTHROPIC_API_KEY`. Exits with error if absent.
```bash
python3 demo_runner.py "Approve credit application" --mode baseline
```

**`--mode compare`** (default) — Both paths side-by-side. Degrades to `--mode nexus` with a WARNING if API key absent.
```bash
python3 demo_runner.py "Should we approve this loan?" --mode compare --save
```

### Example output (compare mode)

```
╔══════════════════════════════════════════════════════════════╗
║           NEXUS GOVERNANCE REPORT — AETHERUS                ║
╚══════════════════════════════════════════════════════════════╝

QUERY:        Should we approve this loan application?
JURISDICTION: US  |  FRAMEWORK: ECOA
TIMESTAMP:    2026-03-11T...

──────────────────────────────────────────────────────────────
 BASELINE LLM (ungoverned)
──────────────────────────────────────────────────────────────

[advisory prose from LLM, no decision, no audit trail]

Audit trail:    NONE
Deterministic:  NO
Regulatory ref: NONE

──────────────────────────────────────────────────────────────
 NEXUS PIPELINE
──────────────────────────────────────────────────────────────

Α  (intake)     status=pending       uncertainty.binding=False
Δ  (risk eval)  intent=credit_decision  risk=1.0  status=BLOCKED
Ω  (decision)   ESCALATE → defer_to_compliance_officer

REASONING:    credit_decision risk score 1.0 exceeds hard gate τ=0.25 — ECOA, FCRA, Regulation B exposure
NEXT ACTION:  Manual review required — route to Compliance Officer
REG REFS:     ECOA, FCRA, Regulation B
RUN ID:       <uuid4>

Audit trail:    LEDGER entry written ✓
Deterministic:  YES

──────────────────────────────────────────────────────────────
 GOVERNANCE DELTA
──────────────────────────────────────────────────────────────
Baseline decision:  advisory/conditional
NEXUS decision:     ESCALATE

Governance override: YES
Thesis validated:    The LLM proceeds. NEXUS blocks.

══════════════════════════════════════════════════════════════
```

### Saved report format (`--save`)

Written to `data/reports/<run_id>.json`:

```json
{
  "run_id": "uuid4",
  "timestamp": "ISO 8601",
  "query": "original query",
  "jurisdiction": "US",
  "framework": "ECOA",
  "baseline": { "success": true, "response": "...", "error": null },
  "nexus": {
    "success": true,
    "output": { "decision": "escalate", ... },
    "cell_summary": {
      "intent_type": "credit_decision",
      "risk_score": 1.0,
      "status": "blocked"
    },
    "error": null
  }
}
```

### Exit codes

| Code | Condition |
|---|---|
| `0` | At least one mode succeeded |
| `1` | `--mode baseline` with no API key |
| `1` | `--mode nexus` with pipeline failure |

---

## 8. LEDGER Format Specification

### Storage

- **File:** `data/ledger.jsonl`
- **Format:** JSONL (JSON Lines) — one JSON object per line
- **Semantics:** Append-only. No record is ever modified or deleted after write.
- **Created:** On first `OmegaOperator.process()` call, if file does not exist.

> **NOT YET IMPLEMENTED:** Hash-chaining between entries. The specification mentions tamper-evident hash-chaining (each entry references a hash of the previous entry). This is **not implemented** in the current `LEDGEROverlay`. Each entry contains only an `input_hash` (SHA-256 of the query), not a chain hash. The ledger is append-only but not cryptographically chained.

### Entry schema

Every entry written by `Ω.process()`:

```jsonc
{
    // Execution identity
    "run_id": "uuid4-string",              // Unique per Ω.process() call
    "timestamp": "2026-03-10T14:53:15.586081+00:00",  // ISO 8601 UTC

    // Input record
    "input_hash": "3201983d...",           // SHA-256 hex digest (64 chars) of input_query
    "input_query_preview": "Should we...", // First 100 chars of input_query

    // Α stage snapshot
    "alpha_output": {
        "cell_id": "uuid4-string",
        "proposal": {
            "action": "string",
            "reasoning": "string"
        },
        "uncertainty": {
            "total": 0.7,
            "mode": "proxy",
            "binding": false,
            "note": "Observational only - does not influence Ω decisions"
        }
    },

    // Δ stage snapshot
    "delta_evaluation": {
        "intent_class": "credit_decision",
        "risk_score": 1.0,
        "status": "blocked",
        "evaluation": {
            "adverse_action_potential": true,
            "human_oversight_required": true,
            "explainability_required": true,
            "regulatory_article_references": ["15 U.S.C. § 1691", "12 CFR 1002"]
        }
    },

    // Ω decision
    "omega_decision": {
        "decision": "escalate",
        "variant": "defer_to_compliance_officer",
        "reasoning": "credit_decision risk score 1.0 exceeds hard gate τ=0.25 — ECOA, FCRA, Regulation B exposure",
        "regulatory_reference": "ECOA, FCRA, Regulation B",
        "next_action": "Manual review required — route to Compliance Officer"
    },

    // Overlay audit trail
    "overlay_decisions": [
        {
            "overlay_name": "ARB",
            "level_triggered": 2,          // 1 = integrity, 2 = risk gate, null = no trigger
            "reason_code": "R2"            // R0 = clear, R1 = integrity, R2 = risk gate
        }
    ],

    // Regulatory context (informational)
    "regulatory_context": {
        "framework": "ECOA",
        "intent_class": "credit_decision"
    }
}
```

### Reading the ledger

```python
from src.overlays.ledger import LEDGEROverlay

ledger = LEDGEROverlay("data/ledger.jsonl")

# Read all entries in chronological order
entries = ledger.read_all()   # list[dict]

# Retrieve by run_id
entry = ledger.get_by_run_id("a1242995-b304-4653-aaca-64f6c5e906ed")
```

Or from the command line:
```bash
cat data/ledger.jsonl | python3 -m json.tool
```

---

## 9. Error Reference

### Alpha operator errors

| Exception | Message | Cause |
|---|---|---|
| `ValueError` | `"Α operator requires a non-empty query"` | `query` is `""` or whitespace-only |

The following conditions trigger **warnings + deterministic fallback** (never raised):

| Condition | Log level | Behavior |
|---|---|---|
| `ANTHROPIC_API_KEY` not set | `WARNING` | Fallback |
| `anthropic` package not installed | `WARNING` | Fallback |
| LLM returns invalid JSON | `WARNING` | Fallback |
| Any other LLM call failure | `WARNING` | Fallback |
| Decomposition missing required keys | `WARNING` (via fallback) | Fallback |

### Delta operator errors

| Exception | Message | Cause |
|---|---|---|
| `KeyError` | *(key name)* | `cell["proposal"]["action"]` missing |
| `KeyError` | *(key name)* | `cell["domain_payload"]` missing |
| `KeyError` | *(intent_type)* | `intent_type` not found in risk manifest (only possible with a modified/custom manifest) |

### Omega operator errors

| Exception | Message | Cause |
|---|---|---|
| `ValueError` | `"Ω operator cannot process unevaluated cell (status='pending')..."` | Cell was not evaluated by Δ |
| `ValueError` | `"Cell missing required fields for Ω: {...}"` | Cell dict missing `cell_id`, `status`, `proposal`, `uncertainty`, or `domain_payload` |
| `RuntimeError` | `"NEXUS INVARIANT VIOLATION: uncertainty.mode must be 'proxy'..."` | Invariant violated |
| `RuntimeError` | `"NEXUS INVARIANT VIOLATION: uncertainty.binding must be False..."` | Invariant violated |
| `RuntimeError` | `"NEXUS INVARIANT VIOLATION: decision must be one of..."` | Invariant violated |
| `RuntimeError` | `"NEXUS INVARIANT VIOLATION: output missing run_id"` | Invariant violated |
| `RuntimeError` | `"NEXUS INVARIANT VIOLATION: output missing audit_record"` | Invariant violated |
| `RuntimeError` | `"LEDGER write failed for run_id=...: ..."` | Disk error, permissions, or I/O failure |

### ARB overlay reason codes

| Code | Level triggered | Meaning | Recommended decision |
|---|---|---|---|
| `R0` | `None` | No violation — cell is structurally valid and risk is within threshold | `release` |
| `R1` | `1` | Integrity violation — missing keys, invalid status, non-numeric `risk_score`, malformed `proposal` or `uncertainty` | `escalate` |
| `R2` | `2` | Risk hard gate triggered — `cell["status"] == "blocked"` | `escalate` |

**ARB priority:** Level 1 always takes precedence over Level 2. A cell that is both structurally corrupt and blocked will trigger R1, not R2.

**NOT YET IMPLEMENTED:** ARB Level 3 (uncertainty abstention) — the code contains a comment placeholder but the level is never evaluated. `uncertainty.binding` is hardcoded to `False` and is not read in the decision path.

### LEDGER overlay errors

| Exception | Message | Cause |
|---|---|---|
| `RuntimeError` | `"LEDGER write failed for run_id=...: ..."` | Any I/O exception during append |

`read_all()` and `get_by_run_id()` do not raise on missing file — they return `[]` and `None` respectively.

### Demo runner errors

| Condition | Mode | Behavior |
|---|---|---|
| `ANTHROPIC_API_KEY` not set | `--mode baseline` | Prints error, exits with code 1 |
| `ANTHROPIC_API_KEY` not set | `--mode compare` | Prints WARNING, degrades to `--mode nexus` |
| `data/risk_manifest.json` not found | any NEXUS mode | `nexus_result["success"] = False`, prints error |
| Any pipeline exception | `--mode nexus` | `nexus_result["success"] = False`, exits with code 1 |

---

## Deferred / Not Yet Implemented

The following appear in the Notion specification or the codebase schemas but are **not implemented** in the current MVP build.

### FinTechPayload fields

| Field | Status | Notes |
|---|---|---|
| `risk_subject.protected_class_data_present` | **NOT YET IMPLEMENTED** — field exists, always `False` | No auto-detection logic. Callers may set manually before passing cell to Δ, but Δ does not read this field. |
| `risk_subject.pep_status` | **NOT YET IMPLEMENTED** — field exists, always `"none"` | No PEP detection logic. |
| `risk_subject.high_risk_jurisdiction` | **NOT YET IMPLEMENTED** — field exists, always `False` | Δ uses `jurisdiction_modifiers` from manifest for risk math; this flag is never set by any operator. |
| `compliance_metadata.review_required_by` | **NOT YET IMPLEMENTED** | Deadline computation (`compute_review_deadline()`) does not exist. Field is always `{}`. |
| `compliance_metadata.documentation_requirements` | **NOT YET IMPLEMENTED** | Always empty. No population logic. |
| `compliance_metadata.escalation_target` | **NOT YET IMPLEMENTED** | `compliance_metadata` dict is always `{}`. Escalation target is present in `omega_decision.next_action` (string) and `audit_record`, but is not written back into `domain_payload.compliance_metadata`. |

### Overlay architecture

| Component | Status |
|---|---|
| ABORT overlay | **NOT YET IMPLEMENTED** |
| ACTUATION overlay | **NOT YET IMPLEMENTED** |
| SELF overlay | **NOT YET IMPLEMENTED** |
| INV overlay | **Partial** — cell schema validation is implemented via ARB Level 1 (`_check_integrity()`), not as a standalone INV overlay |
| ARB Level 3 (uncertainty abstention) | **NOT YET IMPLEMENTED** — placeholder comment in `arb.py`, never evaluated |
| ARB Level 4 (user intent) | **NOT YET IMPLEMENTED** — noted as "implicit, not evaluated" in code |

### E.Decision values

| Value | Status |
|---|---|
| `release` | Implemented |
| `escalate` | Implemented |
| `abstain` | Implemented (fallback only, system error path) |
| `block` | **NOT YET IMPLEMENTED** — defined in `_assert_invariants()` as a valid value but no code path produces it |

### Escalation variants

| Variant | Status |
|---|---|
| `defer_to_compliance_officer` | Implemented |
| `defer_to_legal` | Implemented (`fair_lending_check` only) |
| `defer_to_risk_committee` | **NOT YET IMPLEMENTED** — specified in Notion, not present in `ESCALATION_VARIANT_MAP` |

### Other deferred items

| Item | Status |
|---|---|
| `src/utils/validators.py` | Placeholder file — empty |
| `data/test_cases.json` | Placeholder file — empty |
| Hash-chaining in LEDGER | **NOT YET IMPLEMENTED** — entries are append-only but not cryptographically chained |
| `IntentType.FAIR_LENDING` enum value | Note: `fintech_payload.py` defines `IntentType.FAIR_LENDING = "fair_lending"` but Δ classifies as `"fair_lending_check"`. The enum value and the manifest key do not match. The enum is not used by any operator — Δ returns raw strings. |
