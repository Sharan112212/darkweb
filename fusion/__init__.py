"""
Fusion Engine Core Package for SIH26151.
Provides explainable multi-signal probabilistic fusion, indicator classification,
analyst explanation generation, conflict resolution, and link lifecycle management.
"""

from fusion.category_classifier import CategoryClassifier
from fusion.conflict_resolver import ConflictResolver
from fusion.explainable_fusion import ExplainableFusionEngine
from fusion.explanation_builder import ExplanationBuilder
from fusion.link_lifecycle import LinkLifecycleManager

__all__ = [
    "CategoryClassifier",
    "ConflictResolver",
    "ExplainableFusionEngine",
    "ExplanationBuilder",
    "LinkLifecycleManager",
]
