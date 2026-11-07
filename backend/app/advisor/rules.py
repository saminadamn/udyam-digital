"""Advisor-facing entry point to the rules engine (the engine itself lives in app/rules/engine.py, per DESIGN.md D6)."""
from app.rules.engine import (
    Profile,
    Violation,
    build_bundle,
    default_bundle,
    eligible_products,
    product_rules,
    rules_version,
    validate_bundle,
)

__all__ = ["Profile", "Violation", "build_bundle", "default_bundle", "eligible_products", "product_rules", "rules_version", "validate_bundle"]
