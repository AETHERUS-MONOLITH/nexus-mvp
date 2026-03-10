"""
NEXUS MVP — Risk Manifest Schema
==================================
Pydantic models and loader for the FinTech Risk Manifest.

The Risk Manifest is the authoritative source of truth for Δ operator
classification. It defines:
    - Risk classes (intent categories with base risk scores)
    - Hard gate thresholds (τ^hard_r per class)
    - Jurisdiction modifiers (additive risk adjustments)
    - Regulatory framework mappings
    - Article references for audit trail

Design Principles:
    - Loaded once, read many times (module-level caching)
    - All values validated at load time (Pydantic enforces bounds)
    - Δ NEVER modifies the manifest — read-only contract
    - Risk scores and thresholds are [0.0, 1.0]

Specification Reference:
    FinTech Risk Manifest v1.0
"""

import json
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RiskClass(BaseModel):
    """
    Individual risk class definition.

    Fields:
        base_risk: Inherent risk score for this class [0.0, 1.0].
        tau_hard_r: Hard gate threshold. If computed risk > tau_hard_r → BLOCKED.
        regulatory_framework: Applicable regulatory frameworks.
        article_references: Statute/regulation citations for the audit trail.
        jurisdiction_modifiers: Additive risk adjustments by jurisdiction code.
    """
    base_risk: float = Field(ge=0.0, le=1.0)
    tau_hard_r: float = Field(ge=0.0, le=1.0)
    regulatory_framework: List[str]
    article_references: List[str]
    jurisdiction_modifiers: Dict[str, float] = {}


class RiskManifest(BaseModel):
    """
    Complete risk manifest — all risk classes and their configurations.
    Root model loaded from data/risk_manifest.json.
    """
    risk_classes: Dict[str, RiskClass]


# --- Module-level cache ---
_cached_manifest: Optional[RiskManifest] = None


def load_risk_manifest(manifest_path: Optional[str] = None) -> RiskManifest:
    """
    Load and validate the risk manifest from JSON.

    Uses module-level caching — loaded once, reused for all subsequent calls.

    Args:
        manifest_path: Optional explicit path. If None, resolves relative to this file.

    Returns:
        Validated RiskManifest instance.

    Raises:
        FileNotFoundError: If manifest JSON doesn't exist.
        json.JSONDecodeError: If manifest JSON is malformed.
        pydantic.ValidationError: If manifest data fails schema validation.
    """
    global _cached_manifest

    default_path = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "data", "risk_manifest.json"
    ))

    if _cached_manifest is not None and manifest_path is None:
        return _cached_manifest

    resolved_path = os.path.normpath(manifest_path) if manifest_path else default_path

    with open(resolved_path, "r") as f:
        data = json.load(f)

    manifest = RiskManifest(**data)

    if resolved_path == default_path:
        _cached_manifest = manifest

    return manifest


def reset_cache() -> None:
    """Clear the cached manifest. Used in testing."""
    global _cached_manifest
    _cached_manifest = None
