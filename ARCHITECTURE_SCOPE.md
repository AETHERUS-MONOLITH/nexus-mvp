# NEXUS MVP REPOSITORY SCOPE

This repository contains the standalone governance kernel for NEXUS.

## Included

- Governance operators (Α, Δ, Ω)
- Decision logic
- Risk manifest
- Domain payload schemas
- Governance test suite
- Audit ledger implementation

## Excluded

- Orchestration pipelines
- Workflow automation
- Prompt orchestration
- Agent management

Those remain in the AETHERUS Pipeline repository.

## Integration Path

After MVP validation, this kernel may be integrated into the AETHERUS_MONOLITH
repository as a submodule or merged package. That decision is deferred until
governance validation is complete.
