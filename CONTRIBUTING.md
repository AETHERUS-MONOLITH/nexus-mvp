# Contributing

Thanks for helping improve NEXUS. Keep changes small, auditable, and aligned
with the governance contract described in the README and docs.

## Workflow

```bash
git clone https://github.com/AETHERUS-MONOLITH/nexus-mvp.git
cd nexus-mvp
python -m pip install -r requirements.txt
git checkout -b your-branch-name
```

Before opening a pull request, run:

```bash
python -m pytest tests/ -v --tb=short
python scripts/prove_determinism.py
```

Open a pull request against `main` with a short summary of what changed and
the validation results.

## Governance Changes

Do not change governance thresholds, risk manifest values, ledger behavior, or
decision semantics without matching tests and documentation. Threshold changes
must explain the policy reason and include proof that expected governance
behavior remains deterministic.
