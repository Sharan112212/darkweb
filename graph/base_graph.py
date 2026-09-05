from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseGraphProjection(ABC):
    """
    Abstract Base Class for graph projection engines.
    Provides unified interface for NetworkX in-memory projection and Neo4j graph database.
    """

    @abstractmethod
    def add_node(self, entity_id: str, label: str = "Entity", attributes: Optional[Dict[str, Any]] = None) -> None:
        """Adds or updates a graph node."""

    @abstractmethod
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        link_id: str,
        score: float,
        tier: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Adds or updates a graph relationship edge."""

    @abstractmethod
    def get_projection(self) -> Dict[str, Any]:
        """Returns full graph projection structure with nodes and edges."""

    @abstractmethod
    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 4,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Finds multi-hop paths between source and target entities."""
