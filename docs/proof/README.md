# MVP Proof Commands

This directory contains public proof artifacts for the NEXUS MVP. Run commands
from the repository root.

## Install

```bash
git clone https://github.com/AETHERUS-MONOLITH/nexus-mvp.git
cd nexus-mvp
python -m pip install -r requirements.txt
```

Python 3.9+ is supported for the MVP. The public proof run is validated on
Python 3.9.6.

## Tests

```bash
python -m pytest tests/ -v --tb=short
```

Expected result:

```text
97 passed
```

## Demo

The NEXUS-only demo does not require an API key. Without
`ANTHROPIC_API_KEY`, Α uses deterministic fallback decomposition and the
governance pipeline still runs.

```bash
python demo_runner.py "Approve a mortgage for a protected class applicant" --mode nexus --jurisdiction US --framework ECOA --no-color
python demo_runner.py "Wire transfer to sanctioned jurisdiction" --mode nexus --jurisdiction US --framework BSA_AML --no-color
```

`timestamp`, `run_id`, UUIDs, and LEDGER append order are intentionally
variable between runs. Deterministic governance behavior is proven by stable
decision fields, not by byte-for-byte identical CLI output.

## Determinism Proof

```bash
python scripts/prove_determinism.py
```

This script runs the same governance input three times and compares only these
stable fields:

- `intent`
- `risk_score`
- `status`
- `decision`
- `variant`
- `reasoning`
- `regulatory_reference`

It explicitly excludes `timestamp`, `run_id`, UUIDs, and LEDGER append order.
It prints `PASS` only when all stable decision fields match.
