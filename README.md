# NEXUS — Governance Kernel for AI Systems

NEXUS is a governance kernel that enforces regulatory constraints on AI systems through deterministic, auditable risk gates. It sits between an LLM and any decision surface in a regulated FinTech environment, ensuring that high-risk financial queries — credit decisions, fair lending checks, AML screening, KYC verification — are structurally classified, gated, and logged regardless of model confidence or output. The core thesis: AI systems in regulated domains require governance that cannot be bypassed by a model, a prompt, or a confidence score.

---

## Architecture

Queries flow through a three-operator pipeline. Each stage has a single responsibility and a strict behavioral contract.

```
INPUT: query + regulatory context
  │
  ▼
Α  (alpha_operator)   — LLM intake and decomposition
                        Single API call. Falls back to deterministic decomposition
                        if no key is present. Does not classify or decide.
  │
  ▼
Δ  (delta_operator)   — Deterministic risk classification
                        Zero LLM calls. Keyword-based intent classification,
                        risk score computation (base + jurisdiction modifier),
                        hard gate evaluation: r > τ → BLOCKED.
  │
  ▼
Ω  (OmegaOperator)    — Decision gate
                        Applies ARB priority ladder. Produces E.Decision:
                        release | escalate | abstain.
                        Writes immutable LEDGER entry on every execution path.
  │
  ▼
OUTPUT: { decision, variant, reasoning, regulatory_reference, audit_record }
```

**Overlays:**

- **ARB** (Arbitration) — priority ladder: integrity violations (L1) take precedence over risk gate violations (L2). Deterministic. Zero LLM calls.
- **LEDGER** — append-only JSONL audit trail. Every Ω execution writes exactly one entry. SHA-256 input hash. No silent exits.

**Invariant enforced at every stage:** `uncertainty.mode = "proxy"`, `uncertainty.binding = False`. Uncertainty is recorded and non-binding. Governance decisions are made on risk scores alone.

---

## Key Features

- **Deterministic risk gates** — same input always produces the same decision. No probabilistic logic downstream of Α.
- **Hard gate semantics** — strict inequality (`r > τ`). Equal-to-threshold is not blocked. Benefit of the doubt is explicit policy.
- **Immutable audit trail** — LEDGER is append-only JSONL. Write failures raise `RuntimeError`. No silent swallowing.
- **Manifest-driven thresholds** — all risk values live in `data/risk_manifest.json`. Adjustable per risk class and jurisdiction without code changes.
- **Jurisdiction modifiers** — additive per-country risk adjustments. US ECOA exposure, EU/UK AML uplift, extensible to any ISO 3166-1 alpha-2 code.
- **Regulatory coverage** — ECOA, Fair Housing Act, FCRA, Regulation B, BSA/AML, USA PATRIOT Act, CIP/OFAC, GLBA, FTC Safeguards, HMDA, EU AI Act (framework-aware).
- **Graceful degradation** — Α falls back to rule-based decomposition when no API key is present. The governance pipeline remains fully functional.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/camilocarlone/nexus-mvp.git
cd nexus-mvp
pip install -r requirements.txt
```

### 2. Configure

```bash
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

The API key is required only for live LLM decomposition in Α and for `--mode baseline` / `--mode compare`. Without it, Α uses deterministic fallback and the full governance pipeline runs.

### 3. Run the demo

```bash
# NEXUS pipeline only — no API key required
python3 demo_runner.py "Approve a mortgage for a protected class applicant" --mode nexus

# Side-by-side: baseline LLM vs. NEXUS (requires API key)
python3 demo_runner.py "Wire transfer to sanctioned jurisdiction" --mode compare --jurisdiction US --framework BSA_AML

# Save full report to data/reports/
python3 demo_runner.py "Approve credit application" --mode compare --save
```

### 4. Run the test suite

```bash
python3 -m pytest tests/ -v --tb=short
```

Expected: **97 passed, 0 failed, 0 errors.**

---

## Direct Integration

```python
from src.operators.alpha import alpha_operator
from src.operators.delta import delta_operator
from src.operators.omega import OmegaOperator

cell = alpha_operator(query, context)
cell = delta_operator(cell)
output = OmegaOperator(ledger_path="data/ledger.jsonl").process(cell, query, {})

print(output["decision"])       # "release" | "escalate" | "abstain"
print(output["reasoning"])
print(output["audit_record"])
```

See [`docs/API.md`](docs/API.md) for full interface documentation and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for production deployment guidance.

---

## Project Status

MVP validated. 97/97 tests passing across unit, integration, and governance correctness suites. Risk manifest covers 7 intent classes with US, EU, and UK jurisdiction modifiers. LEDGER audit trail confirmed across all execution paths.

Current phase: **Phase 9 — Pilot Preparation.**
