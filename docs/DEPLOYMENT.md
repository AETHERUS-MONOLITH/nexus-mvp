# NEXUS MVP — Deployment Guide

**Version:** MVP (Week 1–2 build)
**Audience:** Technical operators deploying NEXUS in a FinTech environment
**Last updated:** March 11, 2026

This guide covers system requirements, installation, configuration, operational modes, LEDGER storage, security requirements, known limitations, and troubleshooting for the NEXUS governance kernel.

For API interface documentation, see [`docs/API.md`](./API.md).

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Running in Demo Mode vs. Production Mode](#4-running-in-demo-mode-vs-production-mode)
5. [LEDGER Storage Considerations](#5-ledger-storage-considerations)
6. [Security Requirements](#6-security-requirements)
7. [Known Limitations (MVP Scope)](#7-known-limitations-mvp-scope)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. System Requirements

### Python

Python **3.9+** is supported for the MVP. Public proof runs are validated on Python 3.9.6.

### Operating System

POSIX-compliant environments supported: Linux (Ubuntu 24 tested), macOS. Windows is not tested and not supported in MVP.

### External Dependencies

An **Anthropic API key** is required for:
- Α operator live LLM decomposition (one API call per query)
- `--mode baseline` and `--mode compare` in `demo_runner.py`

Without an API key, the Α operator falls back to deterministic decomposition (rule-based, zero API calls). The full Δ → Ω governance pipeline remains functional. NEXUS governance behavior is not degraded — only the LLM decomposition quality is affected.

### Hardware

No GPU required. No special compute. NEXUS is CPU-only:
- **Α operator:** single API call to Anthropic over the network (network access required for live LLM mode)
- **Δ operator:** pure keyword matching and arithmetic — negligible CPU
- **Ω operator:** dict lookups and file append — negligible CPU

### Disk

Minimal. The LEDGER grows at approximately 1–2 KB per governance decision (JSONL append). Risk manifest is ~2 KB. No database engine required.

---

## 2. Installation

### Step 1: Obtain the repository

```bash
git clone <repository-url> nexus-mvp
cd nexus-mvp
```

Or transfer the project directory to the deployment host via your preferred method.

### Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

**Verified `requirements.txt` contents:**

```
anthropic>=0.39.0      # Α operator LLM decomposition (optional — fallback activates if absent)
pydantic>=2.0.0        # Cell and schema validation (Pydantic v2 required)
pytest>=7.4.0          # Test suite
pytest-cov>=4.1.0      # Coverage reporting
python-dotenv>=1.0.0   # .env file loading in demo_runner.py and tests
```

### Step 3: Verify directory structure

Verified against actual filesystem as of March 11, 2026:

```
nexus-mvp/
├── demo_runner.py               # CLI for governance demos and comparisons
├── requirements.txt
├── README.md
├── .env                         # User creates — NOT in repo (see Section 3)
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── operators/
│   │   ├── __init__.py
│   │   ├── alpha.py             # Α operator: LLM intake + decomposition
│   │   ├── delta.py             # Δ operator: deterministic risk classification
│   │   └── omega.py             # Ω operator: decision gate + LEDGER write
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── cell.py              # Cell, Proposal, Claim, Evidence, Uncertainty models
│   │   ├── fintech_payload.py   # FinTechPayload, RiskSubject, enums
│   │   └── risk_manifest.py     # RiskClass, RiskManifest, load_risk_manifest()
│   ├── overlays/
│   │   ├── __init__.py
│   │   ├── arb.py               # ARB overlay: priority ladder, integrity checks
│   │   └── ledger.py            # LEDGER overlay: append-only audit trail
│   └── utils/
│       ├── __init__.py
│       └── validators.py        # Placeholder (empty in MVP)
├── tests/
│   ├── __init__.py
│   ├── test_alpha.py            # 24 tests — Α operator unit tests
│   ├── test_delta.py            # 45 tests — Δ operator unit tests
│   ├── test_omega.py            # 17 tests — Ω operator unit tests
│   └── test_governance.py       # 11 tests — end-to-end governance correctness
├── data/
│   ├── risk_manifest.json       # Risk class definitions and thresholds
│   ├── ledger.jsonl             # Created at runtime — append-only audit trail
│   ├── test_cases.json          # Placeholder (empty in MVP)
│   └── reports/                 # Created at runtime by --save flag
└── docs/
    ├── API.md
    └── DEPLOYMENT.md            # This file
```

All `__init__.py` files are present in `src/`, `src/operators/`, `src/schemas/`, `src/overlays/`, `src/utils/`, and `tests/`. These are required for Python package resolution.

### Step 4: Run the test suite to verify installation

```bash
pytest tests/ -v --tb=short
```

Expected: **97 tests passing** (24 alpha + 45 delta + 17 omega + 11 governance).

---

## 3. Configuration

### 3a. API Key Setup (`.env` file)

Create a `.env` file in the project root:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

The `.env` file is loaded by `demo_runner.py` via `python-dotenv` at startup. The Α operator reads the key directly from `os.environ.get("ANTHROPIC_API_KEY")`.

**Verify `.env` is excluded from version control:**

```bash
grep ".env" .gitignore
```

Confirmed: `.env` appears in `.gitignore`. It will not be committed.

> **Note:** The `.gitignore` file contains `.env` listed twice (lines 6 and 13) — a duplicate entry from the project initialization sequence. This is harmless but cosmetically redundant.

**Behavior without an API key:**

The Α operator logs a warning and activates its deterministic fallback:
```
WARNING — ANTHROPIC_API_KEY not set — falling back to deterministic decomposition
```

The fallback sets `uncertainty=0.7` and passes the query through as-is with a generic claim. The Δ and Ω stages are unaffected — governance decisions remain fully deterministic.

---

### 3b. Risk Manifest Configuration (`data/risk_manifest.json`)

The risk manifest is the primary governance configuration file. It defines all risk classes, base risk scores, hard gate thresholds, regulatory frameworks, and jurisdiction modifiers.

> ⚠️ **PROVISIONAL VALUES:** All risk scores and thresholds in `risk_manifest.json` are provisional demonstration values. They require sign-off from a qualified Compliance Officer and Regulatory Counsel before any production use. See FinTech Risk Manifest v1.0 — Validation Requirements.

#### Current risk class table

Verified against `data/risk_manifest.json`:

| Risk Class | `base_risk` | `tau_hard_r` | Regulatory Frameworks |
|---|---|---|---|
| `fair_lending_check` | 0.90 | 0.20 | ECOA, Fair Housing Act |
| `credit_decision` | 0.85 | 0.25 | ECOA, FCRA, Regulation B |
| `aml_screening` | 0.80 | 0.30 | BSA_AML, USA PATRIOT Act |
| `kyc_verification` | 0.75 | 0.30 | CIP, OFAC |
| `fraud_assessment` | 0.70 | 0.35 | GLBA, FTC Safeguards |
| `regulatory_report` | 0.65 | 0.40 | Varies |
| `general_compliance_query` | 0.15 | 0.70 | N/A |

#### Adjusting `base_risk` values

Each risk class has a `base_risk` float in `[0.0, 1.0]`. Higher values represent higher inherent regulatory exposure. Changing `base_risk` changes the floor from which jurisdiction modifiers are applied.

Example — reduce AML base risk:
```json
"aml_screening": {
  "base_risk": 0.70,
  ...
}
```

#### Adjusting `tau_hard_r` thresholds

The hard gate fires when `risk_score > tau_hard_r` (strict inequality). `risk_score == tau_hard_r` does **not** trigger a block — the benefit of the doubt applies.

Lower threshold = more aggressive blocking. Current values are intentionally conservative, biased toward false positives (over-escalation) rather than false negatives (missed violations).

Example — tighten the credit decision gate:
```json
"credit_decision": {
  "tau_hard_r": 0.15,
  ...
}
```

#### Adding jurisdiction modifiers

Each risk class has a `jurisdiction_modifiers` dict mapping ISO 3166-1 alpha-2 country codes to additive floats. The final risk score is computed as:

```
risk_score = clamp(base_risk + jurisdiction_modifier, 0.0, 1.0)
```

Example — add a Singapore modifier to AML screening:
```json
"aml_screening": {
  "jurisdiction_modifiers": {
    "EU": 0.10,
    "UK": 0.10,
    "SG": 0.05
  }
}
```

Current jurisdiction modifiers in the manifest:
- `fair_lending_check`: US +0.15
- `credit_decision`: US +0.15
- `aml_screening`: EU +0.10, UK +0.10
- `kyc_verification`: EU +0.10, UK +0.10
- `fraud_assessment`, `regulatory_report`, `general_compliance_query`: no modifiers

#### Adding new risk classes

1. Add a new key to `risk_classes` in `data/risk_manifest.json` with the required fields:
   ```json
   "new_intent_class": {
     "base_risk": 0.60,
     "tau_hard_r": 0.40,
     "regulatory_framework": ["RegulationX"],
     "article_references": ["12 CFR 1234"],
     "jurisdiction_modifiers": {}
   }
   ```

2. Add corresponding keywords to `INTENT_KEYWORDS` in `src/operators/delta.py`:
   ```python
   "new_intent_class": [
       "keyword1", "keyword2",
   ],
   ```

3. **Keyword ordering is load-bearing.** More specific intent classes must appear before broader ones. `fair_lending_check` must precede `credit_decision` because "disparate impact" keywords would otherwise match `credit_decision`'s broader "credit" keyword first. Apply the same specificity discipline to any new class.

---

### 3c. Other Configuration

**LEDGER path:**
The default path is `data/ledger.jsonl` relative to the project root (hardcoded in `demo_runner.py`). The `OmegaOperator` constructor accepts a custom path:
```python
omega = OmegaOperator(ledger_path="/var/log/nexus/ledger.jsonl")
```

**LLM model:**
The Α operator uses `claude-sonnet-4-20250514`. This is hardcoded in `src/operators/alpha.py` at the `client.messages.create(model=...)` call. To change the model, edit that string directly.

**Decomposition prompt:**
The LLM prompt is defined as `DECOMPOSITION_PROMPT` at the top of `src/operators/alpha.py`. It can be customized to tune decomposition behavior for domain-specific vocabulary or jurisdictions. Do not remove the `{{JSON only}}` constraint — the Α operator parses the response as raw JSON.

---

## 4. Running in Demo Mode vs. Production Mode

### Demo Mode (`demo_runner.py`)

The demo runner is the primary external-facing interface for customer pilots and regulatory reviewers. It wraps the three-operator pipeline in a CLI with colored terminal output and optional report saving.

**Basic usage:**

```bash
# NEXUS pipeline only (no API key required if Α fallback activates)
python3 demo_runner.py "Approve a mortgage for a protected class applicant" --mode nexus

# Baseline LLM only (requires API key)
python3 demo_runner.py "Approve a credit application" --mode baseline

# Side-by-side comparison (requires API key; degrades to nexus-only if key absent)
python3 demo_runner.py "Wire transfer to sanctioned jurisdiction" --mode compare --jurisdiction US --framework BSA_AML

# Save full report to data/reports/<run_id>.json
python3 demo_runner.py "Approve this loan" --mode compare --save

# Disable terminal color (for CI, log capture, or non-ANSI terminals)
python3 demo_runner.py "Approve this loan" --mode nexus --no-color
```

**All arguments:**

| Argument | Default | Description |
|---|---|---|
| `query` | (required) | The governance query to evaluate |
| `--jurisdiction` | `US` | ISO 3166-1 alpha-2 country code |
| `--framework` | `ECOA` | Regulatory framework string |
| `--mode` | `compare` | `baseline`, `nexus`, or `compare` |
| `--save` | off | Write JSON report to `data/reports/<run_id>.json` |
| `--no-color` | off | Disable ANSI color codes |

**Mode behavior:**

- `compare` (default): runs both baseline LLM and NEXUS pipeline. If API key is absent, demotes automatically to `nexus` mode with a warning.
- `nexus`: NEXUS pipeline only. API key not required if Α fallback activates.
- `baseline`: raw LLM call only. Requires API key. Exits with code 1 if key is not set.

---

### Production Mode (direct Python integration)

No UI exists in the MVP. Production mode means direct Python imports and sequential operator calls.

**Import pattern:**

```python
from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator
```

**Full pipeline example:**

```python
from uuid import uuid4
from datetime import datetime, timezone
from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator

query = "Approve credit application for applicant 00123"
context = {
    "session_id": str(uuid4()),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "regulatory_framework": "ECOA",
    "jurisdiction": "US",
}

# Stage 1: Α — intake and decomposition
cell = alpha_operator(query, context)

# Stage 2: Δ — deterministic risk classification
cell = delta_operator(cell)

# Stage 3: Ω — decision gate and LEDGER write
omega = OmegaOperator(
    ledger_path="/var/log/nexus/ledger.jsonl",
    manifest_path="/etc/nexus/risk_manifest.json",
)
output = omega.process(cell, query, {"framework": "ECOA", "intent_class": cell["domain_payload"]["intent_type"]})

print(output["decision"])       # "release" or "escalate" or "abstain"
print(output["reasoning"])
print(output["audit_record"])
```

For full interface documentation, see [`docs/API.md`](./API.md).

**Data handling distinction:**

| | Demo mode | Production mode |
|---|---|---|
| LEDGER location | `data/ledger.jsonl` (project dir) | Custom `ledger_path` passed to `OmegaOperator` |
| Reports | `data/reports/<run_id>.json` | Not generated (integrator responsibility) |
| API key loading | `load_dotenv()` in `demo_runner.py` | Integrator sets `ANTHROPIC_API_KEY` in environment |

In production, point `ledger_path` to a persistent, backed-up storage location outside the project directory. See [Section 5](#5-ledger-storage-considerations).

---

## 5. LEDGER Storage Considerations

### Location and format

- **Default location:** `data/ledger.jsonl` (relative to project root)
- **Configurable:** `OmegaOperator(ledger_path="/path/to/ledger.jsonl")`
- **Format:** JSONL — one JSON object per line, UTF-8 encoded

Each entry contains:

| Field | Type | Description |
|---|---|---|
| `run_id` | UUID string | Unique identifier for this governance execution |
| `timestamp` | ISO 8601 string | UTC timestamp of Ω execution |
| `input_hash` | hex string | SHA-256 of the raw input query |
| `input_query_preview` | string | First 100 characters of the input query |
| `alpha_output` | object | Cell ID, proposal, uncertainty snapshot from Α |
| `delta_evaluation` | object | Intent class, risk score, cell status, risk flags |
| `omega_decision` | object | Decision, variant, reasoning, regulatory reference, next action |
| `overlay_decisions` | array | ARB level triggered and reason code |
| `regulatory_context` | object | Framework and intent class |

### Immutability guarantee

The LEDGER is **append-only by design.** `LEDGEROverlay.write()` opens the file in append mode (`"a"`). There are no update, modify, or delete methods in `src/overlays/ledger.py`. Write failures raise `RuntimeError` — they are never silently swallowed.

### Hash-chaining — NOT YET IMPLEMENTED

> ⚠️ **NOT YET IMPLEMENTED:** Hash-chaining of LEDGER entries (each entry containing the cryptographic hash of the previous entry to form a tamper-evident chain) is not implemented in the current MVP. Each entry contains only a standalone SHA-256 hash of its own input query (`input_hash`). There is no chain linking entries together. Tamper detection across the full LEDGER requires an external integrity verification mechanism in production deployments.

### Backup recommendations

The LEDGER is the compliance audit trail. Loss of LEDGER data constitutes a compliance gap.

Recommended backup approach:
- **Minimum:** daily backup of `ledger.jsonl` to immutable storage (AWS S3 with Object Lock, write-once NAS, or equivalent)
- **For production:** log rotation — new LEDGER file per day or month to manage file size and simplify backup scope
- NEXUS does not implement log rotation. Rotation is the integrator's responsibility.

### Retention policy

FinTech audit trail retention requirements vary by regulation:

| Regulation | Minimum retention |
|---|---|
| BSA/AML | 5 years (31 CFR 1010.430) |
| ECOA (adverse action) | 25 months |
| FCRA | Variable by record type |
| EU GDPR | Purpose-limited; defined per data category |

**Recommendation:** retain all LEDGER entries for a minimum of **7 years** to satisfy overlapping BSA, ECOA, and FCRA requirements. Consult Regulatory Counsel for jurisdiction-specific requirements.

NEXUS does not auto-purge. Retention management and deletion scheduling are the integrator's responsibility.

---

## 6. Security Requirements

### API key management

- Store the Anthropic API key in `.env` only — never in source code, never in command-line arguments, never in log output
- `.env` is confirmed in `.gitignore` — it will not be committed
- For production deployments: use a secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager, etc.) rather than a `.env` file. Inject the key into the process environment at startup

### `.gitignore` gaps — action required

The current `.gitignore` excludes `.env` but does **not** exclude `data/ledger.jsonl` or `data/reports/`. These files contain:
- `ledger.jsonl`: raw input query previews (may contain applicant names, account numbers, credit scores) and all governance decisions
- `data/reports/`: full pipeline traces including complete query text

**Before committing to any shared or remote repository, add these exclusions:**

```bash
echo "data/ledger.jsonl" >> .gitignore
echo "data/reports/" >> .gitignore
```

### Access control

For production deployments, apply file-level access controls:

| Resource | Recommended access |
|---|---|
| `data/ledger.jsonl` | Read: compliance-authorized personnel only. Write: append-only for NEXUS process user |
| `data/risk_manifest.json` | Read: NEXUS process. Write: admin-only with change control |
| `.env` (or secrets) | Read: NEXUS process only |
| `data/reports/` | Read: compliance-authorized personnel only |

Unauthorized modification of `data/risk_manifest.json` constitutes a governance bypass — it directly controls which queries are blocked and which are released.

### Data handling for FinTech

Queries processed by NEXUS **may contain PII**: applicant names, credit scores, account numbers, dates of birth, SSNs.

LEDGER entries store `input_query_preview` (the first 100 characters of the raw query). This preview may contain PII.

For production deployments:
- **Encrypt LEDGER at rest.** Use filesystem encryption (LUKS, AWS EBS encryption) or application-level encryption before writing entries
- **Restrict LEDGER access** to compliance-authorized personnel with documented audit log of access
- `demo_runner.py --save` writes full query text and the complete pipeline trace to `data/reports/<run_id>.json`. Apply the same PII protections to this directory

---

## 7. Known Limitations (MVP Scope)

### Architectural limitations

- **Single jurisdiction per query.** No cross-border risk aggregation. If a query spans multiple jurisdictions, only the jurisdiction passed in `context["jurisdiction"]` is applied.
- **Single cell per Ω execution.** Multi-cell bundles are not supported. The Ω operator processes one cell dict per `.process()` call.
- **No UI.** Output is JSON and CLI text only. `demo_runner.py` is the sole user-facing interface.
- **Rule-based intent classification only.** Intent is determined by keyword matching in `INTENT_KEYWORDS` (see `src/operators/delta.py`). No ML-based classification. No semantic similarity. No disambiguation.
- **No adaptive thresholds.** NEXUS does not learn from escalation outcomes. Thresholds are static values in `data/risk_manifest.json`.
- **No dynamic threshold adjustment at runtime.** Changes to `risk_manifest.json` require a process restart to take effect (manifest is cached in memory via `load_risk_manifest()`).
- **TC-012 baseline comparison (`--mode compare`) consumes Anthropic API credits** for every invocation.

---

### Deferred fields — NOT YET IMPLEMENTED

The following fields are defined in the schema but their population logic is not implemented:

**`risk_subject.protected_class_data_present`**
> NOT YET IMPLEMENTED. Field exists in `RiskSubject` schema, defaults to `False`. Automatic detection of protected class data in queries (per Notion spec: `detect_protected_class_data()`) is not implemented. The field is never set to `True` by any operator.

**`risk_subject.pep_status`**
> NOT YET IMPLEMENTED. Field exists in `RiskSubject` schema, defaults to `"none"`. No PEP (Politically Exposed Person) detection or external screening logic is implemented. The field always retains its default value.

**`compliance_metadata.review_required_by`**
> NOT YET IMPLEMENTED. `compliance_metadata` is a plain `dict = {}` in `FinTechPayload`. Deadline computation per regulation (e.g., 30-day SAR filing window under BSA) is not implemented. This field is always empty.

**`compliance_metadata.documentation_requirements`**
> NOT YET IMPLEMENTED. Population logic deferred. `compliance_metadata` dict is always empty in the current MVP.

**`compliance_metadata.escalation_target`**
> NOT YET IMPLEMENTED as a schema field. Escalation routing is computed by `OmegaOperator._make_decision()` and written to `output["next_action"]` (e.g., `"Manual review required — route to Fair Lending Counsel"`), but it is not populated back into `domain_payload["compliance_metadata"]`.

---

### Deferred overlays — NOT YET IMPLEMENTED

**ABORT overlay** (pre-execution halt)
> NOT YET IMPLEMENTED. Not present in MVP.

**ACTUATION overlay** (post-execution validation)
> NOT YET IMPLEMENTED. Not present in MVP.

**SELF overlay** (reflection loop)
> NOT YET IMPLEMENTED. Not present in MVP.

**INV overlay** (invariant enforcement)
> PARTIAL. Cell schema validation is performed by the ARB overlay (Level 1 integrity check). A dedicated INV overlay is not present.

**ARB Level 3** (uncertainty abstention)
> NOT YET IMPLEMENTED. Uncertainty is non-binding in MVP — it is recorded in the cell and the LEDGER but is never read for governance decisions. The `_make_decision()` method in `OmegaOperator` explicitly does not read `uncertainty`. ARB Level 3 is commented as DEFERRED in `src/overlays/arb.py`.

---

### Deferred decision values and variants — NOT YET IMPLEMENTED

**`block` E.Decision value**
> NOT YET IMPLEMENTED. The value `"block"` is listed in the valid decisions set in `OmegaOperator._assert_invariants()` but is never produced by any current code path in `_make_decision()`. Queries exceeding the hard gate produce `"escalate"`, not `"block"`.

**`defer_to_risk_committee` escalation variant**
> NOT YET IMPLEMENTED. The current escalation variant map in `src/operators/omega.py` routes to `"defer_to_compliance_officer"` or `"defer_to_legal"` only. There is no `"defer_to_risk_committee"` variant in the `ESCALATION_VARIANT_MAP`.

**Hash-chaining of LEDGER entries**
> NOT YET IMPLEMENTED. See [Section 5](#5-ledger-storage-considerations) for details.

---

### Schema / spec divergences (not deferred — existing mismatch)

**`IntentType` enum vs. manifest keys**
> The `IntentType` enum in `src/schemas/fintech_payload.py` defines `FAIR_LENDING = "fair_lending"`, but the manifest key and all operator logic use `"fair_lending_check"`. The enum is not used by any operator — operators use plain string literals matching manifest keys. This mismatch does not affect runtime behavior but creates a documentation inconsistency.

---

## 8. Troubleshooting

### Common failure modes

| Symptom | Cause | Resolution |
|---|---|---|
| `ModuleNotFoundError: No module named 'pydantic'` | Dependencies not installed | `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'anthropic'` | `anthropic` package not installed | `pip install anthropic` or `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'src'` | Working directory is not project root | Run commands from `nexus-mvp/` directory |
| `ANTHROPIC_API_KEY not set` warning in logs | Missing `.env` or key not in environment | Create `.env` with `ANTHROPIC_API_KEY=sk-ant-...`; Α fallback activates automatically |
| `ERROR: ANTHROPIC_API_KEY not set.` (exits with code 1) | `--mode baseline` requires API key | Set up `.env` or use `--mode nexus` instead |
| `FileNotFoundError: risk_manifest.json` | Manifest missing or wrong working directory | Ensure `data/risk_manifest.json` exists; verify working directory is project root |
| `ValueError: Α operator requires a non-empty query` | Empty or whitespace-only string passed to `alpha_operator` | Provide a non-empty query string |
| `ValueError: Ω operator cannot process unevaluated cell` | Cell with `status="pending"` passed directly to Ω | Run `delta_operator(cell)` before `OmegaOperator.process()` |
| `ValueError: Cell missing required fields for Ω` | Malformed cell dict missing required keys | Ensure cell passes through both `alpha_operator` and `delta_operator` before reaching Ω |
| `RuntimeError: NEXUS INVARIANT VIOLATION: uncertainty.mode` | `cell["uncertainty"]` modified between operators | Do not modify the cell's `uncertainty` field between pipeline stages |
| `RuntimeError: NEXUS INVARIANT VIOLATION: uncertainty.binding` | `cell["uncertainty"]["binding"]` set to non-`False` | Same as above — do not modify uncertainty |
| `RuntimeError: LEDGER write failed` | Disk full, directory missing, or insufficient permissions | Verify `data/` directory exists and is writable; check disk space |
| Α always returns deterministic fallback | API key missing, `anthropic` not installed, or LLM error | Verify `.env` file and run `pip install anthropic`; check logs for specific LLM error |
| `KeyError` during risk score computation | Intent type not found in manifest | Ensure the intent type string matches a key in `data/risk_manifest.json` |

### Verifying system health

**Run the full test suite:**

```bash
pytest tests/ -v --tb=short
```

Expected result: **97 tests passing** (24 alpha + 45 delta + 17 omega + 11 governance).

**Quick smoke test (no API key required):**

```bash
python3 demo_runner.py "Approve a loan application" --mode nexus --no-color
```

Expected output includes:
- `Δ (risk eval)` line showing `intent=credit_decision`, a risk score, and `BLOCKED`
- `Ω (decision)` line showing `ESCALATE → defer_to_compliance_officer`
- `Audit trail: LEDGER entry written ✓`

If the smoke test produces this output, the full governance pipeline is operational.

**Inspect the LEDGER:**

```bash
# View the most recent entry
tail -1 data/ledger.jsonl | python3 -m json.tool
```

**Verify test count breakdown:**

```bash
pytest tests/ --collect-only -q 2>/dev/null | tail -5
```

### Log locations

Operators use Python's `logging` module. By default, no file handler is configured — log output goes to `stderr`.

To capture logs to a file:

```bash
python3 demo_runner.py "query" --mode nexus 2> nexus.log
```

For production deployments: configure logging handlers (`FileHandler`, `RotatingFileHandler`, or a structured logging integration) in the calling application. NEXUS itself does not configure any handlers — it only calls `logging.getLogger(__name__)` and emits to the logger hierarchy.

The **LEDGER** (`data/ledger.jsonl`) is the primary compliance audit log. Python logging output is operational telemetry only and should not be treated as the audit trail.
