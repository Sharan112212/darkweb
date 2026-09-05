"""
Collection framework module for SIH26151 Dark-Web Threat Actor Attribution Platform.
Exports CaptureManager, FixtureReplayer, TorCollector, CollectionNormalizer, and NormalizedPayload.
"""

from collection.capture_manager import CaptureManager
from collection.fixture_replayer import FixtureReplayer
from collection.tor_collector import TorCollector
from collection.normalizer import CollectionNormalizer, NormalizedPayload

__all__ = [
    "CaptureManager",
    "FixtureReplayer",
    "TorCollector",
    "CollectionNormalizer",
    "NormalizedPayload",
]
